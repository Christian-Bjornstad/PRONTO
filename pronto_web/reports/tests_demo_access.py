from django.test import Client, TestCase, override_settings
from django.conf import settings
from django.core.management import call_command, CommandError
from pronto_web.reports.tests_draft_save import DraftSaveTests


class DemoAccessTests(TestCase):
    setUp = DraftSaveTests.setUp

    def demo(self):
        return override_settings(PRONTO_DEMO_ENABLED=True, PRONTO_DEMO_REPORTS=[self.report.report_id],
            PRONTO_DEMO_USER_ID=self.writer.pk, PRONTO_REQUIRE_INITIALS=True,
            MIDDLEWARE=[*settings.MIDDLEWARE, 'pronto_web.reports.demo_access.DemoAccessMiddleware'])

    def test_demo_opens_only_allowlisted_report_without_login(self):
        self.record.report_data['attachments'] = []
        self.record.save()
        url = f'/reports/{self.report.report_id}/'
        assert self.client.get(url).status_code == 401
        with self.demo():
            self.client = Client()
            assert self.client.get(url, HTTP_HOST='127.0.0.1').status_code == 200
            assert self.client.get('/reports/unlisted/', HTTP_HOST='127.0.0.1').status_code in (401, 404)
            assert self.client.get(url, REMOTE_ADDR='192.168.1.2', HTTP_HOST='127.0.0.1').status_code == 403
            assert self.client.get(url, HTTP_HOST='evil.example').status_code in (400, 403)
            assert self.client.get(url, HTTP_HOST='127.0.0.1', HTTP_X_FORWARDED_FOR='127.0.0.1').status_code == 403
            assert self.client.get(f'/reports/{self.report.report_id}/alignments/anything/data/', HTTP_HOST='127.0.0.1').status_code == 401

    def test_demo_command_rejects_missing_database_or_allowlist(self):
        for options in ({}, {'database': 'x.demo.sqlite3'}, {'report': ['x']}):
            with self.assertRaises(CommandError):
                call_command('run_demo', **options)

    def test_demo_save_finalize_print_history(self):
        import uuid
        from pronto_web.reports.models import ReviewAudit, ReportPrintAudit, ReviewRevision
        self.record.report_data['attachments'] = []
        self.record.save()
        source = self.record.report_data
        with self.demo():
            client = Client(HTTP_HOST='127.0.0.1')
            command = {'schemaVersion': '1.0', 'reportId': self.report.report_id,
                'baseRevision': 1, 'draft': self.draft, 'declaredInitials': 'AB'}
            saved = client.post(self.url, data=command, content_type='application/json')
            assert saved.status_code == 201
            command.update(baseRevision=2, draft=saved.json()['review'], declaredInitials='CD')
            final = client.post(f'/reports/{self.report.report_id}/finalizations/', data=command, content_type='application/json')
            assert final.status_code == 201
            assert final.json()['review']['lastSavedAttribution']['declaredInitials'] == 'AB'
            assert final.json()['review']['finalizationAttribution']['declaredInitials'] == 'CD'
            printed = client.post(f'/reports/{self.report.report_id}/print-requests/', data={
                'schemaVersion': '1.0', 'revision': 3, 'requestId': str(uuid.uuid4()), 'declaredInitials': 'EF'}, content_type='application/json')
            assert printed.status_code == 201
            assert ReviewRevision.objects.count() == 3
            assert list(ReviewAudit.objects.order_by('revision').values_list('declared_initials', flat=True)) == ['AB', 'CD']
            assert ReportPrintAudit.objects.get().declared_initials == 'EF'
            self.record.refresh_from_db()
            assert self.record.report_data == source
            assert client.get(f'/reports/{self.report.report_id}/alignments/anything/data/').status_code == 401
