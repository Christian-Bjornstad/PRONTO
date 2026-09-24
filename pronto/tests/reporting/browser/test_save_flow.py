"""The live report writes only on an explicit, acknowledged save."""

import json
from pathlib import Path
from playwright.sync_api import expect

from pronto.tests.reporting.browser.test_report import _page, _serve, browser
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html


def _live_report():
    report = build_report()
    return render_html(
        report, draft_review(report), inline_assets=True,
        save_url=f"/reports/{report.report_id}/revisions/",
        csrf_token="test-csrf-token", actor_id="7",
    )


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
            page.get_by_role("tab", name="Molekylært tumorboard").click()
            page.locator('textarea[data-review-note="summary"]').fill("Syntetisk oppsummering")
            assert commands == []
            assert page.locator("#dirty-lbl").inner_text() == "Ulagret gjennomgang"
            assert page.evaluate("window.dispatchEvent(new Event('beforeunload', {cancelable:true}))") is False
            page.locator("#save-btn").click()
            expect(page.locator("#review-feedback")).to_have_text("Lagret som revisjon 2.")
            assert page.locator("#dirty-lbl").inner_text() == "Alle endringer lagret"
            assert page.locator("#save-btn").is_disabled()
            assert len(commands) == 1
            assert commands[0]["baseRevision"] == 1
            assert commands[0]["draft"]["notes"]["summary"] == "Syntetisk oppsummering"
            page.locator('textarea[data-review-note="summary"]').fill("Neste syntetiske revisjon")
            page.get_by_role("tab", name="Variantgjennomgang").click()
            with page.expect_download() as pending:
                page.locator("#download-review").click()
            exported = json.loads(Path(pending.value.path()).read_text(encoding="utf-8"))
            assert exported["revision"] == 2
            page.locator("#save-btn").click()
            expect(page.locator("#review-feedback")).to_have_text("Lagret som revisjon 3.")
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
            page.get_by_role("tab", name="Molekylært tumorboard").click()
            note = page.locator('textarea[data-review-note="summary"]')
            note.fill("Lokal tekst som må beholdes")
            page.locator("#save-btn").click()
            expect(page.locator("#save-error")).to_contain_text("revisjon 3")
            assert page.locator("#save-error").get_attribute("role") == "alert"
            assert note.input_value() == "Lokal tekst som må beholdes"
            assert page.locator("#dirty-lbl").inner_text() == "Ulagret gjennomgang"
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
            page.locator("#tmb-edit-value").fill("12")
            page.locator("#tmb-edit-value").dispatch_event("change")
            page.locator("#save-btn").click()
            assert commands == []
            assert "Begrunn" in page.locator("#save-error").inner_text()
            page.locator("#tmb-correction-reason").fill("Syntetisk kontroll")
            with page.expect_request("**/revisions/"):
                page.locator("#save-btn").click()
            assert len(commands) == 1
            correction = commands[0]["draft"]["valueCorrections"][-1]
            assert correction["author"] == "7"
            assert correction["reason"] == "Syntetisk kontroll"
            assert page.locator("#dirty-lbl").inner_text() == "Ulagrede kildekorreksjoner"
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
            page.get_by_role("tab", name="Molekylært tumorboard").click()
            note = page.locator('textarea[data-review-note="summary"]')
            note.fill("Syntetisk lokalt utkast")
            page.locator("#save-btn").click()
            expect(page.locator("#save-error")).to_contain_text("Kunne ikke bekrefte lagring")
            assert note.input_value() == "Syntetisk lokalt utkast"
            assert page.locator("#dirty-lbl").inner_text() == "Ulagret gjennomgang"
            assert page.locator("#save-btn").is_enabled()
        finally:
            context.close()
