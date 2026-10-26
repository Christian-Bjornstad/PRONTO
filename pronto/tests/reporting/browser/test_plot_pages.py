from dataclasses import replace

from pronto.tests.reporting.browser.test_report import _page, _serve, browser
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_html_surfaces import ONE_PIXEL_PNG
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.migration import migrate_review_state_to_v3
from pronto_report.renderers.html import render_html


def test_long_pdf_page_navigation_and_collapsed_signature(browser):
    report = build_report()
    cnv = dict(report.attachments[0], assetId='synthetic-cnv', name='SYN_CNV_overview_plots.pdf', description='CNV')
    signature = dict(cnv, assetId='synthetic-signature', name='SYN_joint_mutational_signature.pdf', description='Mutasjonssignatur')
    report = replace(report, attachments=(cnv, signature))
    review = migrate_review_state_to_v3(draft_review(report))
    html = render_html(report, review, inline_assets=True, plot_images={
        'synthetic-cnv':tuple(('image/png', ONE_PIXEL_PNG) for _ in range(55)),
        'synthetic-signature':(('image/png', ONE_PIXEL_PNG),)})
    with _serve(html) as url:
        context, page, errors, requests = _page(browser, html)
        try:
            page.goto(url)
            page.locator('#tab-key-findings').click()
            assert not page.locator('.signature-details img').is_visible()
            page.locator('.signature-details summary').click()
            assert page.locator('.signature-details img').is_visible()
            page.locator('#tab-cnv-plots').click()
            page.locator('[data-cnv-view="plots"]').click()
            assert page.locator('[data-v3-plot]').count() == 1
            assert page.locator('.plot-document-page:visible').count() == 1
            assert page.locator('[data-plot-step="-1"]').is_disabled()
            page.locator('[data-plot-step="1"]').click()
            assert page.locator('[data-plot-page-select]').input_value() == '1'
            page.locator('[data-plot-page-select]').select_option('54')
            assert page.locator('[data-plot-page="54"]').is_visible()
            assert page.locator('[data-plot-step="1"]').is_disabled()
            page.locator('[data-plot-step="-1"]').click()
            assert page.locator('[data-plot-page-select]').input_value() == '53'
            assert page.locator('.plot-document-page:visible').count() == 1
            assert errors == []
        finally:
            context.close()
