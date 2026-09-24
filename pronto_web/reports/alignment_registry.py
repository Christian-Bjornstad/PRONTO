"""Read-only manifest for explicit report/sample alignment pairs."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Literal

from django.conf import settings


_FIELDS = {"id", "reportId", "sampleId", "referenceBuild", "role", "format", "data", "index"}
_ROLES = {"TUMOUR_DNA", "NORMAL_DNA", "TUMOUR_RNA", "NORMAL_RNA"}
_FORMATS = {"bam", "cram"}
_BUILDS = {"GRCh37", "GRCh38"}


class InvalidAlignmentRegistry(ValueError):
    """A configured source is missing, ambiguous, or outside its root."""


@dataclass(frozen=True, slots=True)
class RegisteredPair:
    source_id: str
    report_id: str
    sample_id: str
    reference_build: str
    role: str
    format: str
    data_path: Path
    index_path: Path


def resolve_registry_path(root: Path, relative: str) -> Path:
    """Resolve a file below an allowlisted root, refusing symlink traversal."""
    candidate = Path(relative)
    if (not relative or candidate.is_absolute() or candidate.drive
            or any(part in {"", ".", ".."} for part in candidate.parts)):
        raise InvalidAlignmentRegistry("invalid relative source path")
    try:
        base = root.resolve(strict=True)
        if not base.is_dir():
            raise InvalidAlignmentRegistry("source root is not a directory")
        current = base
        for part in candidate.parts:
            current = current / part
            if current.is_symlink():
                raise InvalidAlignmentRegistry("symlinked source path")
        target = current.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise InvalidAlignmentRegistry("source file is unavailable") from exc
    if base not in target.parents or not target.is_file():
        raise InvalidAlignmentRegistry("source file is outside root or not a file")
    return target


def _configured_pairs() -> tuple[RegisteredPair, ...]:
    root_text = getattr(settings, "PRONTO_ALIGNMENT_SOURCE_ROOT", "")
    manifest_text = getattr(settings, "PRONTO_ALIGNMENT_REGISTRY_JSON", "")
    if not root_text and not manifest_text:
        return ()
    if not root_text or not manifest_text:
        raise InvalidAlignmentRegistry("source registry configuration is incomplete")
    root = Path(root_text)
    try:
        document = json.loads(Path(manifest_text).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidAlignmentRegistry("source registry cannot be read") from exc
    if not isinstance(document, dict) or set(document) != {"version", "sources"}:
        raise InvalidAlignmentRegistry("invalid source registry document")
    if type(document["version"]) is not int or document["version"] != 1 or not isinstance(document["sources"], list):
        raise InvalidAlignmentRegistry("unsupported source registry version")

    pairs: list[RegisteredPair] = []
    seen: set[str] = set()
    for entry in document["sources"]:
        if not isinstance(entry, dict) or set(entry) != _FIELDS:
            raise InvalidAlignmentRegistry("invalid source entry")
        if not all(isinstance(entry[field], str) and entry[field] for field in _FIELDS):
            raise InvalidAlignmentRegistry("source fields must be nonempty strings")
        source_id = entry["id"]
        if source_id in seen or len(source_id) > 128 or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", source_id) is None:
            raise InvalidAlignmentRegistry("duplicate or invalid source ID")
        seen.add(source_id)
        if entry["role"] not in _ROLES or entry["format"] not in _FORMATS or entry["referenceBuild"] not in _BUILDS:
            raise InvalidAlignmentRegistry("unsupported source role, format, or build")
        if not entry["data"].lower().endswith("." + entry["format"]):
            raise InvalidAlignmentRegistry("alignment format disagrees with source path")
        if not entry["index"].lower().endswith((".bai", ".csi") if entry["format"] == "bam" else (".crai",)):
            raise InvalidAlignmentRegistry("index format disagrees with source path")
        pairs.append(RegisteredPair(
            source_id=source_id,
            report_id=entry["reportId"],
            sample_id=entry["sampleId"],
            reference_build=entry["referenceBuild"],
            role=entry["role"],
            format=entry["format"],
            data_path=resolve_registry_path(root, entry["data"]),
            index_path=resolve_registry_path(root, entry["index"]),
        ))
    return tuple(sorted(pairs, key=lambda pair: (pair.role, pair.source_id)))


def lookup_registered(report_id: str, sample_id: str, reference_build: str) -> tuple[RegisteredPair, ...]:
    """Return all exact-key candidates; the caller chooses when there are many."""
    return tuple(
        pair for pair in _configured_pairs()
        if (pair.report_id, pair.sample_id, pair.reference_build) == (report_id, sample_id, reference_build)
    )


def resolve_registered_component(report_id: str, source_id: str, component: Literal["data", "index"]) -> Path:
    if component not in {"data", "index"}:
        raise InvalidAlignmentRegistry("unknown source component")
    for pair in _configured_pairs():
        if pair.report_id == report_id and pair.source_id == source_id:
            return pair.data_path if component == "data" else pair.index_path
    raise InvalidAlignmentRegistry("unknown source for report")
