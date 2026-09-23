"""Traceable, JSON-ready facts for the reference-style report interface."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pronto_report.migration import migrate_review_state_v1
from pronto_report.models import ReportData, ReviewState


def _copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _copy(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy(item) for item in value]
    return value


def _fact(value: Any, source: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None or value == "":
        return {"value": None, "availability": "UNAVAILABLE", "source": None}
    return {"value": _copy(value), "availability": "AVAILABLE", "source": _copy(source)}


def _global_source(report: ReportData) -> dict[str, Any]:
    return {
        "kind": "REPORT_PROVENANCE",
        "generatedAt": report.provenance["generatedAt"],
        "sourceFiles": _copy(report.provenance["sourceFiles"]),
    }


def _facts(report: ReportData) -> dict[str, dict[str, Any]]:
    source = _global_source(report)
    fields = {
        "sampleId": report.sample.get("sampleId"),
        "patientPseudonym": report.sample.get("patientPseudonym"),
        "referenceBuild": report.sample.get("referenceBuild"),
        "tumourType": report.sample.get("tumourType"),
        "specimenType": report.sample.get("specimenType"),
        "runId": report.run.get("runId"),
        "assay": report.run.get("assay"),
        "instrument": report.run.get("instrument"),
        "patientAge": None,
        "tumourContent": None,
        "sampleMaterial": None,
        "requisitionHospital": None,
        "extractionHospital": None,
        "batch": None,
        "pipeline": None,
    }
    return {name: _fact(value, source) for name, value in fields.items()}


def _measurement(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "metricId": item["metricId"],
        "label": item["label"],
        "unit": item.get("unit", ""),
        **_fact(item["value"], item["source"]),
        "status": item.get("status"),
        "thresholds": _copy(item.get("thresholds", ())),
    }


def _variant_fields(variant: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    names = (
        "gene", "genomicLocation", "dnaChange", "proteinChange",
        "alleleFrequency", "chromosome", "position", "reference", "alternate",
    )
    return {name: _fact(variant.get(name), variant["source"]) for name in names}


def project_reference_ui(
    report: ReportData, review: ReviewState | None = None
) -> dict[str, Any]:
    """Project validated snapshots without modifying source facts or decisions."""
    if review is not None and review.report_id != report.report_id:
        raise ValueError("Review state does not belong to this report")
    if review is not None and review.schema_version == "1.0":
        review = migrate_review_state_v1(review)

    biomarker_cards = {}
    for item in report.biomarkers:
        metric_id = str(item["metricId"])
        if metric_id in biomarker_cards:
            raise ValueError(f"Duplicate biomarker metricId: {metric_id}")
        biomarker_cards[metric_id] = _measurement(item)
    biomarker_cards.setdefault("tmb", _fact(None, None))
    biomarker_cards.setdefault("msi", _fact(None, None))
    biomarker_cards.setdefault("localapp_tmb", _fact(None, None))
    known_variants = {variant["variantId"] for variant in report.variants}
    reviews = {}
    if review is not None:
        for item in review.variant_reviews:
            variant_id = item["variantId"]
            if variant_id not in known_variants:
                raise ValueError(f"Review references unknown variantId: {variant_id}")
            if variant_id in reviews:
                raise ValueError(f"Duplicate variant review for variantId: {variant_id}")
            reviews[variant_id] = item
    variants = [
        {
            "variantId": variant["variantId"],
            "occurrenceId": variant["occurrenceId"],
            "fields": _variant_fields(variant),
            "annotations": [
                {
                    "key": annotation["key"],
                    "fact": _fact(
                        annotation["value"],
                        annotation.get("source", variant["source"]),
                    ),
                }
                for annotation in variant["annotations"]
            ],
            "review": _copy(reviews.get(variant["variantId"])),
        }
        for variant in report.variants
    ]
    return {
        "reportId": report.report_id,
        "facts": _facts(report),
        "biomarkers": biomarker_cards,
        "qcMetrics": [_measurement(item) for item in report.qc_metrics],
        "variants": variants,
        "attachments": _copy(report.attachments),
        "provenance": _copy(report.provenance),
        "review": {
            "revision": review.revision,
            "status": review.status,
            "reviewer": _copy(review.reviewer),
            "runQcAssessment": _copy(review.run_qc_assessment),
            "finalizedAt": review.finalized_at,
            "finalizedBy": review.finalized_by,
        } if review else None,
        "notes": _copy(review.notes) if review else None,
        "corrections": _copy(review.value_corrections) if review else [],
    }
