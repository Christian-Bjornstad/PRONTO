import json
from uuid import uuid4
from django.test import TestCase, override_settings
from pronto_web.reports.models import ReviewRevision


@override_settings(PRONTO_WORKING_DRAFTS=True)
class WorkingDraftTests(TestCase):
    def setUp(self):
        from pronto_web.reports.tests_draft_save import DraftSaveTests
        from pronto_report.review.source_defaults import upgrade_review
        from pronto_report.serialization import serialize_review_state
        DraftSaveTests.setUp(self)
        self.client.force_login(self.writer)
        self.draft = json.loads(serialize_review_state(upgrade_review(self.report, self.review)))
        self.draft['revision'] = 2
        self.working_url = f'/reports/{self.report.report_id}/working/'

    def command(self, action='SAVE', version=0, revision=2, **extra):
        body = {'schemaVersion':'2.0','reportId':self.report.report_id,'action':action,
                'baseRevision':revision,'expectedVersion':version, **extra}
        if action == 'SAVE': body['draft'] = self.draft
        return self.client.post(self.working_url, json.dumps(body),content_type='application/json')

    def test_saves_overwrite_one_draft_and_reject_stale_client(self):
        from pronto_web.reports.models import WorkingDraft
        first = self.command()
        assert first.status_code == 201
        assert first.json()['workingVersion'] == 1
        self.draft = first.json()['review']
        self.draft['notes']['summary'] = 'Updated working content'
        second = self.command(version=1)
        assert second.status_code == 201
        assert second.json()['review']['revision'] == 2
        assert WorkingDraft.objects.count() == 1
        assert ReviewRevision.objects.count() == 1
        assert self.command(version=1).status_code == 409

    def test_finalize_and_reopen_preserve_signed_content(self):
        from pronto_web.reports.models import WorkingDraft
        assert self.command().status_code == 201
        final = self.command('FINALIZE', version=1)
        assert final.status_code == 201
        assert final.json()['review']['status'] == 'FINAL'
        assert not WorkingDraft.objects.exists()
        old = ReviewRevision.objects.get(revision=2).review_data
        reopened = self.command('REOPEN', revision=2, sourceRevision=2)
        assert reopened.status_code == 201
        assert reopened.json()['review']['revision'] == 3
        assert 'finalizedAt' not in reopened.json()['review']
        assert ReviewRevision.objects.get(revision=2).review_data == old
        assert self.command(version=1,revision=2).status_code == 409

    def test_reopened_final_can_upload_presentation_figure(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
        from PIL import Image
        self.command(); self.command('FINALIZE',version=1)
        self.command('REOPEN',revision=2,sourceRevision=2)
        buffer=BytesIO();Image.new('RGB',(20,20),'white').save(buffer,'PNG')
        response=self.client.post(f'/reports/{self.report.report_id}/figures/',
                                 {'image':SimpleUploadedFile('pathway.png',buffer.getvalue(),content_type='image/png')})
        assert response.status_code == 201

    def test_index_distinguishes_working_copy_and_preserved_final(self):
        self.command(); self.command('FINALIZE',version=1)
        old=ReviewRevision.objects.get(revision=2).review_data
        self.command('REOPEN',revision=2,sourceRevision=2)
        response=self.client.get('/reports/')
        self.assertContains(response,'Working draft · revision 3')
        self.assertContains(response,'Latest finalized · revision 2')
        from unittest.mock import patch
        with patch('pronto_web.reports.views.load_plot_images_from_bytes',return_value={}):
            historical=self.client.get(f'/reports/{self.report.report_id}/?revision=2')
        self.assertContains(historical,'Finalized · revision 2')
        self.draft=self.command('RESET',version=1,revision=3).json()['review']
        self.draft['notes']['summary']='Changed in the new revision'
        assert self.command(version=2,revision=3).status_code==201
        assert self.command('FINALIZE',version=3,revision=3).status_code==201
        assert ReviewRevision.objects.get(revision=2).review_data==old
        assert ReviewRevision.objects.get(revision=3).review_data['status']=='FINAL'

    def test_start_new_revision_preserves_selected_working_draft(self):
        self.draft['notes']['summary']='Selected saved draft'
        assert self.command().status_code == 201
        response=self.command('REOPEN',version=1,sourceRevision=2,replaceWorking=True)
        assert response.status_code == 201
        assert response.json()['review']['revision']==3
        assert ReviewRevision.objects.get(revision=2).review_data['notes']['summary']=='Selected saved draft'

    def test_export_freezes_draft_and_retry_keeps_content(self):
        self.command()
        body={'schemaVersion':'1.0','reportId':self.report.report_id,'revision':2,
              'requestId':str(uuid4()),'layout':'ESMO','workingVersion':1}
        url=f'/reports/{self.report.report_id}/pdf-exports/'
        exported=self.client.post(url,json.dumps(body),content_type='application/json')
        assert exported.status_code == 200
        assert exported['X-Working-Version'] == '2'
        assert ReviewRevision.objects.filter(revision=2).exists()
        self.draft['notes']['summary']='After exported version'
        self.draft['revision']=3
        assert self.command(version=2,revision=3).status_code == 201
        retry=self.client.post(url,json.dumps(body),content_type='application/json')
        assert retry.status_code == 200
        assert 'X-Working-Version' not in retry
        assert ReviewRevision.objects.get(revision=2).review_data['notes']['summary'] != 'After exported version'

    def test_foreign_access_and_invalid_manual_ids_are_rejected(self):
        self.client.force_login(self.other)
        assert self.command().status_code == 404
        self.client.force_login(self.writer)
        self.draft['findingReviews']=[{'findingId':'unknown','reportingDecision':'INCLUDE','reportHighlight':False}]
        assert self.command().status_code == 422

    def test_unknown_figures_do_not_save(self):
        self.draft['presentationFigures']=[{'figureId':str(uuid4()),'caption':'Unknown'}]
        assert self.command().status_code == 422

    def test_invalid_action_type_is_a_validation_error(self):
        for action in ([],{},None,False):
            assert self.command(action=action).status_code == 422

    def test_non_finite_values_do_not_save(self):
        self.draft['manualCnvRows']=[{'findingId':'manual-cnv-x','geneSymbol':'MET','tumorFc':float('nan')}]
        assert self.command().status_code == 422
