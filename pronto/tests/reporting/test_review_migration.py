"""Contract tests for the explicit, lossless ReviewState v1 to v2 migration."""

import json

import pytest

from pronto_report.migration import migrate_review_state_v1
from pronto_report.serialization import deserialize_review_state, serialize_review_state
from pronto_report.validation import ContractValidationError, validate_review_state


def legacy_document():
    return {
        "schemaVersion": "1.0",
        "reportId": "report-001",
        "revision": 3,
        "status": "DRAFT",
        "reviewer": {"reviewerId": "biologist-001", "displayName": "Biolog"},
        "createdAt": "2026-09-22T12:00:00Z",
        "updatedAt": "2026-09-23T09:00:00Z",
        "variantReviews": [{
            "variantId": "variant-001",
            "reportingDecision": "INCLUDE",
            "clinicalClassification": "UNCERTAIN",
            "igvAssessment": "SUPPORTS",
            "comment": "Kontrollert i IGV",
        }],
        "runQcAssessment": {"status": "CONDITIONAL", "comment": "Se dekning"},
        "reportNotes": "Eldre, ufordelt notat — behold ordrett.",
        "valueCorrections": [{
            "path": "/sample/tumourType",
            "originalValue": "Ukjent",
            "correctedValue": "Lunge",
            "reason": "Bekreftet i rekvisisjon",
            "author": "biologist-001",
            "timestamp": "2026-09-23T09:00:00Z",
        }],
    }


def v2_document():
    document = legacy_document()
    document["schemaVersion"] = "2.0"
    document["notes"] = {
        "summary": "Oppsummering",
        "biomarkerContext": "Biomarkører og terapi",
        "additional": "Andre kommentarer",
        "importedLegacyNote": "Eldre, ufordelt notat — behold ordrett.",
    }
    del document["reportNotes"]
    return document


def test_v2_notes_and_independent_variant_dimensions_round_trip():
    original = validate_review_state(v2_document())

    restored = deserialize_review_state(serialize_review_state(original))

    assert restored == original
    assert dict(restored.notes) == v2_document()["notes"]
    assert restored.variant_reviews[0]["reportingDecision"] == "INCLUDE"
    assert restored.variant_reviews[0]["clinicalClassification"] == "UNCERTAIN"
    assert "reportNotes" not in json.loads(serialize_review_state(restored))


def test_migration_keeps_legacy_text_labeled_and_all_other_review_data():
    legacy = validate_review_state(legacy_document())

    migrated = migrate_review_state_v1(legacy)
    output = json.loads(serialize_review_state(migrated))

    expected = v2_document()
    expected["notes"] = {
        "summary": "",
        "biomarkerContext": "",
        "additional": "",
        "importedLegacyNote": legacy_document()["reportNotes"],
    }
    assert output == expected
    assert deserialize_review_state(serialize_review_state(migrated)) == migrated
    assert json.loads(serialize_review_state(legacy)) == legacy_document()


def test_finalized_v1_review_migrates_without_losing_signoff():
    document = legacy_document()
    document.update({
        "status": "FINAL",
        "finalizedAt": "2026-09-23T10:00:00Z",
        "finalizedBy": "biologist-001",
    })

    migrated = migrate_review_state_v1(validate_review_state(document))

    assert migrated.status == "FINAL"
    assert migrated.finalized_at == document["finalizedAt"]
    assert migrated.finalized_by == document["finalizedBy"]


@pytest.mark.parametrize("change,expected_path", [
    ({"notes": {"summary": "only one"}}, "notes.biomarkerContext"),
    ({"notes": {**v2_document()["notes"], "unknown": "must not drop"}}, "notes.unknown"),
    ({"reportNotes": "must not drop"}, "reportNotes"),
])
def test_v2_rejects_missing_or_unknown_note_data(change, expected_path):
    document = v2_document()
    document.update(change)

    with pytest.raises(ContractValidationError) as caught:
        validate_review_state(document)

    assert expected_path in {issue.path for issue in caught.value.issues}


def test_migration_rejects_wrong_version():
    with pytest.raises(ValueError, match="v1"):
        migrate_review_state_v1(validate_review_state(v2_document()))
