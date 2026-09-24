"""Validate and publish complete alignment pairs under a private root.

No database record is created here. Callers create READY metadata only after
``publish_pair`` returns; its directory rename makes both files appear at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import re
import stat
import uuid


CHUNK_SIZE = 1024 * 1024
_OPAQUE_NAME = re.compile(r"[0-9a-f]{32}\Z")


class InvalidAlignmentPair(ValueError):
    """The content, index, or reference is unusable or inconsistent."""


class UnsafeAlignmentPath(ValueError):
    """A path is not a regular owned file beneath its expected root."""


class StorageLimitError(ValueError):
    """A file exceeds the configured hard byte limit."""


@dataclass(frozen=True)
class AlignmentHeader:
    references: tuple[str, ...]
    lengths: tuple[int, ...]
    has_index: bool


@dataclass(frozen=True)
class PublishedPair:
    root: Path
    directory: Path
    data_path: Path
    index_path: Path
    data_key: str
    index_key: str
    data_size: int
    index_size: int
    data_sha256: str
    index_sha256: str


def _regular_file(path: Path) -> Path:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise UnsafeAlignmentPath("alignment component must be a regular file")
    return path


def _private_root(path: Path) -> Path:
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise UnsafeAlignmentPath("private root is unavailable")
    return path.resolve(strict=True)


def validate_pair(data_path: Path, index_path: Path, format: str,
                  reference_path: Path) -> AlignmentHeader:
    """Require real BAM/CRAM, usable random-access index and matching contigs."""
    if format not in {"bam", "cram"}:
        raise InvalidAlignmentPair("unsupported alignment format")
    try:
        data = _regular_file(data_path)
        index = _regular_file(index_path)
        reference = _regular_file(reference_path)
        _regular_file(Path(str(reference) + ".fai"))
        import pysam  # Linux save dependency; viewing must still run on Windows.

        with pysam.FastaFile(str(reference)) as fasta:
            reference_lengths = dict(zip(fasta.references, fasta.lengths))
        with pysam.AlignmentFile(
            str(data), "rb" if format == "bam" else "rc",
            index_filename=str(index), reference_filename=str(reference),
            require_index=True,
        ) as alignment:
            if not alignment.has_index() or (format == "bam" and not alignment.is_bam) \
                    or (format == "cram" and not alignment.is_cram):
                raise InvalidAlignmentPair("format or index is invalid")
            names = tuple(alignment.references)
            lengths = tuple(alignment.lengths)
            if not names or any(reference_lengths.get(name) != length
                                for name, length in zip(names, lengths)):
                raise InvalidAlignmentPair("reference contigs do not match")
            # A tiny indexed fetch also forces htslib to read the index and CRAM data.
            next(alignment.fetch(names[0], 0, lengths[0]), None)
            return AlignmentHeader(names, lengths, True)
    except (OSError, ValueError, RuntimeError, UnsafeAlignmentPath) as exc:
        if isinstance(exc, InvalidAlignmentPair):
            raise
        raise InvalidAlignmentPair("alignment, index, or local reference is invalid") from exc


def _copy_to_private_file(source: Path, destination: Path, max_bytes: int) -> tuple[int, str]:
    if max_bytes <= 0:
        raise StorageLimitError("positive byte limit required")
    source = _regular_file(source)
    source_fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(source_fd).st_mode):
            raise UnsafeAlignmentPath("source is not a regular file")
        target_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            count = 0
            digest = sha256()
            with os.fdopen(source_fd, "rb", closefd=False) as input_file, \
                    os.fdopen(target_fd, "wb", closefd=False) as output_file:
                while block := input_file.read(CHUNK_SIZE):
                    count += len(block)
                    if count > max_bytes:
                        raise StorageLimitError("alignment component exceeds byte limit")
                    output_file.write(block)
                    digest.update(block)
                output_file.flush()
                os.fsync(output_file.fileno())
            if count == 0:
                raise InvalidAlignmentPair("empty alignment component")
            return count, digest.hexdigest()
        finally:
            os.close(target_fd)
    finally:
        os.close(source_fd)


def _fsync_directory(directory: Path) -> None:
    if os.name == "posix":
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def publish_pair(staging_data: Path, staging_index: Path, destination_root: Path,
                 *, max_data_bytes: int | None = None,
                 max_index_bytes: int | None = None) -> PublishedPair:
    """Copy a bounded pair and atomically reveal its opaque directory."""
    root = _private_root(destination_root)
    data = _regular_file(staging_data)
    index = _regular_file(staging_index)
    # Callers must pass configured limits. The current source size is only a
    # fallback for standalone use; the streaming loop rejects later growth.
    data_limit = max_data_bytes if max_data_bytes is not None else data.stat().st_size
    index_limit = max_index_bytes if max_index_bytes is not None else index.stat().st_size
    if data.stat().st_size > data_limit or index.stat().st_size > index_limit:
        raise StorageLimitError("alignment component exceeds byte limit")
    key = uuid.uuid4().hex
    temporary = root / f".{key}.tmp"
    final = root / key
    temporary.mkdir(mode=0o700)
    promoted = False
    try:
        data_size, data_hash = _copy_to_private_file(data, temporary / "data", data_limit)
        index_size, index_hash = _copy_to_private_file(index, temporary / "index", index_limit)
        _fsync_directory(temporary)
        os.replace(temporary, final)
        promoted = True
        _fsync_directory(root)
        return PublishedPair(root, final, final / "data", final / "index",
                             f"{key}/data", f"{key}/index", data_size, index_size,
                             data_hash, index_hash)
    except BaseException:
        cleanup = final if promoted else temporary
        for name in ("data", "index"):
            (cleanup / name).unlink(missing_ok=True)
        cleanup.rmdir()
        raise


def remove_pair(pair: PublishedPair) -> None:
    """Remove only a pair with exact opaque ownership metadata under its root."""
    root = _private_root(pair.root)
    directory = pair.directory
    if (directory.is_symlink() or directory.parent != root
            or not _OPAQUE_NAME.fullmatch(directory.name)
            or pair.data_path != directory / "data"
            or pair.index_path != directory / "index"
            or pair.data_key != f"{directory.name}/data"
            or pair.index_key != f"{directory.name}/index"):
        raise UnsafeAlignmentPath("pair does not belong to private root")
    _regular_file(pair.data_path)
    _regular_file(pair.index_path)
    pair.data_path.unlink()
    pair.index_path.unlink()
    directory.rmdir()
    _fsync_directory(root)
