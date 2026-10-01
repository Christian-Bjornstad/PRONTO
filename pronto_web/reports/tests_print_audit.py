import uuid
from unittest.mock import patch
from django.db import OperationalError
from django.test import TestCase, Client
from pronto_web.reports.tests_draft_save import DraftSaveTests
from pronto_web.reports.models import ReviewRevision


class PrintAuditTests(TestCase):
    setUp = DraftSaveTests.setUp

    def request_print(self, **changes):
        payload = {'schemaVersion': '1.0', 'revision': 1, 'declaredInitials': 'ab', 'requestId': str(self.request_id)}
        return self.client.post(f'/reports/{self.report.report_id}/print-requests/',
            data={**payload, **changes}, content_type='application/json')

    def test_print_is_idempotent_without_mutating_review(self):
        self.client.force_login(self.writer)
        self.request_id = uuid.uuid4()
        first = self.request_print()
        assert first.status_code == 201
        assert self.request_print().json() == first.json()
        assert first.json()['declaredInitials'] == 'AB'
        assert self.request_print(declaredInitials='CD').status_code == 409
        assert ReviewRevision.objects.count() == 1
        self.request_id = uuid.uuid4()
        assert self.request_print().status_code == 201

    def test_print_requires_access_valid_initials_and_current_revision(self):
        self.request_id = uuid.uuid4()
        assert self.request_print().status_code == 401
        self.client.force_login(self.other)
        assert self.request_print().status_code == 404
        self.client.force_login(self.writer)
        assert self.request_print(revision=2).status_code == 409
        assert self.request_print(declaredInitials='<script>').status_code == 422
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.writer)
        assert self.request_print().status_code == 403

    def test_failed_audit_does_not_claim_success(self):
        self.client.force_login(self.writer)
        self.request_id = uuid.uuid4()
        with patch('pronto_web.reports.print_audit.ReportPrintAudit.objects.create', side_effect=OperationalError('unavailable')):
            assert self.request_print().status_code == 503
        assert ReviewRevision.objects.count() == 1

    def test_retry_after_revision_advance_returns_original_event(self):
        self.client.force_login(self.writer)
        self.request_id = uuid.uuid4()
        first = self.request_print().json()
        original = ReviewRevision.objects.get(revision=1)
        newer = dict(original.review_data, revision=2)
        ReviewRevision.objects.create(report=self.record, revision=2, review_data=newer)
        assert self.request_print().json() == first
        self.request_id = uuid.uuid4()
        assert self.request_print().status_code == 409
