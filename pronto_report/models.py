"""Immutable in-process snapshots for validated PRONTO report contracts."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias, TypeVar, cast


JsonScalar: TypeAlias = str | int | float | bool | None
FrozenJsonValue: TypeAlias = JsonScalar | Mapping[str, "FrozenJsonValue"] | tuple["FrozenJsonValue", ...]
FrozenJsonObject: TypeAlias = Mapping[str, FrozenJsonValue]

ModelType = TypeVar("ModelType", bound="_ContractSnapshot")


def _freeze(value: Any) -> FrozenJsonValue:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return cast(JsonScalar, value)


def _object(value: Any) -> FrozenJsonObject:
    frozen = _freeze(value)
    return cast(FrozenJsonObject, frozen)


def _array(value: Any) -> tuple[FrozenJsonValue, ...]:
    frozen = _freeze(value)
    return cast(tuple[FrozenJsonValue, ...], frozen)


@dataclass(frozen=True, slots=True)
class _ContractSnapshot:
    schema_version: str
    report_id: str


@dataclass(frozen=True, slots=True)
class ReportData(_ContractSnapshot):
    """Immutable source and calculated facts from validated ReportData JSON."""

    sample: FrozenJsonObject
    run: FrozenJsonObject
    provenance: FrozenJsonObject
    biomarkers: tuple[FrozenJsonValue, ...]
    qc_metrics: tuple[FrozenJsonValue, ...]
    variants: tuple[FrozenJsonValue, ...]
    attachments: tuple[FrozenJsonValue, ...]
    diagnostics: tuple[FrozenJsonValue, ...]

    @classmethod
    def from_validated(cls, document: Mapping[str, Any]) -> ReportData:
        """Create a detached snapshot after boundary validation has succeeded."""
        return cls(
            schema_version=cast(str, document["schemaVersion"]),
            report_id=cast(str, document["reportId"]),
            sample=_object(document["sample"]),
            run=_object(document["run"]),
            provenance=_object(document["provenance"]),
            biomarkers=_array(document["biomarkers"]),
            qc_metrics=_array(document["qcMetrics"]),
            variants=_array(document["variants"]),
            attachments=_array(document["attachments"]),
            diagnostics=_array(document["diagnostics"]),
        )


@dataclass(frozen=True, slots=True)
class ReviewState(_ContractSnapshot):
    """Immutable snapshot of validated human review activity."""

    revision: int
    status: str
    reviewer: FrozenJsonObject
    created_at: str
    updated_at: str
    variant_reviews: tuple[FrozenJsonValue, ...]
    run_qc_assessment: FrozenJsonObject
    report_notes: str
    value_corrections: tuple[FrozenJsonValue, ...]
    finalized_at: str | None = None
    finalized_by: str | None = None

    @classmethod
    def from_validated(cls, document: Mapping[str, Any]) -> ReviewState:
        """Create a detached snapshot after boundary validation has succeeded."""
        return cls(
            schema_version=cast(str, document["schemaVersion"]),
            report_id=cast(str, document["reportId"]),
            revision=cast(int, document["revision"]),
            status=cast(str, document["status"]),
            reviewer=_object(document["reviewer"]),
            created_at=cast(str, document["createdAt"]),
            updated_at=cast(str, document["updatedAt"]),
            variant_reviews=_array(document["variantReviews"]),
            run_qc_assessment=_object(document["runQcAssessment"]),
            report_notes=cast(str, document["reportNotes"]),
            value_corrections=_array(document["valueCorrections"]),
            finalized_at=cast(str | None, document.get("finalizedAt")),
            finalized_by=cast(str | None, document.get("finalizedBy")),
        )
