"""Standalone HTML downloads are audited against an exact saved revision."""

import json
from uuid import uuid4
from unittest.mock import patch

from django.db import DatabaseError
from django.test import Client, TestCase

from pronto_web.reports.models import ReviewRevision


class HtmlExportTests(TestCase):
    def setUp(self):
        from pronto_web.reports.tests_draft_save import DraftSaveTests
        DraftSaveTests.setUp(self)

    def payload(self, **overrides):
        return {'schemaVersion': '1.0', 'reportId': self.report.report_id,
                'revision': 1, 'declaredInitials': 'AB', 'requestId': str(uuid4()),
                **overrides}

    def post(self, client, payload):
        return client.post(f'/reports/{self.report.report_id}/html-exports/',
                           data=json.dumps(payload), content_type='application/json')

    def test_download_is_offline_html_and_exact_retry_keeps_one_audit(self):
        from pronto_web.reports.models import ReportHtmlExportAudit
        client = Client()
        client.force_login(self.writer)
        payload = self.payload()

        first = self.post(client, payload)
        assert first.status_code == 200
        assert first['Content-Type'].startswith('text/html; charset=utf-8')
        assert first['Content-Disposition'].startswith('attachment; filename=')
        assert first['X-Content-Type-Options'] == 'nosniff'
        assert "default-src 'none'" in first['Content-Security-Policy']
        assert "style-src 'unsafe-inline'" in first['Content-Security-Policy']
        assert b'Key findings' in first.content and b'Revision 1' in first.content
        assert b'<script' not in first.content and b'https://' not in first.content
        event = ReportHtmlExportAudit.objects.get(report=self.record)
        assert event.action == 'HTML_DOWNLOAD_REQUESTED'
        assert event.actor_id == self.writer.pk
        assert event.declared_initials == 'AB'
        assert event.revision == 1
        assert not any(field.name in {'content', 'html', 'pdf'} for field in event._meta.fields)

        newer = json.loads(json.dumps(ReviewRevision.objects.get(report=self.record).review_data))
        newer['revision'] = 2
        newer['notes']['summary'] = 'Later revision only'
        ReviewRevision.objects.create(report=self.record, revision=2, review_data=newer)
        replay = self.post(client, payload)
        assert replay.status_code == 200
        assert replay.content == first.content
        assert b'Later revision only' not in replay.content
        assert ReportHtmlExportAudit.objects.filter(report=self.record).count() == 1

    def test_export_rejects_invalid_access_csrf_stale_and_conflicting_key(self):
        from pronto_web.reports.models import ReportHtmlExportAudit
        payload = self.payload()
        assert self.post(Client(), payload).status_code in (401, 404)
        ungranted = Client()
        ungranted.force_login(self.other)
        assert self.post(ungranted, payload).status_code == 404
        guarded = Client(enforce_csrf_checks=True)
        guarded.force_login(self.writer)
        assert self.post(guarded, payload).status_code == 403
        client = Client()
        client.force_login(self.writer)
        for invalid in (
            {**payload, 'reportId': 'another-report'},
            {**payload, 'declaredInitials': '1'},
            {**payload, 'requestId': 'not-a-uuid'},
            {**payload, 'revision': 2},
        ):
            response = self.post(client, invalid)
            assert response.status_code in (409, 422)
            assert 'Content-Disposition' not in response
        assert ReportHtmlExportAudit.objects.count() == 0
        assert self.post(client, payload).status_code == 200
        conflict = self.post(client, {**payload, 'declaredInitials': 'CD'})
        assert conflict.status_code == 409
        assert 'Content-Disposition' not in conflict
        assert ReportHtmlExportAudit.objects.count() == 1

    def test_render_or_audit_failure_returns_no_attachment_or_event(self):
        from pronto_web.reports.models import ReportHtmlExportAudit
        client = Client()
        client.force_login(self.writer)
        with patch('pronto_web.reports.html_export_audit.render_summary_html', side_effect=ValueError('bad render')):
            failed = self.post(client, self.payload())
        assert failed.status_code >= 500
        assert 'Content-Disposition' not in failed
        assert ReportHtmlExportAudit.objects.count() == 0
        with patch.object(ReportHtmlExportAudit.objects, 'create', side_effect=DatabaseError('audit failed')):
            failed = self.post(client, self.payload())
        assert failed.status_code >= 500
        assert 'Content-Disposition' not in failed
        assert ReportHtmlExportAudit.objects.count() == 0
