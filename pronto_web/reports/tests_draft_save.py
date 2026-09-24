"""The authenticated draft endpoint must preserve revisions and audit together."""

import json
from dataclasses import replace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase

from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.migration import migrate_review_state_v1
from pronto_report.serialization import serialize_report_data, serialize_review_state
from pronto_web.reports.models import ReportGrant, ReportRecord, ReviewRevision


class DraftSaveTests(TestCase):
    def setUp(self):
        self.report = build_report()
        self.review = migrate_review_state_v1(draft_review(self.report))
        self.record = ReportRecord.objects.create(
            report_id=self.report.report_id,
            report_data=json.loads(serialize_report_data(self.report)),
        )
        ReviewRevision.objects.create(
            report=self.record, revision=self.review.revision,
            review_data=json.loads(serialize_review_state(self.review)),
        )
        self.writer = get_user_model().objects.create_user(username="writer")
        self.other = get_user_model().objects.create_user(username="other")
        ReportGrant.objects.create(report=self.record, user=self.writer)
        self.url = f"/reports/{self.report.report_id}/revisions/"
        self.draft = json.loads(serialize_review_state(self.review))
        self.draft["notes"]["summary"] = "Syntetisk vurdering"

    def payload(self, **overrides):
        return {"schemaVersion": "1.0", "reportId": self.report.report_id,
                "baseRevision": 1, "draft": self.draft, **overrides}

    def post(self, client, payload):
        return client.post(self.url, data=json.dumps(payload), content_type="application/json")

    def test_save_creates_one_revision_and_audit_then_stale_client_gets_409(self):
        from pronto_web.reports.models import ReviewAudit

        first_client = Client()
        second_client = Client()
        first_client.force_login(self.writer)
        second_client.force_login(self.writer)
        first = self.post(first_client, self.payload())

        assert first.status_code == 201
        assert first.json()["review"]["revision"] == 2
        assert first.json()["review"]["notes"]["summary"] == "Syntetisk vurdering"
        assert first.json()["review"]["reviewer"]["reviewerId"] == str(self.writer.pk)
        assert first.json()["audit"]["action"] == "SAVE_DRAFT"
        assert first.json()["audit"]["actorId"] == str(self.writer.pk)
        assert ReviewRevision.objects.filter(report=self.record).count() == 2
        assert ReviewAudit.objects.filter(report=self.record, revision=2).count() == 1

        stale = self.post(second_client, self.payload())
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "REVISION_CONFLICT"
        assert stale.json()["error"]["currentRevision"] == 2
        assert ReviewRevision.objects.filter(report=self.record).count() == 2
        assert ReviewAudit.objects.filter(report=self.record).count() == 1

    def test_save_accepts_reasoned_source_correction_from_signed_in_biologist(self):
        client = Client()
        client.force_login(self.writer)
        self.draft["valueCorrections"].append({
            "path": "/sample/tumourType",
            "originalValue": self.report.sample.get("tumourType"),
            "correctedValue": "Syntetisk korrigert verdi",
            "reason": "Kontrollert mot syntetisk kildemateriale",
            "author": str(self.writer.pk),
            "timestamp": self.draft["updatedAt"],
        })

        response = self.post(client, self.payload())

        assert response.status_code == 201
        saved = response.json()["review"]["valueCorrections"][-1]
        assert saved["author"] == str(self.writer.pk)
        assert saved["timestamp"] == response.json()["review"]["updatedAt"]
        assert saved["originalValue"] == self.report.sample.get("tumourType")

    def test_authentication_report_grant_and_csrf_are_required(self):
        assert self.post(Client(), self.payload()).status_code == 401
        ungranted = Client()
        ungranted.force_login(self.other)
        denied = self.post(ungranted, self.payload())
        assert denied.status_code == 404
        assert denied.json()["error"]["code"] == "REVIEW_NOT_FOUND"

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.get("/accounts/login/")
        csrf_client.force_login(self.writer)
        assert self.post(csrf_client, self.payload()).status_code == 403
        token = csrf_client.cookies["csrftoken"].value
        accepted = csrf_client.post(self.url, data=json.dumps(self.payload()),
                                    content_type="application/json", HTTP_X_CSRFTOKEN=token)
        assert accepted.status_code == 201

    def test_oversized_command_is_rejected_before_persistence(self):
        from pronto_web.reports.models import ReviewAudit

        client = Client()
        client.force_login(self.writer)
        oversized = self.payload(extra="x" * (1024 * 1024))
        response = self.post(client, oversized)
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
        assert ReviewRevision.objects.filter(report=self.record).count() == 1
        assert ReviewAudit.objects.count() == 0

    def test_invalid_command_draft_and_final_lock_write_nothing(self):
        from pronto_web.reports.models import ReviewAudit

        client = Client()
        client.force_login(self.writer)
        wrong_report = self.post(client, self.payload(reportId="another-report"))
        assert wrong_report.status_code == 422
        bad_draft = {**self.draft, "reportId": "another-report"}
        invalid = self.post(client, self.payload(draft=bad_draft))
        assert invalid.status_code == 422
        bad_correction = json.loads(json.dumps(self.draft))
        bad_correction["valueCorrections"].append({
            "path": "/sample/unknown", "originalValue": None,
            "correctedValue": "synthetic", "reason": "No source",
            "author": str(self.writer.pk), "timestamp": "2026-09-23T10:00:00Z",
        })
        rejected = self.post(client, self.payload(draft=bad_correction))
        assert rejected.status_code == 422
        assert ReviewRevision.objects.filter(report=self.record).count() == 1
        assert ReviewAudit.objects.count() == 0

        final = json.loads(serialize_review_state(self.review))
        final.update({"status": "FINAL", "finalizedAt": "2026-09-22T13:00:00Z",
                      "finalizedBy": "biologist", "updatedAt": "2026-09-22T13:00:00Z"})
        ReviewRevision.objects.filter(report=self.record).update(review_data=final)
        locked = self.post(client, self.payload())
        assert locked.status_code == 409
        assert locked.json()["error"]["code"] == "FINAL_LOCKED"
        assert ReviewRevision.objects.filter(report=self.record).count() == 1
        assert ReviewAudit.objects.count() == 0

    def test_audit_write_failure_rolls_back_new_revision(self):
        from pronto_web.reports.models import ReviewAudit

        client = Client()
        client.force_login(self.writer)
        with patch.object(ReviewAudit.objects, "create", side_effect=IntegrityError("audit unavailable")):
            with self.assertRaises(IntegrityError):
                self.post(client, self.payload())
        assert ReviewRevision.objects.filter(report=self.record).count() == 1
        assert ReviewAudit.objects.count() == 0

    def test_revoked_grant_cannot_commit_after_an_earlier_authorization_check(self):
        from pronto_report.review.contracts import AuditRecord, ReviewCommandError
        from pronto_web.reports.review_repository import DjangoReviewRepository

        repository = DjangoReviewRepository(self.record, self.report)
        assert repository.latest(self.report.report_id).revision == 1
        ReportGrant.objects.filter(report=self.record, user=self.writer).delete()
        next_review = replace(self.review, revision=2)
        audit = AuditRecord(self.report.report_id, str(self.writer.pk), "SAVE_DRAFT", 2,
                            "2026-09-23T10:00:00Z")

        with self.assertRaises(ReviewCommandError) as caught:
            repository.commit(self.report.report_id, 1, next_review, audit)
        assert caught.exception.code == "FORBIDDEN"
        assert ReviewRevision.objects.filter(report=self.record).count() == 1
