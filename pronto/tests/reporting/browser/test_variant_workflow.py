"""Review filters and progress operate on stable variant identities."""

from dataclasses import replace
import json
from pathlib import Path

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
            page.set_default_timeout(3000)
            page.goto(url)
            page.get_by_role("tab", name="Variant review").click()
            assert page.locator("#review-progress").inner_text() == "1 of 29 variants reviewed"
            page.get_by_role("button", name="Exclude 2").click()
            assert page.locator("#variant-table tbody tr:visible").count() == 2
            assert page.locator("#variant-count").inner_text() == "2 of 30 occurrences"
            page.get_by_role("button", name="All 30").click()
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
            page.set_default_timeout(3000)
            page.goto(url)
            page.get_by_role("tab", name="Variant review").click()
            page.get_by_label("Search variants").fill("TERT")
            rows = page.locator("#variant-table tbody tr:visible")
            assert rows.count() == 2
            occurrence_ids = rows.evaluate_all("items => items.map(item => item.dataset.occurrenceId)")
            variant_ids = rows.evaluate_all("items => items.map(item => item.querySelector('select').dataset.variantId)")
            assert len(set(occurrence_ids)) == 2
            assert len(set(variant_ids)) == 1
            page.get_by_role("button", name="Sort by allele frequency").click()
            assert set(rows.evaluate_all("items => items.map(item => item.dataset.occurrenceId)")) == set(occurrence_ids)
            rows.first.locator('select[data-review-field="reportingDecision"]').select_option("INCLUDE")
            assert rows.nth(1).locator('select[data-review-field="reportingDecision"]').input_value() == "INCLUDE"
            assert page.locator("#review-progress").inner_text() == "1 of 29 variants reviewed"
            page.get_by_role("button", name="Include 2").click()
            assert rows.count() == 2
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_bulk_action_requires_confirmation_and_changes_one_visible_unique_variant(browser):
    report = build_report()
    review = replace(draft_review(report), variant_reviews=())
    html = render_html(report, review, inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.set_default_timeout(3000)
            page.goto(url)
            page.get_by_role("tab", name="Variant review").click()
            page.get_by_label("Search variants").fill("TERT")
            button = page.get_by_role("button", name="Include visible unreviewed")
            dialogs = []
            page.once("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
            button.click()
            assert "1 unique variant" in dialogs[0]
            assert page.locator("#review-progress").inner_text() == "0 of 29 variants reviewed"
            page.once("dialog", lambda dialog: dialog.accept())
            button.click()
            rows = page.locator("#variant-table tbody tr:visible")
            assert rows.count() == 2
            assert rows.first.locator('select[data-review-field="reportingDecision"]').input_value() == "INCLUDE"
            assert rows.nth(1).locator('select[data-review-field="reportingDecision"]').input_value() == "INCLUDE"
            assert rows.first.locator('select[data-review-field="clinicalClassification"]').input_value() == "UNCLASSIFIED"
            assert page.locator("#review-progress").inner_text() == "1 of 29 variants reviewed"
            with page.expect_download() as pending:
                page.get_by_role("button", name="Download ReviewState").click()
            saved = json.loads(Path(pending.value.path()).read_text(encoding="utf-8"))
            assert len(saved["variantReviews"]) == 1
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_bulk_action_never_overwrites_existing_decision(browser):
    report = build_report()
    review = draft_review(report)
    html = render_html(report, review, inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.set_default_timeout(3000)
            page.goto(url)
            page.get_by_role("tab", name="Variant review").click()
            dialogs = []
            page.once("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.accept()))
            page.get_by_role("button", name="Include visible unreviewed").click()
            assert "28 unique variants" in dialogs[0]
            tert = page.locator(f'#variant-table tbody tr select[data-variant-id="{review.variant_reviews[0]["variantId"]}"][data-review-field="reportingDecision"]')
            assert tert.count() == 2
            assert tert.first.input_value() == "EXCLUDE"
            assert page.locator("#review-progress").inner_text() == "29 of 29 variants reviewed"
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_variant_comment_syncs_duplicate_rows_without_changing_decision_or_classification(browser):
    report = build_report()
    review = draft_review(report)
    html = render_html(report, review, inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.set_default_timeout(3000)
            page.goto(url)
            page.get_by_role("tab", name="Variant review").click()
            page.get_by_label("Search variants").fill("TERT")
            comments = page.locator('#variant-table tbody tr:visible textarea[data-review-field="comment"]')
            assert comments.count() == 2
            comments.first.fill("Confirmet i gjennomgang")
            assert comments.nth(1).input_value() == "Confirmet i gjennomgang"
            assert page.locator("#dirty-lbl").inner_text() == "Unsaved review"
            with page.expect_download() as pending:
                page.get_by_role("button", name="Download ReviewState").click()
            saved = json.loads(Path(pending.value.path()).read_text(encoding="utf-8"))
            activity = next(item for item in saved["variantReviews"] if item["variantId"] == review.variant_reviews[0]["variantId"])
            assert activity["comment"] == "Confirmet i gjennomgang"
            assert activity["reportingDecision"] == "EXCLUDE"
            assert activity["clinicalClassification"] == "PATHOGENIC"
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_clinical_filter_is_independent_of_reporting_decision(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.set_default_timeout(3000)
            page.goto(url)
            page.get_by_role("tab", name="Variant review").click()
            page.get_by_role("button", name="Pathogenic 2").click()
            rows = page.locator("#variant-table tbody tr:visible")
            assert rows.count() == 2
            assert rows.first.locator('select[data-review-field="reportingDecision"]').input_value() == "EXCLUDE"
            rows.first.locator('select[data-review-field="clinicalClassification"]').select_option("UNCERTAIN")
            assert rows.count() == 0
            page.get_by_role("button", name="Uncertain 2").click()
            assert rows.count() == 2
            assert rows.first.locator('select[data-review-field="reportingDecision"]').input_value() == "EXCLUDE"
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_igv_assessment_syncs_duplicates_without_inventing_source_qc(browser):
    report = build_report()
    review = draft_review(report)
    html = render_html(report, review, inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.set_default_timeout(3000)
            page.goto(url)
            page.get_by_role("tab", name="Variant review").click()
            page.get_by_label("Search variants").fill("TERT")
            controls = page.locator('#variant-table tbody tr:visible select[data-review-field="igvAssessment"]')
            assert controls.count() == 2
            controls.first.select_option("SUPPORTS")
            assert controls.nth(1).input_value() == "SUPPORTS"
            with page.expect_download() as pending:
                page.get_by_role("button", name="Download ReviewState").click()
            saved = json.loads(Path(pending.value.path()).read_text(encoding="utf-8"))
            activity = next(item for item in saved["variantReviews"] if item["variantId"] == review.variant_reviews[0]["variantId"])
            assert activity["igvAssessment"] == "SUPPORTS"
            assert activity["reportingDecision"] == "EXCLUDE"
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_variant_review_keeps_mobile_page_width_and_scrollable_table(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html, width=375)
        try:
            page.goto(url)
            page.get_by_role("tab", name="Variant review").click()
            assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            assert page.locator("#variant-table").evaluate("table => table.scrollWidth > table.parentElement.clientWidth")
            assert page.get_by_role("button", name="Pathogenic 2").is_visible()
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()
