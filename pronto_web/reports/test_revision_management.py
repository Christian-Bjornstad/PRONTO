from copy import deepcopy
from django.test import TestCase
from .models import HiddenRevision, ReviewRevision, AdministrationEvent
from .user_management import create_installation_admin


class RevisionManagementTests(TestCase):
    def setUp(self):
        from .tests_draft_save import DraftSaveTests
        from .models import ReportGrant
        DraftSaveTests.setUp(self)
        self.admin = create_installation_admin('manager', 'test-manager-8842')
        ReportGrant.objects.create(report=self.record, user=self.admin)
        for revision in (2, 3):
            data = deepcopy(self.record.reviews.first().review_data)
            data['revision'] = revision
            ReviewRevision.objects.create(report=self.record, revision=revision, review_data=data)
        self.url = f'/reports/{self.record.pk}/history/'
        self.client.force_login(self.admin)

    def test_only_administrator_can_hide_redundant_drafts_and_restore(self):
        self.client.force_login(self.writer)
        self.assertEqual(self.client.post(self.url, {'action':'HIDE','revision':2}).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(self.url, {'action':'HIDE','revision':2}).status_code, 302)
        self.assertEqual(HiddenRevision.objects.count(), 1)
        index = self.client.get('/reports/').content.decode()
        self.assertNotIn('?revision=2', index)
        self.assertEqual(ReviewRevision.objects.count(), 3)
        self.assertEqual(self.client.post(self.url, {'action':'RESTORE','revision':2}).status_code, 302)
        self.assertFalse(HiddenRevision.objects.exists())
        self.assertEqual(AdministrationEvent.objects.filter(action__endswith='REVISION').count(), 2)

    def test_current_and_final_revisions_are_preserved(self):
        self.client.post(self.url, {'action':'HIDE','revision':3})
        row = ReviewRevision.objects.get(revision=2)
        row.review_data['status'] = 'FINAL'
        row.save()
        self.client.post(self.url, {'action':'HIDE','revision':2})
        self.assertFalse(HiddenRevision.objects.exists())
