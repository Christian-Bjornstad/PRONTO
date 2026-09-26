from dataclasses import replace

from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html


def test_workspace_displays_depth_fixed_precision_and_pending_annotations():
    report = build_report()
    variant = dict(report.variants[0], alleleFrequency=0.06123456)
    report = replace(report, variants=(variant,))
    html = render_html(report)
    assert '<td>0,061</td>' in html
    assert 'data-vaf="0.06123456"' in html
    assert 'Dybde tumor DNA' in html
    assert 'OncoKB' in html
    assert 'Ikke mottatt' in html
    assert 'Ikke krysssjekket' in html


def test_draft_has_selection_buttons_and_escaped_qc_comment():
    report = build_report()
    review = replace(draft_review(report), run_qc_assessment={
        'status': 'CONDITIONAL', 'comment': '<script>not executable</script>',
    })
    html = render_html(report, review)
    assert 'data-include-variant=' in html
    assert 'Ta med i rapport' in html
    assert 'id="qc-review-comment"' in html
    assert '&lt;script&gt;not executable&lt;/script&gt;' in html
    assert '<option value="CONDITIONAL" selected>' in html
