"""Authenticated upload protocol with synthetic BAM/BAI only."""

from pathlib import Path
from dataclasses import replace
from hashlib import sha256
import json
import sys

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto.tests.reporting.test_html_surfaces import ONE_PIXEL_PNG
from pronto_report.serialization import serialize_report_data
from pronto_web.reports.models import (ReportAsset, ReportGrant, ReportRecord,
                                       ReportWriteGrant, SavedAlignment)


FIXTURES = Path(__file__).resolve().parents[2] / "pronto" / "tests" / "reporting" / "browser" / "fixtures"


@pytest.fixture
def web_context(db, tmp_path, monkeypatch):
    from pronto_web.reports import alignment_config

    monkeypatch.setattr(alignment_config, "_supported_platform", lambda: True)
    original = build_report()
    asset = dict(original.attachments[0])
    asset.update({"name": "approved/qc.png", "mediaType": "image/png",
                  "sha256": sha256(ONE_PIXEL_PNG).hexdigest()})
    report_data = replace(original, attachments=(asset,))
    record = ReportRecord.objects.create(
        report_id=report_data.report_id,
        report_data=json.loads(serialize_report_data(report_data)),
    )
    ReportAsset.objects.create(report=record, asset_id=asset["assetId"], content=ONE_PIXEL_PNG)
    reader = get_user_model().objects.create_user(username="web-reader")
    writer = get_user_model().objects.create_user(username="web-writer")
    other = get_user_model().objects.create_user(username="web-other")
    for user in (reader, writer, other):
        ReportGrant.objects.create(report=record, user=user)
    for user in (writer, other):
        ReportWriteGrant.objects.create(report=record, user=user)
    root, stage = tmp_path / "managed", tmp_path / "staging"
    root.mkdir()
    stage.mkdir()
    reference = FIXTURES / "synthetic-chr22.fa"
    with override_settings(
        PRONTO_ALIGNMENT_STORE_ROOT=str(root), PRONTO_ALIGNMENT_STAGING_ROOT=str(stage),
        PRONTO_ALIGNMENT_POLICY_APPROVED=True,
        PRONTO_ALIGNMENT_MAX_BYTES=1024 * 1024,
        PRONTO_ALIGNMENT_MAX_INDEX_BYTES=1024 * 1024,
        PRONTO_ALIGNMENT_MIN_FREE_BYTES=0,
        PRONTO_ALIGNMENT_REFERENCE_FILES={"GRCh37": {
            "fasta": str(reference), "index": str(Path(str(reference) + ".fai")),
        }},
    ):
        yield record, report_data, reader, writer, other, root, stage


def _client(user, csrf=False):
    client = Client(enforce_csrf_checks=csrf)
    client.force_login(user)
    if csrf:
        client.get("/accounts/login/")
    return client


def _csrf(client):
    return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}


def _metadata(report):
    bam, bai = FIXTURES / "synthetic-chr22.bam", FIXTURES / "synthetic-chr22.bam.bai"
    return {
        "sampleId": report.sample["sampleId"], "referenceBuild": "GRCh37",
        "role": "TUMOUR_DNA", "format": "bam",
        "dataSize": bam.stat().st_size, "indexSize": bai.stat().st_size,
        "confirmed": True,
    }


def _start(client, report, **headers):
    return client.post(
        f"/reports/{report.report_id}/alignments/save-sessions/",
        data=json.dumps(_metadata(report)), content_type="application/json", **headers,
    )


def _put(client, report, session_id, component, content, **headers):
    request_headers = {"HTTP_CONTENT_RANGE": f"bytes 0-{len(content) - 1}/{len(content)}"}
    request_headers.update(headers)
    return client.put(
        f"/reports/{report.report_id}/alignments/save-sessions/{session_id}/{component}/",
        data=content, content_type="application/octet-stream",
        **request_headers,
    )


def test_save_start_requires_write_grant_and_csrf(web_context):
    _, report, reader, writer, _, _, stage = web_context
    reader_client = _client(reader)
    assert _start(reader_client, report).status_code == 403
    writer_client = _client(writer, csrf=True)
    assert _start(writer_client, report).status_code == 403
    assert _start(writer_client, report, HTTP_X_CSRFTOKEN="wrong").status_code == 403
    response = _start(writer_client, report, **_csrf(writer_client))
    assert response.status_code == 201
    assert response.json()["sessionId"]
    assert list(stage.iterdir()) == []


def test_chunk_checks_owner_report_range_and_quota_before_consuming_body(web_context):
    _, report, _, writer, other, _, stage = web_context
    client = _client(writer)
    session = _start(client, report).json()["sessionId"]
    bam = (FIXTURES / "synthetic-chr22.bam").read_bytes()
    assert _put(_client(other), report, session, "data", bam).status_code == 403
    assert _put(client, report, session, "data", bam, HTTP_CONTENT_RANGE="bytes 1-2/3").status_code == 416
    assert _put(client, report, session, "data", bam + b"extra").status_code in {413, 416}
    assert list(stage.iterdir()) == []
    response = _put(client, report, session, "data", bam)
    assert response.status_code == 204
    assert response["Upload-Offset"] == str(len(bam))


def test_csrf_mismatched_report_and_cancelled_partial_upload(web_context):
    record, report, _, writer, _, _, stage = web_context
    client = _client(writer, csrf=True)
    session = _start(client, report, **_csrf(client)).json()["sessionId"]
    bam = (FIXTURES / "synthetic-chr22.bam").read_bytes()
    assert _put(client, report, session, "data", bam).status_code == 403
    assert _put(client, report, session, "data", bam, **_csrf(client)).status_code == 204
    complete_url = f"/reports/{record.pk}/alignments/save-sessions/{session}/complete/"
    assert client.post(complete_url, data=json.dumps({"referenceBuild": "GRCh37"}),
                       content_type="application/json", **_csrf(client)).status_code == 400
    other_report = ReportRecord.objects.create(report_id="other-report", report_data=record.report_data)
    ReportGrant.objects.create(report=other_report, user=writer)
    ReportWriteGrant.objects.create(report=other_report, user=writer)
    wrong_url = f"/reports/{other_report.pk}/alignments/save-sessions/{session}/index/"
    bai = (FIXTURES / "synthetic-chr22.bam.bai").read_bytes()
    wrong = client.put(wrong_url, data=bai, content_type="application/octet-stream",
                       HTTP_CONTENT_RANGE=f"bytes 0-{len(bai) - 1}/{len(bai)}", **_csrf(client))
    assert wrong.status_code == 403
    cancel_url = f"/reports/{record.pk}/alignments/save-sessions/{session}/"
    assert client.delete(cancel_url).status_code == 403
    assert client.delete(cancel_url, **_csrf(client)).status_code == 204
    assert list(stage.iterdir()) == []
    assert SavedAlignment.objects.count() == 0


def test_upload_rejects_malformed_ranges_and_unconfirmed_start(web_context):
    from pronto_web.reports.alignment_ranges import RangeNotSatisfiable, parse_upload_range
    from pronto_web.reports.alignment_commands import MAX_CHUNK_BYTES

    _, report, _, writer, _, _, stage = web_context
    client = _client(writer)
    payload = _metadata(report)
    payload["confirmed"] = False
    assert client.post(f"/reports/{report.report_id}/alignments/save-sessions/",
                       data=json.dumps(payload), content_type="application/json").status_code == 400
    session = _start(client, report).json()["sessionId"]
    bam = (FIXTURES / "synthetic-chr22.bam").read_bytes()
    for header in ("bytes 0-1/*", "bytes 0-99/4", "bytes 0-1/4, 2-3/4", "bytes 2-1/4"):
        assert _put(client, report, session, "data", bam,
                    HTTP_CONTENT_RANGE=header).status_code == 416
    with pytest.raises(RangeNotSatisfiable):
        parse_upload_range(f"bytes 0-{MAX_CHUNK_BYTES}/{MAX_CHUNK_BYTES + 1}", MAX_CHUNK_BYTES)
    assert _put(client, report, session, "data", bam,
                HTTP_CONTENT_RANGE=f"bytes 0-{len(bam) - 2}/{len(bam)}").status_code == 416
    assert list(stage.iterdir()) == []


@pytest.mark.skipif(sys.platform == "win32", reason="pysam validation is Linux-only")
def test_complete_reopen_saved_range_and_delete(web_context):
    record, report, reader, writer, _, root, _ = web_context
    client = _client(writer)
    session = _start(client, report).json()["sessionId"]
    bam = (FIXTURES / "synthetic-chr22.bam").read_bytes()
    bai = (FIXTURES / "synthetic-chr22.bam.bai").read_bytes()
    assert _put(client, report, session, "data", bam).status_code == 204
    assert _put(client, report, session, "index", bai).status_code == 204
    complete_url = f"/reports/{record.pk}/alignments/save-sessions/{session}/complete/"
    complete = client.post(complete_url, data=json.dumps({"referenceBuild": "GRCh37"}),
                           content_type="application/json")
    assert complete.status_code == 201
    assert client.post(complete_url, data=json.dumps({"referenceBuild": "GRCh37"}),
                       content_type="application/json").status_code == 200
    saved_id = complete.json()["savedId"]
    source_id = f"saved-{saved_id.replace('-', '')}"
    data_url = f"/reports/{record.pk}/alignments/{source_id}/data/"
    response = _client(reader).get(data_url, HTTP_RANGE="bytes=0-3")
    assert response.status_code == 206
    assert b"".join(response.streaming_content) == bam[:4]
    stranger = get_user_model().objects.create_user(username="web-stranger")
    assert _client(stranger).get(data_url, HTTP_RANGE="bytes=0-3").status_code == 404
    assert source_id.encode() in _client(reader).get(f"/reports/{record.pk}/").content
    assert client.delete(f"/reports/{record.pk}/alignments/{saved_id}/").status_code == 204
    assert not SavedAlignment.objects.filter(pk=saved_id).exists()
    assert list(root.iterdir()) == []
    assert _client(reader).get(data_url, HTTP_RANGE="bytes=0-3").status_code == 404


@pytest.mark.skipif(sys.platform == "win32", reason="pysam validation is Linux-only")
def test_registered_preserve_needs_confirmation_and_keeps_original(web_context, tmp_path):
    record, report, reader, writer, _, root, _ = web_context
    bam = FIXTURES / "synthetic-chr22.bam"
    bai = FIXTURES / "synthetic-chr22.bam.bai"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "sources": [{
        "id": "http-source", "reportId": record.pk,
        "sampleId": report.sample["sampleId"], "referenceBuild": "GRCh37",
        "role": "TUMOUR_DNA", "format": "bam", "data": bam.name,
        "index": bai.name,
    }]}), encoding="utf-8")
    url = f"/reports/{record.pk}/alignments/http-source/preserve/"
    with override_settings(PRONTO_ALIGNMENT_SOURCE_ROOT=str(FIXTURES),
                           PRONTO_ALIGNMENT_REGISTRY_JSON=str(manifest)):
        assert _client(reader).post(url, data=json.dumps({"confirmed": True}),
                                    content_type="application/json").status_code == 403
        client = _client(writer)
        assert client.post(url, data=json.dumps({"confirmed": False}),
                           content_type="application/json").status_code == 400
        response = client.post(url, data=json.dumps({"confirmed": True}),
                               content_type="application/json")
        assert response.status_code == 201
        assert len(list(root.iterdir())) == 1
        assert bam.exists() and bai.exists()
