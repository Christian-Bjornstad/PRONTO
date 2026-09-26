from unittest.mock import patch
from django.test import TestCase, override_settings
from pronto_web.reports.tests_draft_save import DraftSaveTests
from pronto_web.reports.models import ReviewAudit, ReviewRevision


@override_settings(PRONTO_REQUIRE_INITIALS=True)
class AttributionTests(TestCase):
    setUp = DraftSaveTests.setUp
    payload = DraftSaveTests.payload
    post = DraftSaveTests.post

    def test_missing_initials_rejected_without_write(self):
        self.client.force_login(self.writer)
        response = self.post(self.client, self.payload())
        assert response.status_code == 422
        assert ReviewRevision.objects.count() == 1

    def test_saved_and_final_initials_are_separate_and_same_person_allowed(self):
        self.client.force_login(self.writer)
        saved = self.post(self.client, self.payload(declaredInitials='abø'))
        assert saved.status_code == 201
        review = saved.json()['review']
        assert review['lastSavedAttribution'] == {'declaredInitials': 'ABØ', 'method': 'SELF_REPORTED'}
        response = self.client.post(f'/reports/{self.report.report_id}/finalizations/',
            data=self.payload(baseRevision=2, draft=review, declaredInitials='abø'), content_type='application/json')
        assert response.status_code == 201
        assert response.json()['review']['finalizationAttribution']['declaredInitials'] == 'ABØ'
        assert list(ReviewAudit.objects.values_list('declared_initials', flat=True)) == ['ABØ', 'ABØ']

    def test_same_initials_do_not_merge_actors(self):
        from pronto_web.reports.models import ReportGrant
        ReportGrant.objects.create(report=self.record, user=self.other)
        self.client.force_login(self.writer)
        first = self.post(self.client, self.payload(declaredInitials='AB')).json()['review']
        self.client.force_login(self.other)
        second = self.post(self.client, self.payload(baseRevision=2, draft=first, declaredInitials='AB'))
        assert second.status_code == 201
        assert set(ReviewAudit.objects.values_list('actor_id', flat=True)) == {self.writer.pk, self.other.pk}

    def test_audit_failure_rolls_back_revision(self):
        self.client.force_login(self.writer)
        with patch('pronto_web.reports.review_repository.ReviewAudit.objects.create', side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):
                self.post(self.client, self.payload(declaredInitials='AB'))
        assert ReviewRevision.objects.count() == 1

    def test_draft_cannot_forge_saved_attribution(self):
        self.client.force_login(self.writer)
        self.draft['lastSavedAttribution'] = {'declaredInitials': 'ZZ', 'method': 'SELF_REPORTED'}
        response = self.post(self.client, self.payload(declaredInitials='AB'))
        assert response.status_code == 201
        assert response.json()['review']['lastSavedAttribution']['declaredInitials'] == 'AB'
