import json
from pathlib import Path

from pronto.tests.reporting.browser.test_report import _page, _serve, browser
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html


def test_selection_and_qc_are_preserved_in_download(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            assert page.locator('#panel-variant-review').is_visible()
            row = page.locator('#variant-table tbody tr').first
            row.locator('[data-include-variant]').click()
            assert row.locator('[data-include-variant]').get_attribute('aria-pressed') == 'true'
            assert row.locator('[data-review-field="clinicalClassification"]').input_value() == 'UNCLASSIFIED'
            page.get_by_role('tab', name='Molekylært tumorboard').click()
            assert 'CHEK2' in page.locator('#board-findings').inner_text()
            page.get_by_role('tab', name='Sekvenserings-QC').click()
            page.locator('#qc-review-status').select_option('CONDITIONAL')
            page.locator('#qc-review-comment').fill('Demo: kontroller dybde.')
            page.get_by_role('tab', name='Variantgjennomgang').click()
            with page.expect_download() as pending:
                page.get_by_role('button', name='Last ned ReviewState').click()
            saved = json.loads(Path(pending.value.path()).read_text(encoding='utf-8'))
            assert saved['runQcAssessment'] == {'status': 'CONDITIONAL', 'comment': 'Demo: kontroller dybde.'}
            assert any(v['variantId'] == report.variants[0]['variantId'] and v['reportingDecision'] == 'INCLUDE' for v in saved['variantReviews'])
            assert diagnostics == []
        finally:
            context.close()
