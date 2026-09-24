"""Explicit, authorized lifecycle for privately retained alignment pairs."""

from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import os
import re

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .alignment_config import alignment_saving_enabled
from .alignment_registry import InvalidAlignmentRegistry, lookup_registered
from .alignment_ranges import RangeNotSatisfiable
from .alignment_store import (
    PublishedPair, StorageLimitError, UnsafeAlignmentPath, publish_pair,
    remove_pair, validate_pair,
)
from .models import (
    ALIGNMENT_BUILDS, ALIGNMENT_FORMATS, ALIGNMENT_ROLES, AlignmentEvent,
    AlignmentUploadSession, ReportWriteGrant, SavedAlignment,
)


MAX_CHUNK_BYTES = 8 * 1024 * 1024
_KEY = re.compile(r"[0-9a-f]{32}\Z")


class AlignmentConflict(ValueError):
    """A different pair already occupies the exact saved identity."""


class AlignmentSessionClosed(ValueError):
    """An upload is expired, cancelled, failed or already finalizing."""


def require_alignment_write(actor, report) -> None:
    if (not actor.is_authenticated or not actor.is_active
            or not ReportWriteGrant.objects.filter(report=report, user=actor).exists()):
        raise PermissionDenied("alignment write grant required")


def _require_gate() -> None:
    if not alignment_saving_enabled(settings):
        raise PermissionDenied("alignment saving is not configured")


def _reference(build: str) -> Path:
    pair = settings.PRONTO_ALIGNMENT_REFERENCE_FILES.get(build)
    if not pair:
        raise ValueError("local reference for build is unavailable")
    return Path(pair["fasta"])


def _stage_path(key: str) -> Path:
    if not _KEY.fullmatch(key):
        raise UnsafeAlignmentPath("invalid staging key")
    root = Path(settings.PRONTO_ALIGNMENT_STAGING_ROOT)
    if root.is_symlink() or not root.is_dir():
        raise UnsafeAlignmentPath("staging root is unavailable")
    return root.resolve(strict=True) / key


def _cleanup(session: AlignmentUploadSession) -> None:
    for key in (session.staging_data_key, session.staging_index_key):
        path = _stage_path(key)
        if path.is_symlink():
            raise UnsafeAlignmentPath("symlinked staging component")
        path.unlink(missing_ok=True)


def _identity(report, sample_id: str, build: str, role: str):
    return SavedAlignment.objects.filter(
        report=report, sample_id=sample_id, reference_build=build,
        role=role, status="READY",
    )


def _digest_file(path: Path) -> tuple[int, str]:
    digest = sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _same(existing: SavedAlignment, data: tuple[int, str], index: tuple[int, str]) -> bool:
    return (existing.data_size, existing.data_sha256, existing.index_size,
            existing.index_sha256) == (data[0], data[1], index[0], index[1])


def begin_local_save(actor, report, sample_id: str, build: str, role: str,
                     format: str, sizes: dict[str, int]) -> AlignmentUploadSession:
    require_alignment_write(actor, report)
    _require_gate()
    if (not isinstance(sample_id, str) or not sample_id or len(sample_id) > 128
            or (sample_id, build) != (report.report_data.get("sample", {}).get("sampleId"),
                                       report.report_data.get("sample", {}).get("referenceBuild"))
            or build not in dict(ALIGNMENT_BUILDS) or role not in dict(ALIGNMENT_ROLES)
            or format not in dict(ALIGNMENT_FORMATS)):
        raise ValueError("alignment identity does not match report")
    _reference(build)
    if not isinstance(sizes, dict) or set(sizes) != {"data", "index"}:
        raise ValueError("both component sizes are required")
    data_size, index_size = sizes["data"], sizes["index"]
    if (type(data_size) is not int or type(index_size) is not int
            or not 0 < data_size <= settings.PRONTO_ALIGNMENT_MAX_BYTES
            or not 0 < index_size <= settings.PRONTO_ALIGNMENT_MAX_INDEX_BYTES):
        raise StorageLimitError("component exceeds configured byte limit")
    return AlignmentUploadSession.objects.create(
        report=report, owner=actor, sample_id=sample_id, reference_build=build,
        role=role, format=format, expected_data_size=data_size,
        expected_index_size=index_size, expires_at=timezone.now() + timedelta(hours=24),
    )


def _authorized_session(actor, session_id, report=None) -> AlignmentUploadSession:
    session = AlignmentUploadSession.objects.select_for_update().select_related("report").get(pk=session_id)
    require_alignment_write(actor, session.report)
    if session.owner_id != actor.pk or (report is not None and session.report_id != report.pk):
        raise PermissionDenied("upload belongs to another actor or report")
    return session


def authorized_upload_session(actor, report, session_id) -> AlignmentUploadSession:
    """Check ownership and exact report before an HTTP handler reads any bytes."""
    session = AlignmentUploadSession.objects.select_related("report").get(pk=session_id)
    require_alignment_write(actor, session.report)
    if session.owner_id != actor.pk or session.report_id != report.pk:
        raise PermissionDenied("upload belongs to another actor or report")
    return session


def accept_chunk(actor, session_id, component: str, start: int, total: int, stream,
                 *, report=None) -> int:
    _require_gate()
    if component not in {"data", "index"}:
        raise ValueError("unknown alignment component")
    expired = False
    with transaction.atomic():
        session = _authorized_session(actor, session_id, report)
        if session.expires_at <= timezone.now():
            _cleanup(session)
            session.state = "FAILED"
            session.save(update_fields=["state"])
            expired = True
        else:
            if session.state != "OPEN":
                raise AlignmentSessionClosed("upload is not open")
            expected = getattr(session, f"expected_{component}_size")
            received_field = f"received_{component}_bytes"
            received = getattr(session, received_field)
            if type(start) is not int or type(total) is not int or start != received or total != expected:
                raise RangeNotSatisfiable("chunk range is not contiguous or total changed")
            path = _stage_path(getattr(session, f"staging_{component}_key"))
            flags = os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
            flags |= os.O_CREAT | os.O_EXCL if start == 0 else 0
            fd = os.open(path, flags, 0o600)
            try:
                if os.fstat(fd).st_size != start:
                    raise ValueError("staging offset mismatch")
                os.lseek(fd, start, os.SEEK_SET)
                count = 0
                while block := stream.read(min(1024 * 1024, MAX_CHUNK_BYTES + 1 - count)):
                    count += len(block)
                    if count > MAX_CHUNK_BYTES or start + count > expected:
                        raise StorageLimitError("chunk exceeds byte limit")
                    os.write(fd, block)
                if count == 0:
                    raise ValueError("empty chunk")
                os.fsync(fd)
            except BaseException:
                os.ftruncate(fd, start)
                os.close(fd)
                if start == 0:
                    path.unlink(missing_ok=True)
                raise
            else:
                os.close(fd)
            setattr(session, received_field, start + count)
            session.save(update_fields=[received_field])
            return start + count
    if expired:
        raise AlignmentSessionClosed("upload expired")
    raise AssertionError("upload state did not resolve")


def complete_local_save(actor, session_id, declared_build: str, *, report=None) -> SavedAlignment:
    _require_gate()
    with transaction.atomic():
        session = _authorized_session(actor, session_id, report)
        if declared_build != session.reference_build:
            raise ValueError("confirmed build differs from upload")
        if session.state == "COMPLETED" and session.saved_alignment_id:
            return session.saved_alignment
        if session.state != "OPEN" or session.expires_at <= timezone.now():
            raise AlignmentSessionClosed("upload is not open")
        if (session.received_data_bytes != session.expected_data_size
                or session.received_index_bytes != session.expected_index_size):
            raise ValueError("pair is incomplete")
        session.state = "VALIDATING"
        session.save(update_fields=["state"])
    data = _stage_path(session.staging_data_key)
    index = _stage_path(session.staging_index_key)
    published = None
    try:
        data_digest, index_digest = _digest_file(data), _digest_file(index)
        existing = _identity(session.report, session.sample_id, session.reference_build,
                             session.role).first()
        if existing:
            if existing.format != session.format or not _same(existing, data_digest, index_digest):
                raise AlignmentConflict("different pair already saved for identity")
            saved = existing
        else:
            validate_pair(data, index, session.format, _reference(session.reference_build))
            published = publish_pair(
                data, index, Path(settings.PRONTO_ALIGNMENT_STORE_ROOT),
                max_data_bytes=settings.PRONTO_ALIGNMENT_MAX_BYTES,
                max_index_bytes=settings.PRONTO_ALIGNMENT_MAX_INDEX_BYTES,
            )
            with transaction.atomic():
                saved = SavedAlignment.objects.create(
                    report=session.report, sample_id=session.sample_id,
                    reference_build=session.reference_build, role=session.role,
                    format=session.format, data_key=published.data_key,
                    index_key=published.index_key, data_size=published.data_size,
                    index_size=published.index_size, data_sha256=published.data_sha256,
                    index_sha256=published.index_sha256, saved_by=actor,
                )
                AlignmentEvent.objects.create(report=session.report, actor=actor,
                                              saved_id=saved.id, action="SAVE")
        with transaction.atomic():
            locked = AlignmentUploadSession.objects.select_for_update().get(pk=session.id)
            locked.saved_alignment = saved
            locked.state = "COMPLETED"
            locked.save(update_fields=["saved_alignment", "state"])
        _cleanup(session)
        return saved
    except BaseException:
        if published is not None:
            remove_pair(published)
        _cleanup(session)
        AlignmentUploadSession.objects.filter(pk=session.id).update(state="FAILED")
        raise


def preserve_registered(actor, report, source_id: str) -> SavedAlignment:
    require_alignment_write(actor, report)
    _require_gate()
    sample = report.report_data.get("sample", {})
    try:
        pair = next(pair for pair in lookup_registered(
            report.report_id, sample.get("sampleId"), sample.get("referenceBuild"),
        ) if pair.source_id == source_id)
    except (InvalidAlignmentRegistry, StopIteration) as exc:
        raise ValueError("registered source is unavailable") from exc
    _reference(pair.reference_build)
    data_digest, index_digest = _digest_file(pair.data_path), _digest_file(pair.index_path)
    existing = _identity(report, pair.sample_id, pair.reference_build, pair.role).first()
    if existing:
        if existing.format == pair.format and _same(existing, data_digest, index_digest):
            return existing
        raise AlignmentConflict("different pair already saved for identity")
    validate_pair(pair.data_path, pair.index_path, pair.format, _reference(pair.reference_build))
    published = publish_pair(
        pair.data_path, pair.index_path, Path(settings.PRONTO_ALIGNMENT_STORE_ROOT),
        max_data_bytes=settings.PRONTO_ALIGNMENT_MAX_BYTES,
        max_index_bytes=settings.PRONTO_ALIGNMENT_MAX_INDEX_BYTES,
    )
    try:
        with transaction.atomic():
            saved = SavedAlignment.objects.create(
                report=report, sample_id=pair.sample_id, reference_build=pair.reference_build,
                role=pair.role, format=pair.format, data_key=published.data_key,
                index_key=published.index_key, data_size=published.data_size,
                index_size=published.index_size, data_sha256=published.data_sha256,
                index_sha256=published.index_sha256, saved_by=actor,
            )
            AlignmentEvent.objects.create(report=report, actor=actor, saved_id=saved.id,
                                          action="COPY")
        return saved
    except BaseException:
        remove_pair(published)
        raise


def _published_from_record(record: SavedAlignment) -> PublishedPair:
    root = Path(settings.PRONTO_ALIGNMENT_STORE_ROOT).resolve(strict=True)
    data_parts = record.data_key.split("/")
    index_parts = record.index_key.split("/")
    if (len(data_parts) != 2 or len(index_parts) != 2
            or data_parts[0] != index_parts[0] or not _KEY.fullmatch(data_parts[0])
            or data_parts[1] != "data" or index_parts[1] != "index"):
        raise UnsafeAlignmentPath("invalid stored pair keys")
    directory = root / data_parts[0]
    return PublishedPair(root, directory, directory / "data", directory / "index",
                         record.data_key, record.index_key, record.data_size,
                         record.index_size, record.data_sha256, record.index_sha256)


def delete_saved(actor, report, saved_id) -> None:
    require_alignment_write(actor, report)
    _require_gate()
    with transaction.atomic():
        saved = SavedAlignment.objects.select_for_update().get(pk=saved_id, report=report,
                                                                 status__in=["READY", "DELETING"])
        was_deleting = saved.status == "DELETING"
        saved.status = "DELETING"
        saved.save(update_fields=["status"])
    pair = _published_from_record(saved)
    if pair.directory.exists():
        remove_pair(pair)
    elif not was_deleting:
        raise UnsafeAlignmentPath("READY pair is missing from managed storage")
    with transaction.atomic():
        saved = SavedAlignment.objects.select_for_update().get(pk=saved_id, report=report,
                                                                 status="DELETING")
        AlignmentEvent.objects.create(report=report, actor=actor, saved_id=saved.id,
                                      action="DELETE")
        saved.delete()


def cancel_local_save(actor, session_id, *, report=None) -> None:
    _require_gate()
    with transaction.atomic():
        session = _authorized_session(actor, session_id, report)
        if session.state != "OPEN":
            raise AlignmentSessionClosed("upload is not open")
        _cleanup(session)
        session.state = "CANCELLED"
        session.save(update_fields=["state"])
