"""Versioned save/finalize command and result shapes."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from pronto_report.models import ReviewState
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import ValidationIssue


COMMAND_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class SaveDraftRequest:
    schema_version: str
    report_id: str
    base_revision: int
    draft: Mapping[str, Any]
    declared_initials: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SaveDraftRequest:
        return cls(*_parse_request(payload))


@dataclass(frozen=True, slots=True)
class FinalizeRequest:
    schema_version: str
    report_id: str
    base_revision: int
    draft: Mapping[str, Any]
    declared_initials: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> FinalizeRequest:
        return cls(*_parse_request(payload))


@dataclass(frozen=True, slots=True)
class AuditRecord:
    report_id: str
    actor_id: str
    action: str
    revision: int
    timestamp: str
    declared_initials: str | None = None
    attribution_method: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "reportId": self.report_id,
            "actorId": self.actor_id,
            "action": self.action,
            "revision": self.revision,
            "timestamp": self.timestamp,
            **({'declaredInitials': self.declared_initials, 'method': self.attribution_method} if self.declared_initials else {}),
        }


@dataclass(frozen=True, slots=True)
class ReviewCommandResponse:
    schema_version: str
    review: ReviewState
    audit: AuditRecord

    def as_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "review": json.loads(serialize_review_state(self.review)),
            "audit": self.audit.as_dict(),
        }


class ReviewCommandError(Exception):
    """Stable, input-safe error for a future HTTP adapter."""

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int,
        *,
        current_revision: int | None = None,
        issues: tuple[ValidationIssue, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.current_revision = current_revision
        self.issues = issues

    def as_dict(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": str(self)}
        if self.current_revision is not None:
            error["currentRevision"] = self.current_revision
        if self.issues:
            error["issues"] = [issue.as_dict() for issue in self.issues]
        return {"schemaVersion": COMMAND_VERSION, "error": error}


def _parse_request(payload: Mapping[str, Any]) -> tuple[str, str, int, Mapping[str, Any], str | None]:
    expected = {"schemaVersion", "reportId", "baseRevision", "draft"}
    if not isinstance(payload, Mapping) or not expected <= set(payload) or set(payload) - expected - {'declaredInitials'}:
        raise ReviewCommandError("INVALID_COMMAND", "Invalid review command", 422)
    version = payload["schemaVersion"]
    report_id = payload["reportId"]
    revision = payload["baseRevision"]
    draft = payload["draft"]
    if (version != COMMAND_VERSION or not isinstance(report_id, str) or not report_id
            or type(revision) is not int or revision < 1 or not isinstance(draft, Mapping)):
        raise ReviewCommandError("INVALID_COMMAND", "Invalid review command", 422)
    from pronto_report.review.attribution import normalize_initials
    initials = normalize_initials(payload['declaredInitials']) if 'declaredInitials' in payload else None
    return version, report_id, revision, draft, initials
