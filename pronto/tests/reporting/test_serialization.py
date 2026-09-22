import json

import pytest

import pronto_report.serialization as serialization_module
from pronto_report.serialization import (
    deserialize_report_data,
    deserialize_review_state,
    serialize_report_data,
    serialize_review_state,
)
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
            "tumourType": "Lunge – øvre lapp",
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
        "reportNotes": "Vurdert uten merknad",
        "valueCorrections": [],
    }


def test_report_data_serialization_is_byte_stable():
    report = validate_report_data(report_document())

    first = serialize_report_data(report)
    second = serialize_report_data(report)

    assert first == second
    assert first.endswith(b"\n")
    assert first.startswith(b'{"attachments":')


def test_report_data_round_trip_preserves_unicode_and_values():
    report = validate_report_data(report_document())

    restored = deserialize_report_data(serialize_report_data(report))

    assert restored == report
    assert restored.sample["tumourType"] == "Lunge – øvre lapp"


def test_review_state_round_trip_preserves_values_and_report_binding():
    report = validate_report_data(report_document())
    original = validate_review_state(review_document(), report=report)

    review = deserialize_review_state(serialize_review_state(original), report=report)

    assert review.report_id == report.report_id
    assert review.report_notes == "Vurdert uten merknad"


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b'{"schemaVersion":"1.0","schemaVersion":"1.0"}',
        b'{"value":NaN}',
        b'{"value":1e999}',
        b"\xff",
    ],
)
def test_invalid_json_is_rejected_with_safe_structured_error(payload):
    with pytest.raises(ContractValidationError) as caught:
        deserialize_report_data(payload)

    assert caught.value.code == "INVALID_REPORT_DATA"
    assert caught.value.issues[0].code in {"INVALID_JSON", "DUPLICATE_FIELD"}
    decoded_payload = payload.decode("utf-8", errors="ignore")
    if decoded_payload:
        assert decoded_payload not in str(caught.value.as_dict())


def test_oversized_json_is_rejected_before_parsing(monkeypatch):
    monkeypatch.setattr(serialization_module, "MAX_JSON_BYTES", 16)

    with pytest.raises(ContractValidationError) as caught:
        deserialize_report_data(b" " * 17)

    assert caught.value.issues[0].code == "DOCUMENT_TOO_LARGE"


def test_schema_invalid_json_never_returns_a_model():
    payload = json.dumps(
        {**report_document(), "schemaVersion": "2.0"}
    ).encode("utf-8")

    with pytest.raises(ContractValidationError) as caught:
        deserialize_report_data(payload)

    assert caught.value.issues[0].code == "UNSUPPORTED_SCHEMA_VERSION"
