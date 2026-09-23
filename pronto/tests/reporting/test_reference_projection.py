"""The reference-style UI may show only validated, traceable facts."""

import copy

import pytest

from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.projection import project_reference_ui
from pronto_report.serialization import serialize_report_data
from pronto_report.validation import (
    ContractValidationError, validate_report_data, validate_review_state,
)
import json


def review_document(report, variant_id):
    return {
        "schemaVersion": "2.0",
        "reportId": report.report_id,
        "revision": 2,
        "status": "DRAFT",
        "reviewer": {"reviewerId": "biologist-001"},
        "createdAt": "2026-09-22T12:00:00Z",
        "updatedAt": "2026-09-23T09:00:00Z",
        "variantReviews": [{
            "variantId": variant_id,
            "reportingDecision": "INCLUDE",
            "clinicalClassification": "UNCERTAIN",
            "igvAssessment": "SUPPORTS",
        }],
        "runQcAssessment": {"status": "NOT_REVIEWED"},
        "notes": {
            "summary": "Kort oppsummering",
            "biomarkerContext": "TMB vurdert",
            "additional": "",
            "importedLegacyNote": "",
        },
        "valueCorrections": [{
            "path": "/sample/tumourType",
            "originalValue": None,
            "correctedValue": "Lunge",
            "reason": "Bekreftet fra rekvisisjon",
            "author": "biologist-001",
            "timestamp": "2026-09-23T09:00:00Z",
        }],
    }


def test_projection_marks_missing_reference_fields_unavailable():
    report = build_report()

    ui = project_reference_ui(report)

    assert ui["reportId"] == report.report_id
    assert ui["facts"]["sampleId"]["value"] == report.sample["sampleId"]
    assert ui["facts"]["sampleId"]["source"]["kind"] == "REPORT_PROVENANCE"
    for name in ("tumourType", "specimenType", "patientAge", "tumourContent"):
        assert ui["facts"][name] == {
            "value": None, "availability": "UNAVAILABLE", "source": None
        }
    assert ui["biomarkers"]["localapp_tmb"]["availability"] == "UNAVAILABLE"
    assert ui["qcMetrics"] == []


def test_projected_biomarkers_retain_values_units_and_raw_source():
    ui = project_reference_ui(build_report())

    assert ui["biomarkers"]["tmb"]["value"] == 14.9
    assert ui["biomarkers"]["tmb"]["unit"] == "mut/Mb"
    assert ui["biomarkers"]["tmb"]["source"]["rawValue"] == "14.9 (19)"
    assert ui["biomarkers"]["msi"]["source"]["rawValue"] == "4.13 (5/121)"


def test_duplicate_occurrences_remain_rows_with_one_shared_review():
    report = build_report()
    tert = [variant for variant in report.variants if variant.get("gene") == "TERT"]
    review = validate_review_state(review_document(report, tert[0]["variantId"]), report=report)

    ui = project_reference_ui(report, review)
    rows = [row for row in ui["variants"] if row["fields"]["gene"]["value"] == "TERT"]

    assert len(ui["variants"]) == 30
    assert len(rows) == 2
    assert rows[0]["occurrenceId"] != rows[1]["occurrenceId"]
    assert rows[0]["variantId"] == rows[1]["variantId"]
    assert rows[0]["review"] == rows[1]["review"]
    assert rows[0]["review"]["reportingDecision"] == "INCLUDE"
    assert rows[0]["review"]["clinicalClassification"] == "UNCERTAIN"
    assert rows[0]["fields"]["gene"]["source"]["fileName"]


def test_corrections_do_not_overwrite_source_facts():
    report = build_report()
    document = review_document(report, report.variants[0]["variantId"])
    review = validate_review_state(document, report=report)

    ui = project_reference_ui(report, review)

    assert ui["facts"]["tumourType"]["availability"] == "UNAVAILABLE"
    assert ui["corrections"] == document["valueCorrections"]
    assert ui["notes"] == document["notes"]
    assert ui["review"]["revision"] == 2
    ui["corrections"][0]["correctedValue"] = "Changed locally"
    assert review.value_corrections[0]["correctedValue"] == "Lunge"


def test_duplicate_metric_ids_fail_instead_of_silently_dropping_a_value():
    document = json.loads(serialize_report_data(build_report()))
    document["biomarkers"].append(copy.deepcopy(document["biomarkers"][0]))

    with pytest.raises(ValueError, match="Duplicate biomarker metricId"):
        project_reference_ui(validate_report_data(document))


def test_annotation_named_like_a_core_field_cannot_overwrite_it():
    document = json.loads(serialize_report_data(build_report()))
    document["variants"][0]["annotations"].append({"key": "gene", "value": "not-the-gene"})
    variant = document["variants"][0]

    ui = project_reference_ui(validate_report_data(document))
    projected = ui["variants"][0]

    assert projected["fields"]["gene"]["value"] == variant["gene"]
    assert {entry["key"]: entry["fact"]["value"] for entry in projected["annotations"]}["gene"] == "not-the-gene"


def test_legacy_review_note_is_visible_only_as_imported_text():
    report = build_report()
    document = review_document(report, report.variants[0]["variantId"])
    document["schemaVersion"] = "1.0"
    del document["notes"]
    document["reportNotes"] = "Ufordelt eldre notat"

    ui = project_reference_ui(report, validate_review_state(document, report=report))

    assert ui["notes"] == {
        "summary": "",
        "biomarkerContext": "",
        "additional": "",
        "importedLegacyNote": "Ufordelt eldre notat",
    }
    assert json.loads(json.dumps(ui))["notes"] == ui["notes"]


def test_projection_rejects_review_for_an_unknown_variant():
    report = build_report()
    document = review_document(report, "unknown-variant")

    with pytest.raises(ValueError, match="unknown variantId"):
        project_reference_ui(report, validate_review_state(document, report=report))


@pytest.mark.parametrize("missing", ["reason", "author", "timestamp"])
def test_correction_audit_fields_are_required_at_validation_boundary(missing):
    report = build_report()
    document = review_document(report, report.variants[0]["variantId"])
    broken = copy.deepcopy(document)
    del broken["valueCorrections"][0][missing]

    with pytest.raises(ContractValidationError) as caught:
        validate_review_state(broken, report=report)

    assert f"valueCorrections[0].{missing}" in {issue.path for issue in caught.value.issues}
