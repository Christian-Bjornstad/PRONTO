"""Authenticated read-path tests using approved, non-sensitive report fixtures."""

import json
from dataclasses import replace
from hashlib import sha256

from django.contrib.auth import get_user_model
from django.test import TestCase

from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_html_surfaces import ONE_PIXEL_PNG
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.migration import migrate_review_state_v1
from pronto_report.serialization import serialize_report_data, serialize_review_state
from pronto_web.reports.models import ReportAsset, ReportGrant, ReportRecord, ReviewRevision


class ReportReadTests(TestCase):
    def setUp(self):
        source = build_report()
        asset = dict(source.attachments[0])
        asset.update({"name": "approved/qc.png", "mediaType": "image/png", "sha256": sha256(ONE_PIXEL_PNG).hexdigest()})
        self.report = replace(source, attachments=(asset,))
        self.review = migrate_review_state_v1(draft_review(self.report))
        self.record = ReportRecord.objects.create(
            report_id=self.report.report_id,
            report_data=json.loads(serialize_report_data(self.report)),
        )
        ReviewRevision.objects.create(
            report=self.record, revision=self.review.revision,
            review_data=json.loads(serialize_review_state(self.review)),
        )
        ReportAsset.objects.create(report=self.record, asset_id=asset["assetId"], content=ONE_PIXEL_PNG)
        self.biologist = get_user_model().objects.create_user(username="biologist", password="local-test-only")
        self.other = get_user_model().objects.create_user(username="other", password="local-test-only")
        ReportGrant.objects.create(report=self.record, user=self.biologist)
        self.url = f"/reports/{self.report.report_id}/"

    def test_anonymous_and_ungranted_users_cannot_read_report_or_embedded_asset(self):
        anonymous = self.client.get(self.url)
        assert anonymous.status_code == 401
        assert ONE_PIXEL_PNG not in anonymous.content

        self.client.force_login(self.other)
        forbidden = self.client.get(self.url)
        assert forbidden.status_code == 404
        assert b"data:image/png" not in forbidden.content
        assert b"review-state-data" not in forbidden.content

    def test_authorized_user_sees_validated_report_and_latest_review_in_reference_ui(self):
        newer = json.loads(serialize_review_state(self.review))
        newer["revision"] += 1
        newer["notes"]["summary"] = "Siste lagrede vurdering"
        ReviewRevision.objects.create(report=self.record, revision=newer["revision"], review_data=newer)
        self.client.force_login(self.biologist)

        response = self.client.get(self.url)

        assert response.status_code == 200
        assert b"InPreD" in response.content
        assert b"Siste lagrede vurdering" in response.content
        assert b"Revisjon 2" in response.content
        assert b"data:image/png;base64," in response.content
        assert b'id="igv-panel"' in response.content
        assert b'id="save-btn"' not in response.content
        assert b'<style>' in response.content
        assert response["Cache-Control"] == "no-store"

    def test_no_write_route_is_exposed_in_read_slice(self):
        self.client.force_login(self.biologist)
        assert self.client.post(self.url).status_code == 405

    def test_session_login_allows_only_granted_user_to_read(self):
        login = self.client.get("/accounts/login/")
        assert login.status_code == 200
        assert b"csrfmiddlewaretoken" in login.content
        response = self.client.post("/accounts/login/", {
            "username": "biologist", "password": "local-test-only", "next": self.url,
        })
        assert response.status_code == 302
        assert response["Location"] == self.url
        assert self.client.get(self.url).status_code == 200

    def test_report_index_lists_only_granted_reports(self):
        assert self.client.get("/reports/").status_code == 401
        self.client.force_login(self.other)
        hidden = self.client.get("/reports/")
        assert hidden.status_code == 200
        assert self.report.report_id.encode() not in hidden.content
        self.client.force_login(self.biologist)
        visible = self.client.get("/reports/")
        assert visible.status_code == 200
        assert self.report.report_id.encode() in visible.content

    def test_mismatched_stored_report_or_review_revision_is_not_rendered(self):
        self.client.force_login(self.biologist)
        wrong_report = dict(self.record.report_data)
        wrong_report["reportId"] = "another-report"
        self.record.report_data = wrong_report
        self.record.save(update_fields=["report_data"])
        with self.assertRaises(ValueError):
            self.client.get(self.url)

        self.record.report_data = json.loads(serialize_report_data(self.report))
        self.record.save(update_fields=["report_data"])
        stored_review = ReviewRevision.objects.get(report=self.record)
        stored_review.revision = 2
        stored_review.save(update_fields=["revision"])
        with self.assertRaises(ValueError):
            self.client.get(self.url)
