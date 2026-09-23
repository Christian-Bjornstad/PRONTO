"""TMB edits are local corrections, never mutations of ReportData."""

from dataclasses import replace

from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html


def test_draft_has_reference_style_tmb_gauge_and_reason_field():
    report = build_report()
    html = render_html(report, draft_review(report))

    assert 'id="tmb-gauge"' in html
    assert 'id="tmb-edit-value"' in html
    assert 'id="tmb-correction-reason"' in html
    assert 'data-original-value="14.9"' in html


def test_read_only_report_has_no_tmb_edit_controls():
    html = render_html(build_report())

    assert 'id="tmb-gauge"' not in html
    assert 'id="tmb-edit-value"' not in html


def test_finalized_review_has_no_tmb_edit_controls():
    report = build_report()
    final = replace(
        draft_review(report), status="FINAL",
        finalized_at="2026-09-23T10:00:00Z", finalized_by="reviewer-001",
    )

    html = render_html(report, final)

    assert 'id="tmb-gauge"' not in html
    assert "14,9 mut/Mb" in html
