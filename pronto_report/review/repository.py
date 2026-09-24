"""Atomic persistence boundary; Django will implement it in a later task."""

from __future__ import annotations

from typing import Protocol

from pronto_report.models import ReviewState
from pronto_report.review.contracts import AuditRecord


class ReviewRepository(Protocol):
    def latest(self, report_id: str) -> ReviewState | None:
        """Return the latest saved revision, or None when absent."""

    def commit(
        self,
        report_id: str,
        base_revision: int,
        review: ReviewState,
        audit: AuditRecord,
    ) -> bool:
        """Atomically compare revision and write review plus audit, or write nothing."""


class ReviewAuthorizer(Protocol):
    def can_review(self, actor_id: str, report_id: str) -> bool:
        """Check authenticated actor's report-level review permission."""
