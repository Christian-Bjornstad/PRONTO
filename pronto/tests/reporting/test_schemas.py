import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


SCHEMA_DIR = Path(__file__).parents[3] / "pronto_report" / "schemas"


def load_schema(name):
    with (SCHEMA_DIR / name).open(encoding="utf-8") as schema_file:
        return json.load(schema_file)


def report_data():
    return {
        "schemaVersion": "1.0",
        "reportId": "report_01HXYZ",
        "sample": {
            "sampleId": "SAMPLE-001",
            "patientPseudonym": "CASE-001",
            "referenceBuild": "GRCh38",
        },
        "run": {"runId": "RUN-001"},
        "provenance": {
            "generatedAt": "2026-09-22T12:00:00Z",
            "generator": {"name": "PRONTO", "version": "3.0.0"},
            "sourceFiles": [
                {
                    "name": "small_variant_table.tsv",
                    "sha256": "a" * 64,
                    "mediaType": "text/tab-separated-values",
                }
            ],
        },
        "biomarkers": [],
        "qcMetrics": [],
        "variants": [],
        "attachments": [],
        "diagnostics": [],
    }


@pytest.fixture
def report_validator():
    schema = load_schema("report-data-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_report_data_schema_accepts_minimal_valid_document(report_validator):
    report_validator.validate(report_data())


@pytest.mark.parametrize("schema_version", ["2.0", "v1", 1])
def test_report_data_schema_rejects_unsupported_schema_version(
    report_validator, schema_version
):
    document = report_data()
    document["schemaVersion"] = schema_version

    with pytest.raises(ValidationError):
        report_validator.validate(document)


def test_report_data_schema_rejects_unknown_properties(report_validator):
    document = report_data()
    document["unexpected"] = "value"

    with pytest.raises(ValidationError):
        report_validator.validate(document)


@pytest.mark.parametrize(
    ("field", "limit"),
    [("variants", 10_000), ("attachments", 100), ("diagnostics", 1_000)],
)
def test_report_data_schema_rejects_oversized_collections(
    report_validator, field, limit
):
    document = report_data()
    document[field] = [{}] * (limit + 1)

    with pytest.raises(ValidationError):
        report_validator.validate(document)


def test_report_data_schema_rejects_invalid_timestamp(report_validator):
    document = copy.deepcopy(report_data())
    document["provenance"]["generatedAt"] = "today"

    with pytest.raises(ValidationError):
        report_validator.validate(document)


def review_state():
    return {
        "schemaVersion": "1.0",
        "reportId": "report_01HXYZ",
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


@pytest.fixture
def review_validator():
    schema = load_schema("review-state-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_review_state_schema_accepts_minimal_draft(review_validator):
    review_validator.validate(review_state())


def test_review_state_keeps_decision_and_classification_independent(review_validator):
    document = review_state()
    document["variantReviews"] = [
        {
            "variantId": "variant-001",
            "reportingDecision": "INCLUDE",
            "clinicalClassification": "UNCERTAIN",
            "igvAssessment": "SUPPORTS",
        },
        {
            "variantId": "variant-002",
            "reportingDecision": "EXCLUDE",
            "clinicalClassification": "PATHOGENIC",
            "igvAssessment": "DOES_NOT_SUPPORT",
        },
    ]

    review_validator.validate(document)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reportingDecision", "PATHOGENIC"),
        ("clinicalClassification", "INCLUDE"),
        ("igvAssessment", "YES"),
    ],
)
def test_review_state_rejects_unknown_review_enum(review_validator, field, value):
    document = review_state()
    variant_review = {
        "variantId": "variant-001",
        "reportingDecision": "UNREVIEWED",
        "clinicalClassification": "UNCLASSIFIED",
        "igvAssessment": "NOT_REVIEWED",
    }
    variant_review[field] = value
    document["variantReviews"] = [variant_review]

    with pytest.raises(ValidationError):
        review_validator.validate(document)


def test_final_review_state_requires_finalization_provenance(review_validator):
    document = review_state()
    document["status"] = "FINAL"

    with pytest.raises(ValidationError):
        review_validator.validate(document)

    document["finalizedAt"] = "2026-09-22T13:00:00Z"
    document["finalizedBy"] = "reviewer-001"
    review_validator.validate(document)


@pytest.mark.parametrize("schema_version", ["2.0", "v1", 1])
def test_review_state_rejects_unsupported_schema_version(
    review_validator, schema_version
):
    document = review_state()
    document["schemaVersion"] = schema_version

    with pytest.raises(ValidationError):
        review_validator.validate(document)


@pytest.mark.parametrize(
    ("field", "limit"), [("variantReviews", 10_000), ("valueCorrections", 1_000)]
)
def test_review_state_rejects_oversized_collections(review_validator, field, limit):
    document = review_state()
    document[field] = [{}] * (limit + 1)

    with pytest.raises(ValidationError):
        review_validator.validate(document)


def test_review_state_rejects_unknown_properties(review_validator):
    document = review_state()
    document["patientName"] = "Must not be added"

    with pytest.raises(ValidationError):
        review_validator.validate(document)
