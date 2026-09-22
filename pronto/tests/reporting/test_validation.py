import json

import pytest

from pronto_report.models import ReportData, ReviewState
from pronto_report.validation import (
    ContractValidationError,
    validate_report_data,
    validate_review_state,
)


def report_document():
    return {
        "schemaVersion": "1.0",
        "reportId": "report-001",
        "sample": {
            "sampleId": "sample-001",
            "patientPseudonym": "case-001",
            "referenceBuild": "GRCh38",
        },
        "run": {"runId": "run-001"},
        "provenance": {
            "generatedAt": "2026-09-22T12:00:00Z",
            "generator": {"name": "PRONTO", "version": "3.0.0"},
            "sourceFiles": [{"name": "source.tsv", "sha256": "a" * 64}],
        },
        "biomarkers": [],
        "qcMetrics": [],
        "variants": [],
        "attachments": [],
        "diagnostics": [],
    }


def review_document():
    return {
        "schemaVersion": "1.0",
        "reportId": "report-001",
        "revision": 1,
        "status": "DRAFT",
        "reviewer": {"reviewerId": "reviewer-001"},
        "createdAt": "2026-09-22T12:00:00Z",
        "updatedAt": "2026-09-22T12:00:00Z",
        "variantReviews": [],
        "runQcAssessment": {"status": "NOT_REVIEWED"},
        "reportNotes": "",
        "valueCorrections": [],
    }


def test_validate_report_data_returns_typed_snapshot():
    report = validate_report_data(report_document())

    assert isinstance(report, ReportData)
    assert report.report_id == "report-001"


def test_validate_report_data_returns_stable_required_field_issue():
    document = report_document()
    del document["sample"]["sampleId"]

    with pytest.raises(ContractValidationError) as caught:
        validate_report_data(document)

    assert caught.value.as_dict() == {
        "code": "INVALID_REPORT_DATA",
        "message": "Report data did not pass validation",
        "issues": [
            {
                "path": "sample.sampleId",
                "code": "REQUIRED_FIELD",
                "message": "Required field is missing",
            }
        ],
    }


def test_validate_report_data_identifies_unsupported_version():
    document = report_document()
    document["schemaVersion"] = "2.0"

    with pytest.raises(ContractValidationError) as caught:
        validate_report_data(document)

    assert caught.value.issues[0].path == "schemaVersion"
    assert caught.value.issues[0].code == "UNSUPPORTED_SCHEMA_VERSION"


def test_validation_error_does_not_echo_input_values():
    document = report_document()
    document["reportId"] = "TOP_SECRET_PATIENT_VALUE/../../"

    with pytest.raises(ContractValidationError) as caught:
        validate_report_data(document)

    serialized_error = json.dumps(caught.value.as_dict())
    assert "TOP_SECRET_PATIENT_VALUE" not in serialized_error
    assert str(caught.value) == "Report data did not pass validation"


def test_validate_review_state_returns_typed_snapshot_for_matching_report():
    report = validate_report_data(report_document())
    review = validate_review_state(review_document(), report=report)

    assert isinstance(review, ReviewState)
    assert review.report_id == report.report_id


def test_validate_review_state_rejects_mismatched_report_id_without_echoing_ids():
    report = validate_report_data(report_document())
    document = review_document()
    document["reportId"] = "different-report"

    with pytest.raises(ContractValidationError) as caught:
        validate_review_state(document, report=report)

    assert caught.value.as_dict() == {
        "code": "INVALID_REVIEW_STATE",
        "message": "Review state did not pass validation",
        "issues": [
            {
                "path": "reportId",
                "code": "MISMATCHED_REPORT_ID",
                "message": "Review state belongs to a different report",
            }
        ],
    }
    assert "different-report" not in json.dumps(caught.value.as_dict())


def test_validate_review_state_reports_invalid_type_safely():
    document = review_document()
    document["revision"] = "TOP_SECRET_PATIENT_VALUE"

    with pytest.raises(ContractValidationError) as caught:
        validate_review_state(document)

    assert caught.value.issues[0].path == "revision"
    assert caught.value.issues[0].code == "INVALID_TYPE"
    assert "TOP_SECRET_PATIENT_VALUE" not in json.dumps(caught.value.as_dict())
