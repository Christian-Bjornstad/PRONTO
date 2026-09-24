"""Django implementation of the framework-neutral review persistence boundary."""

from datetime import datetime
import json

from django.db import IntegrityError, transaction

from pronto_report.review.contracts import AuditRecord, ReviewCommandError
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import validate_review_state
from pronto_web.reports.models import ReportGrant, ReportRecord, ReviewAudit, ReviewRevision


class DjangoReviewAuthorizer:
    def __init__(self, user):
        self.user = user

    def can_review(self, actor_id: str, report_id: str) -> bool:
        return (self.user.is_authenticated and self.user.is_active
                and actor_id == str(self.user.pk)
                and ReportGrant.objects.filter(report_id=report_id, user=self.user).exists())


class DjangoReviewRepository:
    def __init__(self, record: ReportRecord, report):
        self.record = record
        self.report = report

    def latest(self, report_id: str):
        if report_id != self.record.pk:
            return None
        row = ReviewRevision.objects.filter(report=self.record).order_by("-revision").first()
        if row is None:
            return None
        review = validate_review_state(row.review_data, report=self.report)
        if review.revision != row.revision:
            raise ValueError("Stored review revision does not match its record")
        return review

    def commit(self, report_id: str, base_revision: int, review, audit: AuditRecord) -> bool:
        if report_id != self.record.pk:
            return False
        try:
            # Django 5.2 transactions and row locking:
            # https://docs.djangoproject.com/en/5.2/topics/db/transactions/#controlling-transactions-explicitly
            # https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update
            with transaction.atomic():
                ReportRecord.objects.select_for_update().get(pk=report_id)
                grant = ReportGrant.objects.select_for_update().filter(
                    report_id=report_id, user_id=audit.actor_id,
                ).first()
                if grant is None:
                    raise ReviewCommandError("FORBIDDEN", "Review access denied", 403)
                latest = ReviewRevision.objects.filter(report_id=report_id).order_by("-revision").first()
                if latest is None or latest.revision != base_revision:
                    return False
                ReviewRevision.objects.create(
                    report_id=report_id, revision=review.revision,
                    review_data=json.loads(serialize_review_state(review)),
                )
                ReviewAudit.objects.create(
                    report_id=report_id, actor_id=audit.actor_id, action=audit.action,
                    revision=audit.revision,
                    occurred_at=datetime.fromisoformat(audit.timestamp.replace("Z", "+00:00")),
                )
            return True
        except IntegrityError:
            # A concurrent insert may win the unique (report, revision) constraint.
            latest = ReviewRevision.objects.filter(report_id=report_id).order_by("-revision").first()
            if latest is not None and latest.revision != base_revision:
                return False
            raise
