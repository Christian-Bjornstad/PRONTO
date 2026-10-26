from dataclasses import replace
from types import MappingProxyType

from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.review_v3 import cnv_plots


def test_long_cnv_pdf_is_one_document_with_numbered_page_selection():
    asset = MappingProxyType({'assetId':'long-pdf','name':'SYN_CNV_overview_plots.pdf','description':'CNV'})
    report = replace(build_report(), attachments=(asset,))
    pages = tuple(('image/jpeg', b'test') for _ in range(55))
    html = cnv_plots(report, {'long-pdf':pages})
    assert html.count('data-v3-plot=') == 1
    assert 'data-plot-page-select' in html
    assert 'Page 55 of 55' in html
    assert html.count('class="plot-document-page"') == 55
    assert 'data-plot-step="-1"' in html and 'data-plot-step="1"' in html


def test_nine_panel_cnv_keeps_existing_named_groups():
    asset = MappingProxyType({'assetId':'nine','name':'SYN_CNV_overview_plots.pdf','description':'CNV'})
    report = replace(build_report(), attachments=(asset,))
    html = cnv_plots(report, {'nine':tuple(('image/jpeg', b'test') for _ in range(9))})
    assert 'B3 / C1' in html and 'cnv-panel-B3' in html and 'cnv-panel-C1' in html
    assert 'data-plot-page-select' not in html
