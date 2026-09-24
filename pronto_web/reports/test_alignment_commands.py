"""Explicit save commands use only synthetic alignment fixtures."""

from io import BytesIO
from datetime import timedelta
from pathlib import Path
import json
import sys

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import override_settings
from django.utils import timezone

from pronto_web.reports.models import (
    AlignmentEvent, AlignmentUploadSession, ReportGrant, ReportRecord,
    ReportWriteGrant, SavedAlignment,
)


FIXTURES = Path(__file__).resolve().parents[2] / "pronto" / "tests" / "reporting" / "browser" / "fixtures"


@pytest.fixture
def command_context(db, tmp_path, monkeypatch):
    from pronto_web.reports import alignment_config

    monkeypatch.setattr(alignment_config, "_supported_platform", lambda: True)
    root = tmp_path / "managed"
    stage = tmp_path / "staging"
    root.mkdir()
    stage.mkdir()
    bam = FIXTURES / "synthetic-chr22.bam"
    bai = FIXTURES / "synthetic-chr22.bam.bai"
    reference = FIXTURES / "synthetic-chr22.fa"
    report = ReportRecord.objects.create(
        report_id="synthetic-report",
        report_data={"sample": {"sampleId": "synthetic-sample", "referenceBuild": "GRCh37"}},
    )
    users = [get_user_model().objects.create_user(username=name) for name in ("reader", "writer", "other")]
    reader, writer, other = users
    for user in users:
        ReportGrant.objects.create(report=report, user=user)
    for user in (writer, other):
        ReportWriteGrant.objects.create(report=report, user=user)
    overrides = override_settings(
        PRONTO_ALIGNMENT_STORE_ROOT=str(root), PRONTO_ALIGNMENT_STAGING_ROOT=str(stage),
        PRONTO_ALIGNMENT_POLICY_APPROVED=True,
        PRONTO_ALIGNMENT_MAX_BYTES=1024 * 1024,
        PRONTO_ALIGNMENT_MAX_INDEX_BYTES=1024 * 1024,
        PRONTO_ALIGNMENT_MIN_FREE_BYTES=0,
        PRONTO_ALIGNMENT_REFERENCE_FILES={"GRCh37": {
            "fasta": str(reference), "index": str(Path(str(reference) + ".fai")),
        }},
    )
    with overrides:
        yield report, reader, writer, other, bam, bai, root, stage


def _begin(writer, report, bam, bai):
    from pronto_web.reports.alignment_commands import begin_local_save

    return begin_local_save(writer, report, "synthetic-sample", "GRCh37", "TUMOUR_DNA", "bam",
                            {"data": bam.stat().st_size, "index": bai.stat().st_size})


def _upload(writer, session, bam, bai):
    from pronto_web.reports.alignment_commands import accept_chunk

    assert accept_chunk(writer, session.id, "data", 0, bam.stat().st_size,
                        BytesIO(bam.read_bytes())) == bam.stat().st_size
    assert accept_chunk(writer, session.id, "index", 0, bai.stat().st_size,
                        BytesIO(bai.read_bytes())) == bai.stat().st_size


def test_only_explicit_writer_can_begin_and_original_actor_owns_session(command_context):
    from pronto_web.reports.alignment_commands import accept_chunk

    report, reader, writer, other, bam, bai, _, stage = command_context
    with pytest.raises(PermissionDenied):
        _begin(reader, report, bam, bai)
    session = _begin(writer, report, bam, bai)
    assert SavedAlignment.objects.count() == 0
    assert list(stage.iterdir()) == []
    with pytest.raises(PermissionDenied):
        accept_chunk(other, session.id, "data", 0, bam.stat().st_size, BytesIO(bam.read_bytes()))
    assert list(stage.iterdir()) == []


@pytest.mark.skipif(sys.platform == "win32", reason="pysam validation is Linux-only")
def test_complete_pair_is_idempotent_and_other_role_is_independent(command_context):
    from hashlib import sha256
    from pronto_web.reports.alignment_commands import complete_local_save
    from pronto_web.reports.alignment_registry import lookup_saved

    report, _, writer, _, bam, bai, root, stage = command_context
    session = _begin(writer, report, bam, bai)
    _upload(writer, session, bam, bai)
    saved = complete_local_save(writer, session.id, "GRCh37")
    assert saved.data_sha256 == sha256(bam.read_bytes()).hexdigest()
    assert saved.index_sha256 == sha256(bai.read_bytes()).hexdigest()
    assert complete_local_save(writer, session.id, "GRCh37").id == saved.id
    assert SavedAlignment.objects.count() == 1
    assert AlignmentEvent.objects.filter(action="SAVE", saved_id=saved.id).count() == 1
    assert len(list(root.iterdir())) == 1
    assert list(stage.iterdir()) == []
    visible = lookup_saved(report.report_id, "synthetic-sample", "GRCh37")
    assert [pair.source_id for pair in visible] == [f"saved-{saved.id.hex}"]
    assert visible[0].data_path.read_bytes() == bam.read_bytes()


@pytest.mark.skipif(sys.platform == "win32", reason="pysam validation is Linux-only")
def test_duplicate_identical_pair_returns_existing_and_different_pair_conflicts(command_context):
    from pronto_web.reports.alignment_commands import (
        AlignmentConflict, begin_local_save, complete_local_save,
    )

    report, _, writer, _, bam, bai, root, _ = command_context
    first = _begin(writer, report, bam, bai)
    _upload(writer, first, bam, bai)
    saved = complete_local_save(writer, first.id, "GRCh37")
    second = _begin(writer, report, bam, bai)
    _upload(writer, second, bam, bai)
    assert complete_local_save(writer, second.id, "GRCh37").id == saved.id
    assert len(list(root.iterdir())) == 1
    changed = _begin(writer, report, bam, bai)
    from pronto_web.reports.alignment_commands import accept_chunk
    data = bytearray(bam.read_bytes())
    data[-1] ^= 1
    accept_chunk(writer, changed.id, "data", 0, len(data), BytesIO(data))
    accept_chunk(writer, changed.id, "index", 0, bai.stat().st_size, BytesIO(bai.read_bytes()))
    with pytest.raises(AlignmentConflict):
        complete_local_save(writer, changed.id, "GRCh37")
    mislabeled = begin_local_save(writer, report, "synthetic-sample", "GRCh37", "TUMOUR_DNA",
                                  "cram", {"data": bam.stat().st_size, "index": bai.stat().st_size})
    _upload(writer, mislabeled, bam, bai)
    with pytest.raises(AlignmentConflict):
        complete_local_save(writer, mislabeled.id, "GRCh37")
    assert SavedAlignment.objects.count() == 1


def test_expired_upload_is_rejected_and_staged_bytes_removed(command_context):
    from pronto_web.reports.alignment_commands import AlignmentSessionClosed, accept_chunk

    report, _, writer, _, bam, bai, _, stage = command_context
    session = _begin(writer, report, bam, bai)
    accept_chunk(writer, session.id, "data", 0, bam.stat().st_size, BytesIO(bam.read_bytes()))
    session.expires_at = timezone.now() - timedelta(seconds=1)
    session.save(update_fields=["expires_at"])
    with pytest.raises(AlignmentSessionClosed):
        accept_chunk(writer, session.id, "index", 0, bai.stat().st_size, BytesIO(bai.read_bytes()))
    assert list(stage.iterdir()) == []
    session.refresh_from_db()
    assert session.state == "FAILED"


def test_oversized_chunk_leaves_session_retryable(command_context):
    from pronto_web.reports.alignment_commands import StorageLimitError, accept_chunk

    report, _, writer, _, bam, bai, _, stage = command_context
    session = _begin(writer, report, bam, bai)
    with pytest.raises(StorageLimitError):
        accept_chunk(writer, session.id, "data", 0, bam.stat().st_size,
                     BytesIO(bam.read_bytes() + b"extra"))
    assert list(stage.iterdir()) == []
    assert accept_chunk(writer, session.id, "data", 0, bam.stat().st_size,
                        BytesIO(bam.read_bytes())) == bam.stat().st_size


@pytest.mark.skipif(sys.platform == "win32", reason="pysam validation is Linux-only")
def test_invalid_pair_fails_closed_and_roles_remain_separate(command_context):
    from pronto_web.reports.alignment_commands import (
        accept_chunk, begin_local_save, complete_local_save,
    )
    from pronto_web.reports.alignment_store import InvalidAlignmentPair

    report, _, writer, _, bam, bai, root, stage = command_context
    invalid = begin_local_save(writer, report, "synthetic-sample", "GRCh37", "TUMOUR_DNA",
                               "bam", {"data": 6, "index": bai.stat().st_size})
    accept_chunk(writer, invalid.id, "data", 0, 6, BytesIO(b"broken"))
    accept_chunk(writer, invalid.id, "index", 0, bai.stat().st_size, BytesIO(bai.read_bytes()))
    with pytest.raises(InvalidAlignmentPair):
        complete_local_save(writer, invalid.id, "GRCh37")
    invalid.refresh_from_db()
    assert invalid.state == "FAILED"
    assert list(stage.iterdir()) == []
    assert list(root.iterdir()) == []

    normal = begin_local_save(writer, report, "synthetic-sample", "GRCh37", "NORMAL_DNA",
                              "bam", {"data": bam.stat().st_size, "index": bai.stat().st_size})
    _upload(writer, normal, bam, bai)
    saved = complete_local_save(writer, normal.id, "GRCh37")
    assert saved.role == "NORMAL_DNA"
    assert SavedAlignment.objects.filter(role="TUMOUR_DNA").count() == 0


@pytest.mark.skipif(sys.platform == "win32", reason="pysam validation is Linux-only")
def test_registered_copy_and_delete_require_write_grant(command_context, tmp_path):
    from pronto_web.reports.alignment_commands import delete_saved, preserve_registered
    from pronto_web.reports.alignment_registry import lookup_saved

    report, reader, writer, _, bam, bai, root, _ = command_context
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "sources": [{
        "id": "synthetic-source", "reportId": report.report_id,
        "sampleId": "synthetic-sample", "referenceBuild": "GRCh37",
        "role": "TUMOUR_DNA", "format": "bam",
        "data": bam.name, "index": bai.name,
    }]}), encoding="utf-8")
    with override_settings(PRONTO_ALIGNMENT_SOURCE_ROOT=str(FIXTURES),
                           PRONTO_ALIGNMENT_REGISTRY_JSON=str(manifest)):
        with pytest.raises(PermissionDenied):
            preserve_registered(reader, report, "synthetic-source")
        saved = preserve_registered(writer, report, "synthetic-source")
        assert SavedAlignment.objects.count() == 1
        assert AlignmentEvent.objects.filter(action="COPY", saved_id=saved.id).exists()
        with pytest.raises(PermissionDenied):
            delete_saved(reader, report, saved.id)
        delete_saved(writer, report, saved.id)
        assert not SavedAlignment.objects.exists()
        assert AlignmentEvent.objects.filter(action="DELETE", saved_id=saved.id).exists()
        assert list(root.iterdir()) == []
        assert bam.exists() and bai.exists()  # registered originals are untouched
        assert lookup_saved(report.report_id, "synthetic-sample", "GRCh37") == ()


@pytest.mark.skipif(sys.platform == "win32", reason="pysam validation is Linux-only")
def test_failed_delete_hides_record_and_can_be_retried(command_context, monkeypatch):
    from pronto_web.reports import alignment_commands
    from pronto_web.reports.alignment_registry import lookup_saved

    report, _, writer, _, bam, bai, _, _ = command_context
    session = _begin(writer, report, bam, bai)
    _upload(writer, session, bam, bai)
    saved = alignment_commands.complete_local_save(writer, session.id, "GRCh37")
    original = alignment_commands.remove_pair

    def fail_once(pair):
        raise OSError("simulated managed-storage failure")

    monkeypatch.setattr(alignment_commands, "remove_pair", fail_once)
    with pytest.raises(OSError, match="simulated managed-storage failure"):
        alignment_commands.delete_saved(writer, report, saved.id)
    saved.refresh_from_db()
    assert saved.status == "DELETING"
    assert lookup_saved(report.report_id, "synthetic-sample", "GRCh37") == ()
    monkeypatch.setattr(alignment_commands, "remove_pair", original)
    alignment_commands.delete_saved(writer, report, saved.id)
    assert not SavedAlignment.objects.filter(pk=saved.id).exists()
