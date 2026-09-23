import json

import pytest

from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html
from pronto_report.validation import ContractValidationError, validate_review_state


def draft_review(report):
    variant_id = report.variants[2]["variantId"]
    return validate_review_state(
        {
            "schemaVersion": "1.0",
            "reportId": report.report_id,
            "revision": 1,
            "status": "DRAFT",
            "reviewer": {"reviewerId": "reviewer-001"},
            "createdAt": "2026-09-22T12:00:00Z",
            "updatedAt": "2026-09-22T12:00:00Z",
            "variantReviews": [
                {
                    "variantId": variant_id,
                    "reportingDecision": "EXCLUDE",
                    "clinicalClassification": "PATHOGENIC",
                    "igvAssessment": "NOT_REVIEWED",
                }
            ],
            "runQcAssessment": {"status": "NOT_REVIEWED"},
            "reportNotes": "",
            "valueCorrections": [],
        },
        report=report,
    )


def test_draft_review_keeps_decision_and_classification_independent():
    report = build_report()
    html = render_html(report, draft_review(report))

    assert 'data-variant-id="' + report.variants[2]["variantId"] + '"' in html
    assert '<option value="EXCLUDE" selected>' in html
    assert '<option value="PATHOGENIC" selected>' in html
    assert 'id="review-state-data"' in html
    assert "Last ned ReviewState" in html


def test_final_review_locks_controls_and_shows_finalization_provenance():
    report = build_report()
    document = json.loads(json.dumps({
        "schemaVersion": "1.0", "reportId": report.report_id,
        "revision": 2, "status": "FINAL",
        "reviewer": {"reviewerId": "reviewer-001"},
        "createdAt": "2026-09-22T12:00:00Z", "updatedAt": "2026-09-22T13:00:00Z",
        "finalizedAt": "2026-09-22T13:00:00Z", "finalizedBy": "reviewer-002",
        "variantReviews": [], "runQcAssessment": {"status": "PASS"},
        "reportNotes": "", "valueCorrections": [],
    }))
    review = validate_review_state(document, report=report)

    html = render_html(report, review)
    assert "Rapportstatus: Endelig" in html
    assert "Ferdigstilt av reviewer-002" in html
    assert 'data-review-field="reportingDecision" disabled' in html
    assert 'data-review-field="clinicalClassification" disabled' in html


def test_review_for_another_report_is_rejected_before_rendering():
    report = build_report()
    document = {
        "schemaVersion": "1.0", "reportId": "other-report", "revision": 1,
        "status": "DRAFT", "reviewer": {"reviewerId": "reviewer-001"},
        "createdAt": "2026-09-22T12:00:00Z", "updatedAt": "2026-09-22T12:00:00Z",
        "variantReviews": [], "runQcAssessment": {"status": "NOT_REVIEWED"},
        "reportNotes": "", "valueCorrections": [],
    }

    with pytest.raises(ContractValidationError) as error:
        validate_review_state(document, report=report)
    assert error.value.issues[0].code == "MISMATCHED_REPORT_ID"


def test_review_text_cannot_close_embedded_json_script():
    report = build_report()
    review = draft_review(report)
    payload = json.loads(json.dumps({
        "schemaVersion": review.schema_version, "reportId": review.report_id,
        "revision": review.revision, "status": review.status,
        "reviewer": {"reviewerId": "reviewer-001"},
        "createdAt": review.created_at, "updatedAt": review.updated_at,
        "variantReviews": [], "runQcAssessment": {"status": "NOT_REVIEWED"},
        "reportNotes": "</script><script>alert(1)</script>", "valueCorrections": [],
    }))
    html = render_html(report, validate_review_state(payload, report=report))

    assert "</script><script>alert(1)</script>" not in html
    assert r"\u003c/script\u003e" in html
