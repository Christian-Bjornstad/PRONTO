"""The live report writes only on an explicit, acknowledged save."""

import json
from pathlib import Path
from pronto.tests.reporting.browser.test_report import _page, _serve, browser, playwright
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html
from pronto_report.migration import migrate_review_state_v1
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import validate_review_state

expect = playwright.expect


def _live_report():
    report = build_report()
    return render_html(
        report, draft_review(report), inline_assets=True,
        save_url=f"/reports/{report.report_id}/revisions/",
        csrf_token="test-csrf-token", actor_id="7",
    )


def test_reset_cancel_then_confirm_reloads_blank_saved_revision(browser):
    report = build_report()
    original = migrate_review_state_v1(draft_review(report))
    base_url = f'/reports/{report.report_id}'
    initial_html = render_html(report, original, inline_assets=True,
        save_url=f'{base_url}/revisions/', reset_url=f'{base_url}/resets/',
        csrf_token='test-csrf-token', actor_id='7', require_initials=True)
    reset_document = json.loads(serialize_review_state(original))
    reset_document.update(revision=2, variantReviews=[], runQcAssessment={'status': 'NOT_REVIEWED'},
        valueCorrections=[], lastSavedAttribution={'declaredInitials': 'AB', 'method': 'SELF_REPORTED'})
    reset_document['notes'].update(summary='', biomarkerContext='', additional='')
    reset_review = validate_review_state(reset_document, report=report)
    reset_html = render_html(report, reset_review, inline_assets=True,
        save_url=f'{base_url}/revisions/', reset_url=f'{base_url}/resets/',
        csrf_token='test-csrf-token', actor_id='7', require_initials=True)
    with _serve(initial_html) as url:
        context, page, diagnostics, _requests = _page(browser, initial_html)
        state = {'reset': False, 'commands': []}
        try:
            page.route(url, lambda route: route.fulfill(status=200, content_type='text/html',
                       body=reset_html if state['reset'] else initial_html))
            def reset(route):
                state['commands'].append(json.loads(route.request.post_data))
                state['reset'] = True
                route.fulfill(status=201, content_type='application/json',
                              body=json.dumps({'schemaVersion': '1.0', 'review': reset_document,
                                               'audit': {'action': 'RESET_DRAFT'}}))
            page.route('**/resets/', reset)
            page.goto(url)
            page.locator('[data-include-variant]').first.click()
            expect(page.locator('#dirty-lbl')).to_have_text('Unsaved review')
            page.once('dialog', lambda dialog: dialog.dismiss())
            page.get_by_role('button', name='Reset', exact=True).click()
            assert state['commands'] == []
            expect(page.locator('#dirty-lbl')).to_have_text('Unsaved review')
            page.once('dialog', lambda dialog: dialog.accept())
            page.get_by_role('button', name='Reset', exact=True).click()
            page.get_by_label('Your initials').fill('AB')
            page.get_by_role('button', name='Confirm', exact=True).click()
            expect(page.locator('#board-saved-revision')).to_have_text('Saved revision: 2')
            expect(page.locator('#dirty-lbl')).to_have_text('All changes saved')
            assert page.locator('[data-include-variant][aria-pressed="true"]').count() == 0
            assert state['commands'][0] == {'schemaVersion': '1.0', 'reportId': report.report_id,
                                            'baseRevision': 1, 'declaredInitials': 'AB'}
            assert diagnostics == []
        finally:
            context.close()


def test_reset_conflict_retains_local_working_copy(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True,
        save_url='/save/', reset_url='/reset/', csrf_token='test', actor_id='7', require_initials=True)
    with _serve(html) as url:
        context, page, diagnostics, _requests = _page(browser, html)
        try:
            page.route('**/reset/', lambda route: route.fulfill(status=409,
                content_type='application/json', body=json.dumps({'error': {
                    'code': 'REVISION_CONFLICT', 'currentRevision': 2}})))
            page.goto(url)
            page.locator('[data-include-variant]').first.click()
            page.once('dialog', lambda dialog: dialog.accept())
            page.get_by_role('button', name='Reset', exact=True).click()
            page.get_by_label('Your initials').fill('AB')
            page.get_by_role('button', name='Confirm', exact=True).click()
            expect(page.locator('#save-error')).to_contain_text('revision 2')
            expect(page.locator('#dirty-lbl')).to_have_text('Unsaved review')
            assert page.locator('[data-include-variant][aria-pressed="true"]').count() == 1
            assert all('409' in message for message in diagnostics)
        finally:
            context.close()


def test_html_download_blocks_dirty_and_uses_current_saved_revision(browser):
    report = build_report()
    review = migrate_review_state_v1(draft_review(report))
    html = render_html(report, review, inline_assets=True,
        save_url='/save/', html_export_url='/html-exports/',
        csrf_token='test', actor_id='7', require_initials=True)
    with _serve(html) as url:
        context, page, diagnostics, _requests = _page(browser, html)
        commands = []
        try:
            def export(route):
                commands.append(json.loads(route.request.post_data))
                route.fulfill(status=200, content_type='text/html; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename="saved-report.html"'},
                    body='<!doctype html><html><body>Saved report</body></html>')
            page.route('**/html-exports/', export)
            page.goto(url)
            page.locator('[data-include-variant]').first.click()
            page.get_by_role('button', name='Download report HTML').click()
            expect(page.locator('#html-export-status')).to_contain_text('Save changes')
            assert commands == []
            page.reload()
            with page.expect_download() as pending:
                page.get_by_role('button', name='Download report HTML').click()
                page.get_by_label('Your initials').fill('AB')
                page.get_by_role('button', name='Confirm', exact=True).click()
            assert pending.value.suggested_filename == 'saved-report.html'
            assert commands[0]['revision'] == 1
            assert commands[0]['declaredInitials'] == 'AB'
            assert commands[0]['reportId'] == report.report_id
            assert page.locator('#dirty-lbl').inner_text() == 'All changes saved'
            assert diagnostics == []
        finally:
            context.close()


def test_final_report_offers_html_download_without_edit_controls():
    report = build_report()
    document = json.loads(serialize_review_state(migrate_review_state_v1(draft_review(report))))
    document.update(status='FINAL', finalizedAt='2026-09-29T12:00:00Z',
                    finalizedBy='biologist-1', updatedAt='2026-09-29T12:00:00Z')
    final = validate_review_state(document, report=report)
    html = render_html(report, final, inline_assets=True,
        html_export_url='/html-exports/', csrf_token='test', require_initials=True)
    assert '>Download report HTML</button>' in html
    assert 'id="reset-btn"' not in html
    assert 'id="finalize-btn"' not in html


def test_explicit_save_advances_revision_once_and_never_autosaves(browser):
    html = _live_report()
    commands = []
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            def save(route):
                commands.append(json.loads(route.request.post_data))
                draft = commands[-1]["draft"]
                response = {"schemaVersion": "1.0", "review": {**draft, "revision": draft["revision"] + 1}}
                route.fulfill(status=201, content_type="application/json", body=json.dumps(response))

            page.route("**/revisions/", save)
            page.goto(url)
            page.get_by_role("tab", name="Tumour board report").click()
            page.locator('textarea[data-review-note="summary"]').fill("Syntetisk oppsummering")
            assert commands == []
            assert page.locator("#dirty-lbl").inner_text() == "Unsaved review"
            assert page.evaluate("window.dispatchEvent(new Event('beforeunload', {cancelable:true}))") is False
            page.locator("#save-btn").click()
            expect(page.locator("#review-feedback")).to_have_text("Saved as revision 2.")
            assert page.locator("#dirty-lbl").inner_text() == "All changes saved"
            assert page.locator("#save-btn").is_disabled()
            assert len(commands) == 1
            assert commands[0]["baseRevision"] == 1
            assert commands[0]["draft"]["notes"]["summary"] == "Syntetisk oppsummering"
            page.locator('textarea[data-review-note="summary"]').fill("Neste syntetiske revisjon")
            page.get_by_role("tab", name="Variant review").click()
            with page.expect_download() as pending:
                page.locator("#download-review").click()
            exported = json.loads(Path(pending.value.path()).read_text(encoding="utf-8"))
            assert exported["revision"] == 2
            page.locator("#save-btn").click()
            expect(page.locator("#review-feedback")).to_have_text("Saved as revision 3.")
            assert len(commands) == 2
            assert commands[1]["baseRevision"] == 2
            assert page.evaluate("localStorage.length") == 0
            assert diagnostics == []
        finally:
            context.close()


def test_conflict_keeps_edit_and_offers_local_export(browser):
    html = _live_report()
    with _serve(html) as url:
        context, page, diagnostics, _requests = _page(browser, html)
        try:
            page.route("**/revisions/", lambda route: route.fulfill(
                status=409, content_type="application/json",
                body=json.dumps({"schemaVersion": "1.0", "error": {
                    "code": "REVISION_CONFLICT", "currentRevision": 3,
                }}),
            ))
            page.goto(url)
            page.get_by_role("tab", name="Tumour board report").click()
            note = page.locator('textarea[data-review-note="summary"]')
            note.fill("Lokal tekst som må beholdes")
            page.locator("#save-btn").click()
            expect(page.locator("#save-error")).to_contain_text("revision exists (3)")
            assert page.locator("#save-error").get_attribute("role") == "alert"
            assert note.input_value() == "Lokal tekst som må beholdes"
            assert page.locator("#dirty-lbl").inner_text() == "Unsaved review"
            with page.expect_download() as pending:
                page.locator("#export-local-draft").click()
            exported = json.loads(Path(pending.value.path()).read_text(encoding="utf-8"))
            assert exported["revision"] == 1
            assert exported["notes"]["summary"] == "Lokal tekst som må beholdes"
            assert all("409" in item for item in diagnostics)
        finally:
            context.close()


def test_failed_save_preserves_correction_and_requires_reason(browser):
    html = _live_report()
    commands = []
    with _serve(html) as url:
        context, page, diagnostics, _requests = _page(browser, html)
        try:
            page.route("**/revisions/", lambda route: (
                commands.append(json.loads(route.request.post_data)),
                route.fulfill(status=422, content_type="application/json", body='{"error":{"code":"INVALID_DRAFT"}}'),
            ))
            page.goto(url)
            page.locator("#edit-btn").click()
            page.get_by_role("tab", name="Key findings").click()
            page.locator("#tmb-edit-value").fill("12")
            page.locator("#tmb-edit-value").dispatch_event("change")
            page.locator("#save-btn").click()
            assert commands == []
            assert "Give a reason" in page.locator("#save-error").inner_text()
            page.locator("#tmb-correction-reason").fill("Syntetisk kontroll")
            with page.expect_request("**/revisions/"):
                page.locator("#save-btn").click()
            assert len(commands) == 1
            correction = commands[0]["draft"]["valueCorrections"][-1]
            assert correction["author"] == "7"
            assert correction["reason"] == "Syntetisk kontroll"
            expect(page.locator("#dirty-lbl")).to_have_text("Unsaved source corrections")
            assert page.locator("#tmb-edit-value").input_value() == "12"
            assert all("422" in item for item in diagnostics)
        finally:
            context.close()


def test_network_failure_does_not_claim_the_draft_was_saved(browser):
    html = _live_report()
    with _serve(html) as url:
        context, page, _diagnostics, _requests = _page(browser, html)
        try:
            page.route("**/revisions/", lambda route: route.abort("failed"))
            page.goto(url)
            page.get_by_role("tab", name="Tumour board report").click()
            note = page.locator('textarea[data-review-note="summary"]')
            note.fill("Syntetisk lokalt utkast")
            page.locator("#save-btn").click()
            expect(page.locator("#save-error")).to_contain_text("Save could not be confirmed")
            assert note.input_value() == "Syntetisk lokalt utkast"
            assert page.locator("#dirty-lbl").inner_text() == "Unsaved review"
            assert page.locator("#save-btn").is_enabled()
        finally:
            context.close()


def test_saved_correction_can_be_removed_without_changing_source(browser):
    report = build_report()
    document = json.loads(serialize_review_state(migrate_review_state_v1(draft_review(report))))
    document["valueCorrections"] = [{
        "path": "/sample/tumourType", "originalValue": None,
        "correctedValue": "Syntetisk korrigert", "reason": "Syntetisk kontroll",
        "author": "7", "timestamp": "2026-09-24T12:00:00Z",
    }]
    review = validate_review_state(document, report=report)
    html = render_html(
        report, review, inline_assets=True,
        save_url=f"/reports/{report.report_id}/revisions/",
        csrf_token="test-csrf-token", actor_id="7",
    )
    commands = []
    with _serve(html) as url:
        context, page, _diagnostics, _requests = _page(browser, html)
        try:
            page.route("**/revisions/", lambda route: (
                commands.append(json.loads(route.request.post_data)),
                route.fulfill(status=422, content_type="application/json", body='{"error":{"code":"INVALID_DRAFT"}}'),
            ))
            page.goto(url)
            assert "Corrected" in page.locator('[data-fact="tumourType"]').text_content()
            assert "Current: Syntetisk korrigert" in page.locator('[data-fact="tumourType"]').text_content()
            assert page.locator('[data-fact="tumourType"] dd').text_content() == "Syntetisk korrigert"
            page.locator("#edit-btn").click()
            field = page.locator("#tumourType-edit")
            page.get_by_role("tab", name="Key findings").click()
            assert field.input_value() == "Syntetisk korrigert"
            field.fill("")
            assert page.locator('[data-fact="tumourType"] dd').text_content() == "Not reported"
            assert page.locator("#dirty-lbl").inner_text() == "Unsaved source corrections"
            with page.expect_request("**/revisions/"):
                page.locator("#save-btn").click()
            assert commands[0]["draft"]["valueCorrections"] == []
            assert report.sample.get("tumourType") is None
        finally:
            context.close()
