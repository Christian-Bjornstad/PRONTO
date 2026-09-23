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
    assert 'id="edit-btn" type="button" aria-pressed="false"' in html
    assert 'class="tmb-gauge report-edit-controls" hidden' in html


def test_draft_patient_context_fields_are_editable_corrections():
    report = build_report()
    html = render_html(report, draft_review(report))

    assert 'data-correction-path="/sample/tumourType"' in html
    assert 'data-correction-path="/sample/specimenType"' in html
    assert 'data-source-value="Ikke oppgitt"' in html
    assert 'id="tumourType-correction-reason"' in html


def test_msi_kpi_is_editable_only_as_a_traced_correction():
    report = build_report()
    html = render_html(report, draft_review(report))

    assert 'id="msi-edit-value"' in html
    assert 'id="msi-correction-reason"' in html
    assert 'data-metric-correction-path="/biomarkers/' in html
    assert 'data-metric="localapp_tmb" data-availability="UNAVAILABLE"' in html


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
