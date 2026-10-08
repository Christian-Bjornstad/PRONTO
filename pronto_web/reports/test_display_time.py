from django.conf import settings
from django.test import TestCase

from pronto_web.reports.models import ReviewRevision


class OsloTimeTests(TestCase):
    def setUp(self):
        from pronto_web.reports.tests_draft_save import DraftSaveTests
        DraftSaveTests.setUp(self)
        self.client.force_login(self.writer)

    def test_oslo_is_default_and_storage_remains_timezone_aware(self):
        assert settings.TIME_ZONE == 'Europe/Oslo'
        assert settings.USE_TZ is True

    def test_index_formats_latest_save_and_version_history_without_rewriting_json(self):
        revision = ReviewRevision.objects.get(report=self.record, revision=1)
        revision.review_data['updatedAt'] = '2026-01-15T12:00:00Z'
        revision.save(update_fields=['review_data'])
        second = {**revision.review_data, 'revision': 2, 'updatedAt': '2026-07-15T12:00:00Z'}
        ReviewRevision.objects.create(report=self.record, revision=2, review_data=second)
        response = self.client.get('/reports/')
        assert response.status_code == 200
        assert response.content.count(b'15.07.2026 14:00:00 CEST') == 2
        assert b'15.01.2026 13:00:00 CET' in response.content
        revision.refresh_from_db()
        assert revision.review_data['updatedAt'] == '2026-01-15T12:00:00Z'
