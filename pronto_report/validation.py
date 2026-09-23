"""Boundary validation for untrusted PRONTO report contract data."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from pronto_report.models import ReportData, ReviewState


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One stable, user-safe contract validation issue."""

    path: str
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "code": self.code, "message": self.message}


class ContractValidationError(ValueError):
    """A predictable validation failure that never includes input values."""

    def __init__(
        self, code: str, message: str, issues: Iterable[ValidationIssue]
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.issues = tuple(issues)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "issues": [issue.as_dict() for issue in self.issues],
        }


@lru_cache(maxsize=3)
def _validator(schema_name: str) -> Draft202012Validator:
    schema_resource = resources.files("pronto_report.schemas").joinpath(schema_name)
    schema = json.loads(schema_resource.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _format_path(parts: Sequence[str | int]) -> str:
    path = ""
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        elif path:
            path += f".{part}"
        else:
            path = part
    return path or "$"


def _path_with(parts: Sequence[str | int], field: str) -> str:
    return _format_path([*parts, field])


def _issue_for(error: ValidationError) -> list[ValidationIssue]:
    parts = list(error.absolute_path)

    if error.validator == "required" and isinstance(error.instance, Mapping):
        missing = [name for name in error.validator_value if name not in error.instance]
        return [
            ValidationIssue(
                path=_path_with(parts, name),
                code="REQUIRED_FIELD",
                message="Required field is missing",
            )
            for name in missing
        ]

    if error.validator == "additionalProperties" and isinstance(
        error.instance, Mapping
    ):
        allowed = set(error.schema.get("properties", {}))
        unknown = sorted(set(error.instance) - allowed)
        return [
            ValidationIssue(
                path=_path_with(parts, name),
                code="UNKNOWN_FIELD",
                message="Unknown field is not allowed",
            )
            for name in unknown
        ]

    path = _format_path(parts)
    if parts == ["schemaVersion"] and error.validator in {"const", "enum", "type"}:
        return [
            ValidationIssue(
                path=path,
                code="UNSUPPORTED_SCHEMA_VERSION",
                message="Schema version is not supported",
            )
        ]

    code_and_message = {
        "type": ("INVALID_TYPE", "Value has an invalid type"),
        "format": ("INVALID_FORMAT", "Value has an invalid format"),
        "maxItems": ("TOO_LARGE", "Collection exceeds the allowed size"),
        "maxLength": ("TOO_LARGE", "Text exceeds the allowed size"),
        "maxProperties": ("TOO_LARGE", "Object exceeds the allowed size"),
        "pattern": ("INVALID_VALUE", "Value has an invalid format"),
        "enum": ("INVALID_VALUE", "Value is not one of the allowed options"),
        "const": ("INVALID_VALUE", "Value is not allowed"),
        "minimum": ("OUT_OF_RANGE", "Value is outside the allowed range"),
        "maximum": ("OUT_OF_RANGE", "Value is outside the allowed range"),
        "minLength": ("REQUIRED_VALUE", "Value must not be empty"),
        "minItems": ("REQUIRED_VALUE", "Collection must not be empty"),
    }
    code, message = code_and_message.get(
        error.validator, ("INVALID_VALUE", "Value did not pass validation")
    )
    return [ValidationIssue(path=path, code=code, message=message)]


def _schema_issues(document: Any, schema_name: str) -> tuple[ValidationIssue, ...]:
    errors = _validator(schema_name).iter_errors(document)
    issues = [issue for error in errors for issue in _issue_for(error)]
    unique = {(issue.path, issue.code, issue.message): issue for issue in issues}
    return tuple(sorted(unique.values(), key=lambda issue: (issue.path, issue.code)))


def validate_report_data(document: Any) -> ReportData:
    """Validate untrusted ReportData input and return an immutable snapshot."""
    issues = _schema_issues(document, "report-data-v1.schema.json")
    if issues:
        raise ContractValidationError(
            "INVALID_REPORT_DATA", "Report data did not pass validation", issues
        )
    return ReportData.from_validated(document)


def validate_review_state(
    document: Any, *, report: ReportData | None = None
) -> ReviewState:
    """Validate untrusted ReviewState input and optionally bind it to a report."""
    version = document.get("schemaVersion") if isinstance(document, Mapping) else None
    schema_name = (
        "review-state-v2.schema.json"
        if version == "2.0"
        else "review-state-v1.schema.json"
    )
    issues = list(_schema_issues(document, schema_name))
    if not issues and report is not None and document["reportId"] != report.report_id:
        issues.append(
            ValidationIssue(
                path="reportId",
                code="MISMATCHED_REPORT_ID",
                message="Review state belongs to a different report",
            )
        )
    if issues:
        raise ContractValidationError(
            "INVALID_REVIEW_STATE", "Review state did not pass validation", issues
        )
    return ReviewState.from_validated(document)
