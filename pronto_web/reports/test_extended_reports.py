import json
from io import BytesIO
from uuid import uuid4
from unittest.mock import patch

from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from pypdf import PdfReader

from pronto_report.migration import migrate_review_state_to_v3
from pronto_report.serialization import serialize_review_state
from pronto_web.reports.models import ReviewRevision


class ExtendedReportTests(TestCase):
    def setUp(self):
        from pronto_web.reports.tests_draft_save import DraftSaveTests
        DraftSaveTests.setUp(self)
        self.draft=json.loads(serialize_review_state(migrate_review_state_to_v3(self.review)))
        ReviewRevision.objects.filter(report=self.record).update(review_data=self.draft)
        self.client.force_login(self.writer)

    def image(self):
        output=BytesIO();Image.new('RGB',(320,160),'green').save(output,'PNG')
        return SimpleUploadedFile('pathway.png',output.getvalue(),content_type='image/png')

    def export(self,layout,revision=1,request_id=None):
        return self.client.post(f'/reports/{self.report.report_id}/pdf-exports/',
            json.dumps({'schemaVersion':'1.0','reportId':self.report.report_id,'revision':revision,
                'requestId':request_id or str(uuid4()),'declaredInitials':'AB','layout':layout}),content_type='application/json')

    def test_upload_save_export_figures_only_at_end_of_presentation_and_historical_read(self):
        url=f'/reports/{self.report.report_id}/figures/'
        response=self.client.post(url,{'image':self.image()})
        assert response.status_code==201
        figure=response.json();identifier=figure['figureId']
        assert self.client.get(figure['url']).status_code==200
        outsider=Client();outsider.force_login(self.other)
        assert outsider.get(figure['url']).status_code==404
        self.draft['presentationFigures']=[{'figureId':identifier,'caption':'Pathway figure appendix'}]
        saved=self.client.post(self.url,json.dumps({'schemaVersion':'1.0','reportId':self.report.report_id,
            'baseRevision':1,'draft':self.draft}),content_type='application/json')
        assert saved.status_code==201
        presentation=self.export('PRESENTATION',2);esmo=self.export('ESMO',2)
        assert presentation.status_code==esmo.status_code==200
        pages=PdfReader(BytesIO(presentation.content)).pages
        assert 'Pathway figure appendix' in pages[-1].extract_text()
        assert float(pages[0].mediabox.width)>float(pages[0].mediabox.height)
        assert 'Pathway figure appendix' not in ''.join(p.extract_text() for p in PdfReader(BytesIO(esmo.content)).pages)
        with patch('pronto_web.reports.views.load_plot_images_from_bytes',return_value={}):
            history=self.client.get(f'/reports/{self.report.report_id}/?revision=1')
        assert history.status_code==200 and b'Read-only export' in history.content
        assert b'data-save-url' not in history.content
        assert ReviewRevision.objects.filter(report=self.record).count()==2

    def test_invalid_figures_and_foreign_references_are_rejected(self):
        invalid=self.client.post(f'/reports/{self.report.report_id}/figures/',{'image':SimpleUploadedFile('x.svg',b'<svg/>')})
        assert invalid.status_code==422
        self.draft['presentationFigures']=[{'figureId':str(uuid4()),'caption':'forged'}]
        result=self.client.post(self.url,json.dumps({'schemaVersion':'1.0','reportId':self.report.report_id,
            'baseRevision':1,'draft':self.draft}),content_type='application/json')
        assert result.status_code==422
        assert ReviewRevision.objects.filter(report=self.record).count()==1

    def test_uploaded_jpeg_metadata_is_removed_from_private_png(self):
        image=Image.new('RGB',(120,60),'green');exif=Image.Exif();exif[315]='PRIVATE_AUTHOR_METADATA'
        output=BytesIO();image.save(output,'JPEG',exif=exif)
        response=self.client.post(f'/reports/{self.report.report_id}/figures/',{
            'image':SimpleUploadedFile('pathway.jpg',output.getvalue(),content_type='image/jpeg')})
        assert response.status_code==201
        payload=self.client.get(response.json()['url']).content
        with Image.open(BytesIO(payload)) as decoded:
            assert not decoded.getexif()
            assert 'exif' not in decoded.info

    def test_large_scientific_plot_is_scaled_within_stored_pixel_limit(self):
        image=Image.new('RGB',(5000,3500),'green');output=BytesIO();image.save(output,'PNG')
        response=self.client.post(f'/reports/{self.report.report_id}/figures/',{
            'image':SimpleUploadedFile('large-pathway.png',output.getvalue(),content_type='image/png')})
        assert response.status_code==201
        with Image.open(BytesIO(self.client.get(response.json()['url']).content)) as decoded:
            assert decoded.width*decoded.height<=16_000_000
            assert abs(decoded.width/decoded.height-5000/3500)<0.01

    def test_pdf_audit_retry_and_failed_render_are_transactional(self):
        from pronto_web.reports.models import ReportPdfExportAudit
        identifier=str(uuid4())
        assert self.export('ESMO',request_id=identifier).status_code==200
        assert self.export('ESMO',request_id=identifier).status_code==200
        assert ReportPdfExportAudit.objects.count()==1
        assert self.export('PRESENTATION',request_id=identifier).status_code==409
        assert self.export('ESMO',2).status_code==409
        with patch('pronto_web.reports.pdf_export.render_report_pdf',side_effect=ValueError('failure')):
            assert self.export('ESMO').status_code==503
        assert ReportPdfExportAudit.objects.count()==1

    def test_pdf_request_rejects_non_string_request_id_without_server_error(self):
        for value in (123,True,[],{}):
            response=self.client.post(f'/reports/{self.report.report_id}/pdf-exports/',json.dumps({
                'schemaVersion':'1.0','reportId':self.report.report_id,'revision':1,'requestId':value,
                'declaredInitials':'AB','layout':'ESMO'}),content_type='application/json')
            assert response.status_code==422

    def test_index_shows_patient_status_and_saved_revision_choices(self):
        response=self.client.get('/reports/')
        assert response.status_code==200 and b'un-reviewed' in response.content
        assert self.report.sample['sampleId'].encode() in response.content
        assert b'revision=1' in response.content
        saved=self.client.post(self.url,json.dumps({'schemaVersion':'1.0','reportId':self.report.report_id,
            'baseRevision':1,'draft':self.draft}),content_type='application/json')
        assert saved.status_code==201
        assert b'under-review' in self.client.get('/reports/').content
        assert self.report.report_id.encode() not in Client().get('/reports/').content

    def test_report_without_saved_review_opens_without_export_actions(self):
        ReviewRevision.objects.filter(report=self.record).delete()
        with patch('pronto_web.reports.views.load_plot_images_from_bytes',return_value={}):
            response=self.client.get(f'/reports/{self.report.report_id}/')
        assert response.status_code==200
        assert b'data-pdf-layout="' not in response.content
        assert b'id="html-export-btn"' not in response.content
        assert self.report.sample['sampleId'].encode() in response.content

    def test_legacy_classification_is_readonly_and_final_status_is_reviewed(self):
        activity=self.draft['variantReviews'][0]
        assert activity['legacyClinicalClassification']=='PATHOGENIC'
        activity['legacyClinicalClassification']='OTHER'
        payload={'schemaVersion':'1.0','reportId':self.report.report_id,'baseRevision':1,'draft':self.draft}
        assert self.client.post(self.url,json.dumps(payload),content_type='application/json').status_code==422
        activity['legacyClinicalClassification']='PATHOGENIC'
        saved=self.client.post(self.url,json.dumps(payload),content_type='application/json')
        assert saved.status_code==201
        draft=saved.json()['review']
        final=self.client.post(f'/reports/{self.report.report_id}/finalizations/',json.dumps({
            'schemaVersion':'1.0','reportId':self.report.report_id,'baseRevision':2,'draft':draft}),content_type='application/json')
        assert final.status_code==201
        assert b'class="status reviewed">reviewed' in self.client.get('/reports/').content
        assert self.client.post(f'/reports/{self.report.report_id}/figures/',{'image':self.image()}).status_code==409
