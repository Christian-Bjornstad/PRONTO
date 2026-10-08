"""Exercise a synthetic cohort through the real saved-review and report flows."""
import json
from collections import Counter
from io import BytesIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import CommandError
from django.test import Client, TestCase, override_settings
from pypdf import PdfReader

from pronto_report.serialization import serialize_report_data
from pronto_web.reports.models import ReportGrant, ReportRecord, ReviewAudit, ReviewRevision


class SyntheticDemoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='local-demo-service')

    def seed(self, count=30, seed=20261001):
        from pronto_web.reports.synthetic_demo import seed_synthetic_cohort
        return seed_synthetic_cohort(self.user, count=count, seed=seed)

    def test_cases_are_repeatable_patient_scoped_and_explicitly_synthetic(self):
        from pronto_web.reports.synthetic_demo import build_synthetic_case
        first = build_synthetic_case(4, seed=20261001)
        repeated = build_synthetic_case(4, seed=20261001)
        other = build_synthetic_case(4, seed=20261002)
        assert serialize_report_data(first.report) == serialize_report_data(repeated.report)
        assert first.assets == repeated.assets
        assert first.report.report_id != other.report.report_id
        assert first.report.sample['patientPseudonym'].startswith('SYN-')
        assert any(d['code'] == 'SYNTHETIC_DEMO' for d in first.report.diagnostics)
        for table in first.report.source_tables:
            assert table['demo']
            assert all(row['sourceSampleId'] == first.report.sample['sampleId'] for row in table['rows'])
        assert {m['metricId']: m['displayRange'] for m in first.report.biomarkers} == {
            'tmb': '[0-100+]', 'msi': '[0-100]', 'hrd': '[0-100]'}
        assert all(m['demo'] for m in first.report.biomarkers)

    def test_thirty_patients_have_all_statuses_history_and_pagination(self):
        result = self.seed()
        assert result == {'created': 30, 'existing': 0}
        assert ReportRecord.objects.count() == ReportGrant.objects.count() == 30
        self.client.force_login(self.user)
        pages = [self.client.get('/reports/'), self.client.get('/reports/?page=2')]
        assert all(page.status_code == 200 for page in pages)
        entries = [entry for page in pages for entry in page.context['entries']]
        assert len(entries) == 30
        assert Counter(entry['status'] for entry in entries) == {
            'un-reviewed': 10, 'under-review': 10, 'reviewed': 10}
        assert b'30 available' in pages[0].content
        assert max(len(entry['revisions']) for entry in entries) >= 4
        for entry in entries:
            for saved in entry['revisions']:
                if saved.revision > 1:
                    assert ReviewAudit.objects.filter(report_id=entry['reportId'], revision=saved.revision).exists()
        assert {'PASS', 'CONDITIONAL', 'FAIL', 'NOT_REVIEWED'} <= {
            entry['revisions'][0].review_data['runQcAssessment']['status'] for entry in entries}

    def test_rerun_preserves_edited_reviews_and_only_adds_missing_patients(self):
        self.seed(6)
        saved = ReviewRevision.objects.filter(revision=2).first()
        saved.review_data['notes']['summary'] = 'Manual edit must survive a seed rerun.'
        saved.save()
        before = list(ReviewRevision.objects.order_by('report_id', 'revision').values())
        assert self.seed(8) == {'created': 2, 'existing': 6}
        after = list(ReviewRevision.objects.filter(report_id__in={r['report_id'] for r in before})
                     .order_by('report_id', 'revision').values())
        assert before == after
        assert ReportRecord.objects.count() == 8

    def test_colliding_non_synthetic_report_rolls_back_entire_batch(self):
        from pronto_web.reports.synthetic_demo import build_synthetic_case
        collision = build_synthetic_case(2, seed=20261001).report.report_id
        ReportRecord.objects.create(report_id=collision, report_data={'source': 'keep untouched'})
        with self.assertRaises(CommandError):
            self.seed(6)
        assert ReportRecord.objects.count() == 1
        assert ReportRecord.objects.get().report_data == {'source': 'keep untouched'}
        assert not ReviewRevision.objects.exists()

    def test_limits_and_non_demo_principals_are_rejected_without_writes(self):
        for count, seed in ((0, 1), (201, 1), (True, 1), (2, -1), (2, True)):
            with self.assertRaises(CommandError):
                self.seed(count, seed)
        self.user.is_superuser = True
        self.user.save()
        with self.assertRaises(CommandError):
            self.seed(2)
        assert not ReportRecord.objects.exists()

    def test_seeded_reports_history_plots_and_pdfs_open_through_loopback_demo(self):
        self.seed(6)
        identifiers = list(ReportRecord.objects.values_list('report_id', flat=True))
        with override_settings(PRONTO_DEMO_ENABLED=True, PRONTO_DEMO_REPORTS=identifiers,
                PRONTO_DEMO_USER_ID=self.user.pk, PRONTO_REQUIRE_INITIALS=True,
                MIDDLEWARE=[*settings.MIDDLEWARE, 'pronto_web.reports.demo_access.DemoAccessMiddleware']):
            client = Client(HTTP_HOST='127.0.0.1')
            for identifier in identifiers:
                response = client.get(f'/reports/{identifier}/')
                assert response.status_code == 200
                assert b'class="demo-notice"' not in response.content
                assert b'Local demonstration' not in response.content
                assert b'Mixed-sample demonstration' not in response.content
            final = ReviewRevision.objects.filter(review_data__status='FINAL').first()
            historical = client.get(f'/reports/{final.report_id}/?revision=1')
            assert historical.status_code == 200 and b'Read-only export' in historical.content
            from uuid import uuid4
            for layout in ('ESMO', 'PRESENTATION'):
                pdf = client.post(f'/reports/{final.report_id}/pdf-exports/', json.dumps({
                    'schemaVersion': '1.0', 'reportId': final.report_id, 'revision': final.revision,
                    'requestId': str(uuid4()), 'declaredInitials': 'SM', 'layout': layout,
                }), content_type='application/json')
                assert pdf.status_code == 200
                text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
                assert 'Synthetic demonstration' not in text
                from pronto_report.renderers.report_pdf import project_report_export
                from pronto_report.validation import validate_report_data, validate_review_state
                report = validate_report_data(final.report.report_data)
                review = validate_review_state(final.review_data, report=report)
                summary = project_report_export(report, review)['notes']['summary']
                assert ' '.join(summary.split()) in ' '.join(text.split())
                assert final.review_data['notes']['summary'].startswith('Synthetic demonstration')
