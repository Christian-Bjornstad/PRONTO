from dataclasses import FrozenInstanceError

import pytest

from pronto_report.models import ReportData, ReviewState


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
        "variantReviews": [
            {
                "variantId": "variant-001",
                "reportingDecision": "INCLUDE",
                "clinicalClassification": "UNCERTAIN",
                "igvAssessment": "SUPPORTS",
            }
        ],
        "runQcAssessment": {"status": "NOT_REVIEWED"},
        "reportNotes": "",
        "valueCorrections": [],
    }


def test_report_data_is_an_immutable_snapshot():
    source = report_document()
    report = ReportData.from_validated(source)

    source["sample"]["sampleId"] = "changed-after-construction"

    assert report.schema_version == "1.0"
    assert report.report_id == "report-001"
    assert report.sample["sampleId"] == "sample-001"
    with pytest.raises(TypeError):
        report.sample["sampleId"] = "cannot-mutate"
    with pytest.raises(FrozenInstanceError):
        report.report_id = "cannot-mutate"


def test_report_data_freezes_nested_arrays_and_objects():
    source = report_document()
    source["diagnostics"] = [
        {
            "severity": "WARNING",
            "code": "MISSING_VALUE",
            "path": "biomarkers",
            "message": "Value was not supplied",
        }
    ]

    report = ReportData.from_validated(source)

    assert isinstance(report.diagnostics, tuple)
    with pytest.raises(TypeError):
        report.diagnostics[0]["message"] = "cannot-mutate"


def test_review_state_is_separate_and_keeps_review_dimensions_independent():
    review = ReviewState.from_validated(review_document())
    variant_review = review.variant_reviews[0]

    assert review.report_id == "report-001"
    assert review.revision == 1
    assert review.status == "DRAFT"
    assert variant_review["reportingDecision"] == "INCLUDE"
    assert variant_review["clinicalClassification"] == "UNCERTAIN"
    with pytest.raises(TypeError):
        variant_review["reportingDecision"] = "EXCLUDE"
