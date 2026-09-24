"""Validated, authorized review commands independent of Django."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Mapping

from pronto_report.models import ReportData, ReviewState
from pronto_report.review.contracts import (
    COMMAND_VERSION, AuditRecord, FinalizeRequest, ReviewCommandError,
    ReviewCommandResponse, SaveDraftRequest,
)
from pronto_report.review.repository import ReviewAuthorizer, ReviewRepository
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import ContractValidationError, validate_review_state


class ReviewCommandService:
    def __init__(
        self,
        repository: ReviewRepository,
        authorizer: ReviewAuthorizer,
        *,
        clock: Callable[[], datetime],
    ) -> None:
        self.repository = repository
        self.authorizer = authorizer
        self.clock = clock

    def _current(
        self, request: SaveDraftRequest | FinalizeRequest, actor_id: str, report: ReportData
    ) -> ReviewState:
        if not actor_id or not self.authorizer.can_review(actor_id, report.report_id):
            raise ReviewCommandError("FORBIDDEN", "Review access denied", 403)
        if request.schema_version != COMMAND_VERSION or request.report_id != report.report_id:
            raise ReviewCommandError("INVALID_COMMAND", "Invalid review command", 422)
        if type(request.base_revision) is not int or request.base_revision < 1:
            raise ReviewCommandError("INVALID_COMMAND", "Invalid base revision", 422)
        current = self.repository.latest(report.report_id)
        if current is None:
            raise ReviewCommandError("REVIEW_NOT_FOUND", "Review not found", 404)
        if request.base_revision != current.revision:
            raise ReviewCommandError(
                "REVISION_CONFLICT", "Saved revision has changed", 409,
                current_revision=current.revision,
            )
        if current.status == "FINAL":
            raise ReviewCommandError("FINAL_LOCKED", "Final review is locked", 409)
        return current

    @staticmethod
    def _draft(
        raw: Mapping[str, Any], report: ReportData, base_revision: int
    ) -> ReviewState:
        try:
            draft = validate_review_state(raw, report=report)
        except ContractValidationError as error:
            raise ReviewCommandError(
                "INVALID_DRAFT", "Draft did not pass validation", 422, issues=error.issues
            ) from error
        if draft.schema_version != "2.0" or draft.status != "DRAFT" or draft.revision != base_revision:
            raise ReviewCommandError("INVALID_DRAFT", "Expected a v2 draft at the base revision", 422)
        return draft

    def _timestamp(self) -> str:
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Review command clock must be timezone-aware")
        return now.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def _commit(
        self, report_id: str, base_revision: int, review: ReviewState,
        actor_id: str, action: str, timestamp: str,
    ) -> ReviewCommandResponse:
        audit = AuditRecord(report_id, actor_id, action, review.revision, timestamp)
        if not self.repository.commit(report_id, base_revision, review, audit):
            latest = self.repository.latest(report_id)
            raise ReviewCommandError(
                "REVISION_CONFLICT", "Saved revision has changed", 409,
                current_revision=latest.revision if latest else None,
            )
        return ReviewCommandResponse(COMMAND_VERSION, review, audit)

    def save(
        self, request: SaveDraftRequest, *, actor_id: str, report: ReportData
    ) -> ReviewCommandResponse:
        current = self._current(request, actor_id, report)
        draft = self._draft(request.draft, report, request.base_revision)
        if draft.created_at != current.created_at:
            raise ReviewCommandError("INVALID_DRAFT", "Draft creation time changed", 422)
        known_variants = {item["variantId"] for item in report.variants}
        reviewed_variants = [item["variantId"] for item in draft.variant_reviews]
        if len(reviewed_variants) != len(set(reviewed_variants)) or set(reviewed_variants) - known_variants:
            raise ReviewCommandError("INVALID_DRAFT", "Unknown or duplicate reviewed variant", 422)
        previous_corrections = {item["path"]: item for item in current.value_corrections}
        allowed_originals = {
            f"/sample/{key}": report.sample.get(key)
            for key in ("tumourType", "specimenType")
        }
        allowed_originals.update({
            f"/biomarkers/{index}/value": item["value"]
            for index, item in enumerate(report.biomarkers)
            if item["metricId"] in {"tmb", "msi"}
        })
        correction_paths = [item["path"] for item in draft.value_corrections]
        if len(correction_paths) != len(set(correction_paths)):
            raise ReviewCommandError("INVALID_DRAFT", "Duplicate source correction", 422)
        for correction in draft.value_corrections:
            path = correction["path"]
            if path not in allowed_originals or correction["originalValue"] != allowed_originals[path]:
                raise ReviewCommandError("INVALID_DRAFT", "Invalid source correction", 422)
            if previous_corrections.get(path) != correction and correction["author"] != actor_id:
                raise ReviewCommandError("INVALID_DRAFT", "Correction author does not match actor", 422)
        if current.notes and draft.notes["importedLegacyNote"] != current.notes["importedLegacyNote"]:
            raise ReviewCommandError("INVALID_DRAFT", "Imported legacy note is read-only", 422)
        timestamp = self._timestamp()
        document = json.loads(serialize_review_state(draft))
        document["revision"] = current.revision + 1
        document["updatedAt"] = timestamp
        document["reviewer"] = {"reviewerId": actor_id}
        for correction in document["valueCorrections"]:
            if previous_corrections.get(correction["path"]) != correction:
                correction["timestamp"] = timestamp
        saved = validate_review_state(document, report=report)
        return self._commit(report.report_id, current.revision, saved, actor_id, "SAVE_DRAFT", timestamp)

    def finalize(
        self, request: FinalizeRequest, *, actor_id: str, report: ReportData
    ) -> ReviewCommandResponse:
        current = self._current(request, actor_id, report)
        draft = self._draft(request.draft, report, request.base_revision)
        if serialize_review_state(draft) != serialize_review_state(current):
            raise ReviewCommandError("UNSAVED_CHANGES", "Save changes before finalizing", 409)
        timestamp = self._timestamp()
        document = json.loads(serialize_review_state(current))
        document.update({
            "revision": current.revision + 1,
            "status": "FINAL",
            "updatedAt": timestamp,
            "finalizedAt": timestamp,
            "finalizedBy": actor_id,
        })
        finalized = validate_review_state(document, report=report)
        return self._commit(report.report_id, current.revision, finalized, actor_id, "FINALIZE", timestamp)
