import json

from pronto_report.serialization import serialize_report_data, serialize_review_state
from pronto_report.validation import validate_review_state
from pronto_web.reports.synthetic_data import build_synthetic_case


def test_generated_copy_is_cleaned_without_rewriting_source_or_manual_notes():
    from pronto_report.renderers.display_copy import presentation_copy

    case = build_synthetic_case(4, seed=20261001)
    original_report = serialize_report_data(case.report)
    original_review = serialize_review_state(case.prepared_review)
    report, review = presentation_copy(case.report, case.prepared_review)
    assert report.sample['tumourType'] == 'Ovarian carcinoma'
    assert review.notes['summary'].endswith('RNA events.')
    assert not review.notes['clinicalEvidence']
    assert report.provenance == case.report.provenance
    assert report.source_tables == case.report.source_tables
    assert report.diagnostics == case.report.diagnostics
    assert serialize_report_data(case.report) == original_report
    assert serialize_review_state(case.prepared_review) == original_review

    document = json.loads(original_review)
    document['notes']['summary'] = 'Demo mentioned in a manually written note.'
    document['notes']['clinicalEvidence'] = 'Reviewed evidence, keep exactly.'
    document['notes']['additional'] += '\nSimulated second save: version history demonstration.'
    manual = validate_review_state(document, report=case.report)
    _, cleaned = presentation_copy(case.report, manual)
    assert cleaned.notes['summary'] == document['notes']['summary']
    assert cleaned.notes['clinicalEvidence'] == document['notes']['clinicalEvidence']
    assert cleaned.notes['additional'] == ''


def test_non_generated_reports_and_reviews_are_not_reworded():
    from pronto_report.renderers.display_copy import presentation_copy
    from pronto.tests.reporting.test_pronto_output_adapter import build_report
    from pronto.tests.reporting.test_html_review_state import draft_review

    report = build_report()
    review = draft_review(report)
    assert presentation_copy(report, review) == (report, review)


def test_clean_ui_preserves_exact_original_value_for_patient_corrections():
    from pronto_report.renderers.html import render_html
    case = build_synthetic_case(4, seed=20261001)
    html = render_html(case.report, case.prepared_review, save_url='/save/', csrf_token='token', actor_id='reviewer')
    assert 'data-original-value="Ovarian carcinoma (synthetic demo)"' in html
    assert 'value="Ovarian carcinoma (synthetic demo)"' in html
    assert '<dd>Ovarian carcinoma</dd>' in html
