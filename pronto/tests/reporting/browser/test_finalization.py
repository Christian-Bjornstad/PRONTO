"""Confirmation and lock behavior for an authenticated report draft."""

from dataclasses import replace
import json

from pronto.tests.reporting.browser.test_report import _page, _serve, browser, playwright
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.migration import migrate_review_state_v1
from pronto_report.renderers.html import render_html
from pronto_report.serialization import serialize_review_state

expect = playwright.expect


def _live_report(report):
    return render_html(
        report, draft_review(report), inline_assets=True,
        save_url=f"/reports/{report.report_id}/revisions/",
        finalize_url=f"/reports/{report.report_id}/finalizations/",
        csrf_token="test-csrf-token", actor_id="7",
    )


def test_unsaved_changes_disable_finalization_and_cancel_does_not_write(browser):
    report = build_report()
    html = _live_report(report)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            final = page.locator("#finalize-btn")
            assert final.is_enabled()
            page.once("dialog", lambda dialog: dialog.dismiss())
            final.click()
            assert requests == [url]
            page.get_by_role("tab", name="Molekylært tumorboard").click()
            page.locator('textarea[data-review-note="summary"]').fill("Ulagret syntetisk notat")
            assert final.is_disabled()
            assert "Lagre endringene" in page.locator("#finalize-hint").inner_text()
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_confirmed_finalization_reloads_locked_server_snapshot(browser):
    report = build_report()
    html = _live_report(report)
    timestamp = "2026-09-24T12:00:00Z"
    final_review = replace(
        migrate_review_state_v1(draft_review(report)), revision=2, status="FINAL",
        updated_at=timestamp, finalized_at=timestamp, finalized_by="7",
    )
    final_html = render_html(report, final_review, inline_assets=True)
    commands = []
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            page.route(url, lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body=final_html))

            def finalize(route):
                commands.append(json.loads(route.request.post_data))
                route.fulfill(status=201, content_type="application/json", body=json.dumps({
                    "schemaVersion": "1.0", "review": json.loads(serialize_review_state(final_review)),
                }))

            page.route("**/finalizations/", finalize)
            page.once("dialog", lambda dialog: dialog.accept())
            page.locator("#finalize-btn").click()
            expect(page.locator(".status-badge")).to_have_text("Rapportstatus: Endelig")
            assert commands[0]["baseRevision"] == 1
            assert commands[0]["draft"]["status"] == "DRAFT"
            assert page.locator("#finalize-btn").count() == 0
            assert page.locator("#save-btn").is_disabled()
            assert page.locator('textarea[data-review-note="summary"]').is_disabled()
            assert len(commands) == 1
            assert diagnostics == []
        finally:
            context.close()


def test_finalization_conflict_preserves_draft_and_offers_recovery(browser):
    report = build_report()
    html = _live_report(report)
    with _serve(html) as url:
        context, page, diagnostics, _requests = _page(browser, html)
        try:
            page.route("**/finalizations/", lambda route: route.fulfill(
                status=409, content_type="application/json",
                body=json.dumps({"error": {"code": "REVISION_CONFLICT", "currentRevision": 2}}),
            ))
            page.goto(url)
            page.once("dialog", lambda dialog: dialog.accept())
            page.locator("#finalize-btn").click()
            expect(page.locator("#save-error")).to_contain_text("revisjon 2")
            assert page.locator("#export-local-draft").is_visible()
            assert page.locator("#finalize-btn").is_enabled()
            assert page.locator(".status-badge").text_content() == "Rapportstatus: Utkast"
            assert all("409" in item for item in diagnostics)
        finally:
            context.close()


def test_failed_finalization_keeps_draft_editable(browser):
    report = build_report()
    html = _live_report(report)
    with _serve(html) as url:
        context, page, _diagnostics, _requests = _page(browser, html)
        try:
            page.route("**/finalizations/", lambda route: route.abort("failed"))
            page.goto(url)
            page.once("dialog", lambda dialog: dialog.accept())
            page.locator("#finalize-btn").click()
            expect(page.locator("#save-error")).to_contain_text("Kunne ikke bekrefte ferdigstilling")
            assert page.locator("#finalize-btn").is_enabled()
            assert page.locator(".status-badge").text_content() == "Rapportstatus: Utkast"
            page.get_by_role("tab", name="Molekylært tumorboard").click()
            note = page.locator('textarea[data-review-note="summary"]')
            note.fill("Kan fortsatt redigeres")
            assert page.locator("#dirty-lbl").inner_text() == "Ulagret gjennomgang"
        finally:
            context.close()
