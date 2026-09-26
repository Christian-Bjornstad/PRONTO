"""Tumour-board edits stay in the page working copy until explicit export/save."""

from io import BytesIO
import json
from pathlib import Path

import pytest
from dataclasses import replace

from pronto.tests.reporting.browser.test_report import _page, _serve, browser
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto.tests.reporting.test_reference_projection import review_document
from pronto_report.renderers.html import render_html
from pronto_report.validation import validate_review_state


pypdf = pytest.importorskip("pypdf")


def test_read_only_export_print_preserves_included_variant_comment(browser):
    report = build_report()
    review = validate_review_state(review_document(report, report.variants[2]['variantId']), report=report)
    activity = dict(review.variant_reviews[0], comment='Kontrollert i IGV. Diskuteres i MDT.')
    review = replace(review, variant_reviews=(activity,))
    html = render_html(report, review, inline_assets=True, snapshot=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            page.get_by_role('tab', name='Molekylært tumorboard').click()
            assert page.locator('#board-findings').inner_text().count('Kontrollert i IGV.') == 1
            assert page.locator('#board-findings script').count() == 0
            pdf = page.pdf()
            printed = '\n'.join(sheet.extract_text() or '' for sheet in pypdf.PdfReader(BytesIO(pdf)).pages)
            assert 'Kontrollert i IGV. Diskuteres i MDT.' in printed
            assert diagnostics == []
        finally:
            context.close()


def test_three_board_notes_update_preview_and_review_export_without_network_write(browser):
    report = build_report()
    review = validate_review_state(review_document(report, report.variants[2]["variantId"]), report=report)
    html = render_html(report, review, inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            page.get_by_role("tab", name="Molekylært tumorboard").click()
            page.get_by_label("Interpretation summary").fill("Oppsummert funn")
            page.get_by_label("Biomarkører og terapeutisk kontekst").fill("TMB og MSI vurdert")
            page.get_by_label("Tilleggskommentarer").fill("Drøftes i MDT")
            assert page.locator("#dirty-lbl").inner_text() == "Ulagret gjennomgang"
            assert page.locator('[data-print-note="summary"]').inner_text() == "Oppsummert funn"
            page.get_by_role("tab", name="Variantgjennomgang").click()
            with page.expect_download() as pending:
                page.get_by_role("button", name="Last ned ReviewState").click()
            saved = json.loads(Path(pending.value.path()).read_text(encoding="utf-8"))
            assert saved["notes"] == {
                "summary": "Oppsummert funn",
                "biomarkerContext": "TMB og MSI vurdert",
                "additional": "Drøftes i MDT",
                "importedLegacyNote": "",
            }
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_board_findings_follow_review_changes_and_keep_duplicate_variant_once(browser):
    report = build_report()
    review = validate_review_state(review_document(report, report.variants[2]["variantId"]), report=report)
    html = render_html(report, review, inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            page.get_by_role("tab", name="Molekylært tumorboard").click()
            assert page.locator("#board-findings li").count() == 1
            page.get_by_role("tab", name="Variantgjennomgang").click()
            tert = review.variant_reviews[0]["variantId"]
            page.locator(f'select[data-variant-id="{tert}"][data-review-field="reportingDecision"]').first.select_option("EXCLUDE")
            page.get_by_role("tab", name="Molekylært tumorboard").click()
            assert page.locator("#board-findings li").count() == 0
            assert page.get_by_text("Ingen funn er markert for rapportering.").is_visible()
            page.get_by_role("tab", name="Variantgjennomgang").click()
            page.locator('select[data-review-field="reportingDecision"]').first.select_option("INCLUDE")
            page.get_by_role("tab", name="Molekylært tumorboard").click()
            assert page.locator("#board-findings li").count() == 1
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_generated_mdt_print_contains_only_current_included_reviewed_findings(browser):
    report = build_report()
    review = validate_review_state(review_document(report, report.variants[2]["variantId"]), report=report)
    html = render_html(report, review, inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.add_init_script("window.print = () => { window.__printCalls = (window.__printCalls || 0) + 1; }")
            page.set_default_timeout(3000)
            page.goto(url)
            page.get_by_role("tab", name="Variantgjennomgang").click()
            tert = review.variant_reviews[0]["variantId"]
            page.locator(f'select[data-variant-id="{tert}"][data-review-field="reportingDecision"]').first.select_option("EXCLUDE")
            page.locator('select[data-review-field="reportingDecision"]').first.select_option("INCLUDE")
            page.locator('textarea[data-review-field="comment"]').first.fill("Kontrollert i IGV")
            page.get_by_role("tab", name="Molekylært tumorboard").click()
            page.get_by_label("Interpretation summary").fill("Diskuteres i møte")
            page.get_by_role("button", name="Generer MDT-utskrift").click()
            assert page.evaluate("window.__printCalls") == 1
            assert page.locator("body").get_attribute("class") == "print-mdt"
            page.emulate_media(media="print")
            pdf = page.pdf(prefer_css_page_size=True)
            pages = pypdf.PdfReader(BytesIO(pdf)).pages
            assert float(pages[0].mediabox.width) > float(pages[0].mediabox.height)
            printed = "\n".join(item.extract_text() or "" for item in pages)
            assert "CHEK2" in printed
            assert "TERT" not in printed
            assert "Diskuteres i møte" in printed
            assert "Kontrollert i IGV" in printed
            assert "ikke signert" in printed.lower()
            assert "Variantgjennomgang" not in printed
            page.evaluate("window.dispatchEvent(new Event('afterprint'))")
            assert page.locator("body").get_attribute("class") == ""
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()
