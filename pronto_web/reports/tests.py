"""Authenticated read-path tests using approved, non-sensitive report fixtures."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_html_surfaces import ONE_PIXEL_PNG
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.migration import migrate_review_state_v1
from pronto_report.serialization import serialize_report_data, serialize_review_state
from pronto_web.reports.models import (AlignmentUploadSession, ReportAsset, ReportGrant,
                                       ReportRecord, ReportWriteGrant, ReviewRevision, SavedAlignment)


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
        assert b'data-save-url="' in response.content
        assert b"data:image/png;base64," in response.content
        assert b'id="save-btn"' in response.content
        assert "csrftoken" in response.cookies
        assert b'id="igv-panel"' in response.content
        assert b"connect-src &#x27;self&#x27;" in response.content
        assert b'<style>' in response.content
        assert response["Cache-Control"] == "no-store"

    def test_report_contains_registered_igv_descriptor_without_physical_paths(self):
        self.client.force_login(self.biologist)
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert b'id="igv-sources"' in response.content
        assert b'id="igv-references"' in response.content

    def test_no_write_route_is_exposed_in_read_slice(self):
        self.client.force_login(self.biologist)
        assert self.client.post(self.url).status_code == 405

    def test_final_report_is_read_only_and_displays_signer(self):
        final = json.loads(serialize_review_state(self.review))
        final.update({
            "status": "FINAL", "revision": 2,
            "updatedAt": "2026-09-22T13:00:00Z",
            "finalizedAt": "2026-09-22T13:00:00Z",
            "finalizedBy": str(self.biologist.pk),
        })
        ReviewRevision.objects.create(report=self.record, revision=2, review_data=final)
        self.client.force_login(self.biologist)

        response = self.client.get(self.url)

        assert response.status_code == 200
        assert b"Rapportstatus: Endelig" in response.content
        assert f"Ferdigstilt av {self.biologist.pk}".encode() in response.content
        assert b'id="finalize-btn"' not in response.content
        assert b'id="save-btn" type="button" disabled' in response.content
        assert b'id="igv-panel"' in response.content
        assert b'data-review-field="reportingDecision" disabled' in response.content

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


class AlignmentRangeTests(ReportReadTests):
    def setUp(self):
        super().setUp()
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.source_root = root
        self.data = b"0123456789"
        (root / "tumour.bam").write_bytes(self.data)
        (root / "tumour.bam.bai").write_bytes(b"INDEX")
        manifest = root / "registry.json"
        manifest.write_text(json.dumps({"version": 1, "sources": [{
            "id": "tumour", "reportId": self.report.report_id,
            "sampleId": self.report.sample["sampleId"],
            "referenceBuild": self.report.sample["referenceBuild"],
            "role": "TUMOUR_DNA", "format": "bam", "data": "tumour.bam",
            "index": "tumour.bam.bai",
        }]}), encoding="utf-8")
        settings_override = override_settings(
            PRONTO_ALIGNMENT_SOURCE_ROOT=str(root),
            PRONTO_ALIGNMENT_REGISTRY_JSON=str(manifest),
        )
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        self.range_url = f"/reports/{self.report.report_id}/alignments/tumour/data/"

    def test_registered_source_is_offered_without_physical_path(self):
        self.client.force_login(self.biologist)
        response = self.client.get(self.url)
        assert b'"sourceId":"tumour"' in response.content
        assert str(self.source_root).encode() not in response.content

    def test_broken_registry_is_not_misreported_as_absent(self):
        self.client.force_login(self.biologist)
        with override_settings(PRONTO_ALIGNMENT_REGISTRY_JSON=str(self.source_root / "missing.json")):
            response = self.client.get(self.url)
        assert response.status_code == 200
        assert b"Registrerte IGV-kilder er utilgjengelige" in response.content
        assert str(self.source_root).encode() not in response.content

    def test_authorized_ranges_and_headers(self):
        self.client.force_login(self.biologist)
        for header, expected, content_range in [
            ("bytes=0-1", b"01", "bytes 0-1/10"),
            ("bytes=2-5", b"2345", "bytes 2-5/10"),
            ("bytes=8-", b"89", "bytes 8-9/10"),
        ]:
            response = self.client.get(self.range_url, HTTP_RANGE=header)
            assert response.status_code == 206
            assert response["Content-Range"] == content_range
            assert response["Content-Length"] == str(len(expected))
            assert response["Accept-Ranges"] == "bytes"
            assert response["Cache-Control"] == "no-store"
            assert response["X-Content-Type-Options"] == "nosniff"
            assert response["Content-Type"] == "application/octet-stream"
            assert b"".join(response.streaming_content) == expected

    def test_index_can_be_read_whole_and_data_requires_range(self):
        self.client.force_login(self.biologist)
        index = self.client.get(self.range_url.replace("/data/", "/index/"))
        assert index.status_code == 200
        assert b"".join(index.streaming_content) == b"INDEX"
        missing = self.client.get(self.range_url)
        assert missing.status_code == 416
        assert missing["Content-Range"] == "bytes */10"

    def test_invalid_ranges_disclose_no_bytes(self):
        self.client.force_login(self.biologist)
        for header in ("bytes=0-1,4-5", "bytes=10-", "garbage"):
            response = self.client.get(self.range_url, HTTP_RANGE=header)
            assert response.status_code == 416
            assert response["Content-Range"] == "bytes */10"
            assert not response.content

    def test_anonymous_ungranted_and_guessed_sources(self):
        assert self.client.get(self.range_url, HTTP_RANGE="bytes=0-1").status_code == 401
        self.client.force_login(self.other)
        assert self.client.get(self.range_url, HTTP_RANGE="bytes=0-1").status_code == 404
        self.client.force_login(self.biologist)
        for url in (
            self.range_url.replace("tumour", "guessed"),
            self.range_url.replace("/data/", "/other/"),
            self.range_url.replace(self.report.report_id, "wrong-report"),
        ):
            assert self.client.get(url, HTTP_RANGE="bytes=0-1").status_code == 404

    def test_head_does_not_stream_or_reveal_data(self):
        self.client.force_login(self.biologist)
        assert self.client.head(self.range_url, HTTP_RANGE="bytes=0-1").status_code == 405

    def test_source_identity_must_still_match_stored_report(self):
        self.client.force_login(self.biologist)
        altered = dict(self.record.report_data)
        altered["sample"] = {**altered["sample"], "sampleId": "another-sample"}
        self.record.report_data = altered
        self.record.save(update_fields=["report_data"])
        assert self.client.get(self.range_url, HTTP_RANGE="bytes=0-1").status_code == 404


class AlignmentMetadataTests(TestCase):
    def setUp(self):
        self.report = ReportRecord.objects.create(report_id="synthetic-report", report_data={})
        self.reader = get_user_model().objects.create_user(username="read-only")
        self.writer = get_user_model().objects.create_user(username="save-writer")
        ReportGrant.objects.create(report=self.report, user=self.reader)

    def test_read_grant_never_implicitly_grants_alignment_write(self):
        assert not ReportWriteGrant.objects.filter(report=self.report, user=self.reader).exists()
        ReportWriteGrant.objects.create(report=self.report, user=self.writer)
        assert ReportWriteGrant.objects.filter(report=self.report, user=self.writer).exists()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReportWriteGrant.objects.create(report=self.report, user=self.writer)

    def test_ready_identity_is_unique_and_upload_offsets_are_bounded(self):
        fields = dict(report=self.report, sample_id="synthetic-sample", reference_build="GRCh37",
                      role="TUMOUR_DNA", format="bam", data_size=10, index_size=5,
                      data_sha256="a" * 64, index_sha256="b" * 64, saved_by=self.writer)
        SavedAlignment.objects.create(**fields, data_key="a" * 32, index_key="b" * 32)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SavedAlignment.objects.create(**fields, data_key="c" * 32, index_key="d" * 32)
        assert SavedAlignment.objects.filter(report=self.report, status="READY").count() == 1
        with self.assertRaises(IntegrityError), transaction.atomic():
            AlignmentUploadSession.objects.create(
                report=self.report, owner=self.writer, sample_id="synthetic-sample",
                reference_build="GRCh37", role="TUMOUR_DNA", format="bam",
                expected_data_size=10, expected_index_size=5, received_data_bytes=11,
                expires_at=timezone.now() + timedelta(hours=1),
            )
