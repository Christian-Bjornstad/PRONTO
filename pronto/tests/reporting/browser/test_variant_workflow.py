"""Review filters and progress operate on stable variant identities."""

from pronto.tests.reporting.browser.test_report import _page, _serve, browser
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html


def test_decision_chips_and_progress_track_unique_variants(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            page.get_by_role("tab", name="Variantgjennomgang").click()
            assert page.locator("#review-progress").inner_text() == "1 av 29 varianter vurdert"
            page.get_by_role("button", name="Ekskludert 2").click()
            assert page.locator("#variant-table tbody tr:visible").count() == 2
            assert page.locator("#variant-count").inner_text() == "2 av 30 forekomster"
            page.get_by_role("button", name="Alle 30").click()
            assert page.locator("#variant-table tbody tr:visible").count() == 30
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_search_sort_and_duplicate_decision_keep_ids_and_progress(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            page.get_by_role("tab", name="Variantgjennomgang").click()
            page.get_by_label("Søk i varianter").fill("TERT")
            rows = page.locator("#variant-table tbody tr:visible")
            assert rows.count() == 2
            occurrence_ids = rows.evaluate_all("items => items.map(item => item.dataset.occurrenceId)")
            variant_ids = rows.evaluate_all("items => items.map(item => item.querySelector('select').dataset.variantId)")
            assert len(set(occurrence_ids)) == 2
            assert len(set(variant_ids)) == 1
            page.get_by_role("button", name="Sorter etter variantallelfrekvens").click()
            assert set(rows.evaluate_all("items => items.map(item => item.dataset.occurrenceId)")) == set(occurrence_ids)
            rows.first.locator('select[data-review-field="reportingDecision"]').select_option("INCLUDE")
            assert rows.nth(1).locator('select[data-review-field="reportingDecision"]').input_value() == "INCLUDE"
            assert page.locator("#review-progress").inner_text() == "1 av 29 varianter vurdert"
            page.get_by_role("button", name="Inkludert 2").click()
            assert rows.count() == 2
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()
