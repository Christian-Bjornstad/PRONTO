"""Cleanup never removes live uploads or anything outside private staging."""

from datetime import timedelta
from io import BytesIO
from pathlib import Path
import os
import time

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from pronto_web.reports.alignment_commands import accept_chunk, begin_local_save
from pronto_web.reports.test_alignment_commands import command_context
from pronto_web.reports.models import SavedAlignment


def test_cleanup_removes_only_expired_staging(command_context):
    report, _, writer, _, bam, bai, _, stage = command_context
    expired = begin_local_save(writer, report, "synthetic-sample", "GRCh37", "TUMOUR_DNA",
                               "bam", {"data": bam.stat().st_size, "index": bai.stat().st_size})
    live = begin_local_save(writer, report, "synthetic-sample", "GRCh37", "NORMAL_DNA",
                            "bam", {"data": bam.stat().st_size, "index": bai.stat().st_size})
    for session in (expired, live):
        accept_chunk(writer, session.id, "data", 0, bam.stat().st_size,
                     BytesIO(bam.read_bytes()))
    expired.expires_at = timezone.now() - timedelta(seconds=1)
    expired.save(update_fields=["expires_at"])
    call_command("clean_alignment_staging", dry_run=True)
    assert (stage / expired.staging_data_key).exists()
    expired.refresh_from_db()
    assert expired.state == "OPEN"
    call_command("clean_alignment_staging")
    assert not (stage / expired.staging_data_key).exists()
    assert (stage / live.staging_data_key).exists()
    expired.refresh_from_db()
    assert expired.state == "FAILED"
    live.refresh_from_db()
    assert live.state == "OPEN"


def test_cleanup_refuses_unowned_path(command_context, tmp_path):
    report, _, writer, _, bam, bai, _, stage = command_context
    outside = tmp_path / "outside"
    outside.write_bytes(b"do not touch")
    session = begin_local_save(writer, report, "synthetic-sample", "GRCh37", "TUMOUR_DNA",
                               "bam", {"data": bam.stat().st_size, "index": bai.stat().st_size})
    session.staging_data_key = "../outside"
    session.expires_at = timezone.now() - timedelta(seconds=1)
    session.save(update_fields=["staging_data_key", "expires_at"])
    with pytest.raises(CommandError):
        call_command("clean_alignment_staging")
    assert outside.read_bytes() == b"do not touch"
    assert list(stage.iterdir()) == []


def test_reconciliation_only_removes_old_unreferenced_managed_pair(command_context):
    report, _, writer, _, _, _, root, _ = command_context
    orphan = root / ("a" * 32)
    referenced = root / ("b" * 32)
    recent = root / ("c" * 32)
    interrupted_copy = root / ("." + "d" * 32 + ".tmp")
    for directory in (orphan, referenced, recent):
        directory.mkdir()
        (directory / "data").write_bytes(b"synthetic")
        (directory / "index").write_bytes(b"index")
    interrupted_copy.mkdir()
    (interrupted_copy / "data").write_bytes(b"partial synthetic copy")
    old = time.time() - 72 * 3600
    for directory in (orphan, referenced):
        for path in (directory / "data", directory / "index", directory):
            os.utime(path, (old, old))
    for path in (interrupted_copy / "data", interrupted_copy):
        os.utime(path, (old, old))
    SavedAlignment.objects.create(
        report=report, sample_id="synthetic-sample", reference_build="GRCh37",
        role="NORMAL_DNA", format="bam", data_key=f"{referenced.name}/data",
        index_key=f"{referenced.name}/index", data_size=9, index_size=5,
        data_sha256="0" * 64, index_sha256="0" * 64, saved_by=writer,
    )
    call_command("reconcile_alignment_store")
    assert orphan.exists()
    assert interrupted_copy.exists()
    call_command("reconcile_alignment_store", delete=True)
    assert not orphan.exists()
    assert not interrupted_copy.exists()
    assert referenced.exists() and recent.exists()


def test_reconciliation_refuses_deletion_with_active_upload(command_context):
    report, _, writer, _, bam, bai, _, _ = command_context
    begin_local_save(writer, report, "synthetic-sample", "GRCh37", "TUMOUR_DNA", "bam",
                     {"data": bam.stat().st_size, "index": bai.stat().st_size})
    with pytest.raises(CommandError, match="active upload"):
        call_command("reconcile_alignment_store", delete=True)
