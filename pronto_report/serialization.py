"""Deterministic and bounded JSON serialization for PRONTO contracts."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

from pronto_report.models import FrozenJsonValue, ReportData, ReviewState
from pronto_report.validation import (
    ContractValidationError,
    ValidationIssue,
    validate_report_data,
    validate_review_state,
)


MAX_JSON_BYTES = 25 * 1024 * 1024


class _DuplicateFieldError(ValueError):
    pass


class _InvalidNumberError(ValueError):
    pass


def _thaw(value: FrozenJsonValue) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _report_document(report: ReportData) -> dict[str, Any]:
    return {
        "schemaVersion": report.schema_version,
        "reportId": report.report_id,
        "sample": _thaw(report.sample),
        "run": _thaw(report.run),
        "provenance": _thaw(report.provenance),
        "biomarkers": _thaw(report.biomarkers),
        "qcMetrics": _thaw(report.qc_metrics),
        "variants": _thaw(report.variants),
        "attachments": _thaw(report.attachments),
        "diagnostics": _thaw(report.diagnostics),
    }


def _review_document(review: ReviewState) -> dict[str, Any]:
    document = {
        "schemaVersion": review.schema_version,
        "reportId": review.report_id,
        "revision": review.revision,
        "status": review.status,
        "reviewer": _thaw(review.reviewer),
        "createdAt": review.created_at,
        "updatedAt": review.updated_at,
        "variantReviews": _thaw(review.variant_reviews),
        "runQcAssessment": _thaw(review.run_qc_assessment),
        "valueCorrections": _thaw(review.value_corrections),
    }
    if review.schema_version == "2.0":
        document["notes"] = _thaw(review.notes) if review.notes is not None else None
    else:
        document["reportNotes"] = review.report_notes
    if review.finalized_at is not None:
        document["finalizedAt"] = review.finalized_at
    if review.finalized_by is not None:
        document["finalizedBy"] = review.finalized_by
    return document


def _encode(document: Mapping[str, Any]) -> bytes:
    text = json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"{text}\n".encode("utf-8")


def serialize_report_data(report: ReportData) -> bytes:
    """Serialize ReportData to canonical, newline-terminated UTF-8 JSON."""
    return _encode(_report_document(report))


def serialize_review_state(review: ReviewState) -> bytes:
    """Serialize ReviewState to canonical, newline-terminated UTF-8 JSON."""
    return _encode(_review_document(review))


def _reject_duplicate_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateFieldError()
        result[key] = value
    return result


def _parse_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise _InvalidNumberError()
    return parsed


def _reject_constant(value: str) -> None:
    raise _InvalidNumberError()


def _decode(payload: str | bytes) -> Any:
    if isinstance(payload, bytes):
        encoded = payload
    elif isinstance(payload, str):
        try:
            encoded = payload.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError() from error
    else:
        raise TypeError()

    if len(encoded) > MAX_JSON_BYTES:
        raise OverflowError()

    text = encoded.decode("utf-8")
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_fields,
        parse_float=_parse_float,
        parse_constant=_reject_constant,
    )


def _decode_error(
    *, contract_code: str, contract_message: str, issue_code: str, issue_message: str
) -> ContractValidationError:
    return ContractValidationError(
        contract_code,
        contract_message,
        [ValidationIssue(path="$", code=issue_code, message=issue_message)],
    )


def _load_payload(
    payload: str | bytes, *, contract_code: str, contract_message: str
) -> Any:
    try:
        return _decode(payload)
    except OverflowError as error:
        raise _decode_error(
            contract_code=contract_code,
            contract_message=contract_message,
            issue_code="DOCUMENT_TOO_LARGE",
            issue_message="JSON document exceeds the allowed size",
        ) from error
    except _DuplicateFieldError as error:
        raise _decode_error(
            contract_code=contract_code,
            contract_message=contract_message,
            issue_code="DUPLICATE_FIELD",
            issue_message="JSON document contains a duplicate field",
        ) from error
    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
        RecursionError,
        TypeError,
        ValueError,
        _InvalidNumberError,
    ) as error:
        raise _decode_error(
            contract_code=contract_code,
            contract_message=contract_message,
            issue_code="INVALID_JSON",
            issue_message="Input is not a valid JSON document",
        ) from error


def deserialize_report_data(payload: str | bytes) -> ReportData:
    """Parse and validate untrusted ReportData JSON before returning a model."""
    document = _load_payload(
        payload,
        contract_code="INVALID_REPORT_DATA",
        contract_message="Report data did not pass validation",
    )
    return validate_report_data(document)


def deserialize_review_state(
    payload: str | bytes, *, report: ReportData | None = None
) -> ReviewState:
    """Parse and validate untrusted ReviewState JSON before returning a model."""
    document = _load_payload(
        payload,
        contract_code="INVALID_REVIEW_STATE",
        contract_message="Review state did not pass validation",
    )
    return validate_review_state(document, report=report)
