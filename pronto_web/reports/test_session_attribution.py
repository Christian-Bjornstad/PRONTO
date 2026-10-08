import json
from io import BytesIO
from uuid import uuid4
from django.test import TestCase, override_settings
from pypdf import PdfReader

from pronto_web.reports import tests_draft_save
from pronto_web.reports.models import ReviewAudit, ReportPdfExportAudit


@override_settings(PRONTO_REQUIRE_INITIALS=False)
class SessionAttributionTests(TestCase):
    setUp = tests_draft_save.DraftSaveTests.setUp
    payload = tests_draft_save.DraftSaveTests.payload
    post = tests_draft_save.DraftSaveTests.post

    def test_save_reset_and_finalize_use_session_identity_without_initials(self):
        self.client.force_login(self.writer)
        response = self.post(self.client, self.payload())
        assert response.status_code == 201
        review = response.json()['review']
        identity = {'actorId': str(self.writer.pk), 'actorLabel': self.writer.username, 'method': 'AUTHENTICATED'}
        assert review['lastSavedAttribution'] == identity
        reset = self.client.post(f'/reports/{self.report.report_id}/resets/', json.dumps({
            'schemaVersion': '1.0', 'reportId': self.report.report_id, 'baseRevision': 2,
        }), content_type='application/json')
        assert reset.status_code == 201
        review = reset.json()['review']
        assert review['lastSavedAttribution'] == identity
        finalized = self.client.post(f'/reports/{self.report.report_id}/finalizations/', self.payload(
            baseRevision=3, draft=review, declaredInitials='ZZ'), content_type='application/json')
        assert finalized.status_code == 201
        assert finalized.json()['review']['finalizationAttribution'] == identity
        assert set(ReviewAudit.objects.values_list('attribution_method', flat=True)) == {'AUTHENTICATED'}
        assert not ReviewAudit.objects.exclude(declared_initials=None).exists()

    def test_pdf_uses_session_identity_and_cannot_be_impersonated_by_initials(self):
        self.client.force_login(self.writer)
        for layout in ('ESMO', 'PRESENTATION'):
            command = {'schemaVersion': '1.0', 'reportId': self.report.report_id, 'revision': 1,
                       'requestId': str(uuid4()), 'layout': layout, 'declaredInitials': 'ZZ'}
            response = self.client.post(f'/reports/{self.report.report_id}/pdf-exports/', json.dumps(command), content_type='application/json')
            assert response.status_code == 200
            text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
            assert self.writer.username in text
            event = ReportPdfExportAudit.objects.get(request_id=command['requestId'])
            assert event.actor_id == self.writer.pk and event.actor_label == self.writer.username
            assert event.declared_initials is None and event.attribution_method == 'AUTHENTICATED'
            assert self.client.post(f'/reports/{self.report.report_id}/pdf-exports/', json.dumps(command), content_type='application/json').status_code == 200

    def test_synthetic_immutable_imported_note_survives_a_clean_ui_save(self):
        from pronto_web.reports.synthetic_data import build_synthetic_case
        from pronto_report.renderers.display_copy import presentation_copy
        case = build_synthetic_case(4, seed=20261001)
        _, shown = presentation_copy(case.report, case.prepared_review)
        assert shown.notes['importedLegacyNote'] == case.prepared_review.notes['importedLegacyNote']

    def test_synthetic_display_cleanup_does_not_change_saved_command_payload(self):
        import re
        from unittest.mock import patch
        from pronto_web.reports.synthetic_data import build_synthetic_case
        from pronto_report.serialization import serialize_report_data, serialize_review_state
        from pronto_web.reports.models import ReportRecord, ReviewRevision, ReportGrant
        case = build_synthetic_case(4, seed=20261001)
        record = ReportRecord.objects.create(report_id=case.report.report_id,
            report_data=json.loads(serialize_report_data(case.report)))
        saved = json.loads(serialize_review_state(case.prepared_review))
        ReviewRevision.objects.create(report=record, revision=saved['revision'], review_data=saved)
        ReportGrant.objects.create(report=record, user=self.writer)
        self.client.force_login(self.writer)
        with patch('pronto_web.reports.views.load_plot_images_from_bytes', return_value={}):
            response = self.client.get(f'/reports/{record.pk}/')
        assert response.status_code == 200
        match = re.search(r'<script type="application/json" id="review-state-data">(.*?)</script>', response.content.decode(), re.S)
        draft = json.loads(match[1])
        assert draft == saved
        finalized = self.client.post(f'/reports/{record.pk}/finalizations/', json.dumps({
            'schemaVersion':'1.0', 'reportId':record.pk, 'baseRevision':saved['revision'], 'draft':draft,
        }), content_type='application/json')
        assert finalized.status_code == 201
        assert finalized.json()['review']['finalizationAttribution']['actorLabel'] == self.writer.username
