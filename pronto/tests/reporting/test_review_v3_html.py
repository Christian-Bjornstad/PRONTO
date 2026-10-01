from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto_report.migration import migrate_review_state_to_v3
from pronto_report.renderers.html import render_html


def test_modern_workspace_has_linked_review_sections_and_full_source_table():
    report = build_report()
    html = render_html(report, migrate_review_state_to_v3(draft_review(report)), inline_assets=True)
    assert 'RNA review' in html
    assert 'data-section-qc="signatures"' in html
    assert 'data-vus-variant=' in html
    assert 'data-highlight-variant=' in html
    assert 'All source columns' in html
    assert 'QC_Verdict' not in html  # not invented when no RNA source exists
    assert 'Clinical trial context' in html
    assert 'data-metric="hrd" data-availability="UNAVAILABLE"' in html


def test_v3_modern_classes_are_exact_and_legacy_label_is_preserved():
    report=build_report()
    html=render_html(report,migrate_review_state_to_v3(draft_review(report)))
    assert '<option value="BENIGN"' in html
    assert '<option value="VUS"' in html
    assert '<option value="ONCOGENIC"' in html
    assert 'Legacy classification (read-only)' in html
