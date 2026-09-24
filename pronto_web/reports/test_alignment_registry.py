"""Only explicitly registered, exact-sample alignment pairs are discoverable."""

import json
import os

import pytest
from django.test import override_settings


@pytest.fixture(autouse=True)
def _django_settings_environment(monkeypatch):
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "pronto_web.settings")
    monkeypatch.setenv("PRONTO_DJANGO_SECRET_KEY", "registry-test-only-secret")


def _registry(tmp_path, entries):
    root = tmp_path / "registered"
    root.mkdir()
    sample_dir = root / "s1"
    sample_dir.mkdir()
    for name in ("tumour.bam", "tumour.bam.bai", "normal.cram", "normal.cram.crai"):
        (sample_dir / name).write_bytes(b"synthetic-fixture")
    manifest = tmp_path / "registry.json"
    manifest.write_text(json.dumps({"version": 1, "sources": entries}), encoding="utf-8")
    return root, manifest


def _entry(source_id, role, data, index):
    return {
        "id": source_id, "reportId": "r1", "sampleId": "s1",
        "referenceBuild": "GRCh37", "role": role,
        "format": "cram" if data.endswith(".cram") else "bam",
        "data": f"s1/{data}", "index": f"s1/{index}",
    }


def test_lookup_returns_all_exact_pairs_in_stable_order(tmp_path):
    from pronto_web.reports.alignment_registry import lookup_registered

    root, manifest = _registry(tmp_path, [
        _entry("tumour", "TUMOUR_DNA", "tumour.bam", "tumour.bam.bai"),
        _entry("normal", "NORMAL_DNA", "normal.cram", "normal.cram.crai"),
    ])
    with override_settings(PRONTO_ALIGNMENT_SOURCE_ROOT=str(root), PRONTO_ALIGNMENT_REGISTRY_JSON=str(manifest)):
        pairs = lookup_registered("r1", "s1", "GRCh37")
        assert tuple(pair.source_id for pair in pairs) == ("normal", "tumour")
        assert pairs[0].format == "cram"
        assert lookup_registered("r1", "s2", "GRCh37") == ()
        assert lookup_registered("r1", "s1", "GRCh38") == ()
        assert lookup_registered("r2", "s1", "GRCh37") == ()


def test_unset_registry_is_empty_and_half_configuration_fails_closed(tmp_path):
    from pronto_web.reports.alignment_registry import InvalidAlignmentRegistry, lookup_registered

    with override_settings(PRONTO_ALIGNMENT_SOURCE_ROOT="", PRONTO_ALIGNMENT_REGISTRY_JSON=""):
        assert lookup_registered("r1", "s1", "GRCh37") == ()
    with override_settings(PRONTO_ALIGNMENT_SOURCE_ROOT=str(tmp_path), PRONTO_ALIGNMENT_REGISTRY_JSON=""):
        with pytest.raises(InvalidAlignmentRegistry):
            lookup_registered("r1", "s1", "GRCh37")


def test_resolver_rejects_traversal_and_symlink_escape(tmp_path, monkeypatch):
    from pronto_web.reports.alignment_registry import InvalidAlignmentRegistry, resolve_registry_path

    root, _ = _registry(tmp_path, [])
    outside = tmp_path / "outside.bam"
    outside.write_bytes(b"outside")
    with pytest.raises(InvalidAlignmentRegistry):
        resolve_registry_path(root, "../outside.bam")
    with pytest.raises(InvalidAlignmentRegistry):
        resolve_registry_path(root, str(outside))
    with pytest.raises(InvalidAlignmentRegistry):
        resolve_registry_path(root, "C:s1/tumour.bam")
    link = root / "s1" / "link.bam"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        # Non-admin Windows hosts may forbid real symlinks. Keep a real file
        # and make only the symlink guard report it as linked.
        link.write_bytes(b"synthetic-fixture")
        original_is_symlink = type(link).is_symlink
        monkeypatch.setattr(type(link), "is_symlink", lambda path: path == link or original_is_symlink(path))
    with pytest.raises(InvalidAlignmentRegistry):
        resolve_registry_path(root, "s1/link.bam")


def test_duplicate_id_and_unknown_role_are_rejected(tmp_path):
    from pronto_web.reports.alignment_registry import InvalidAlignmentRegistry, lookup_registered

    entry = _entry("tumour", "TUMOUR_DNA", "tumour.bam", "tumour.bam.bai")
    root, manifest = _registry(tmp_path, [entry, entry])
    with override_settings(PRONTO_ALIGNMENT_SOURCE_ROOT=str(root), PRONTO_ALIGNMENT_REGISTRY_JSON=str(manifest)):
        with pytest.raises(InvalidAlignmentRegistry):
            lookup_registered("r1", "s1", "GRCh37")
    manifest.write_text(json.dumps({"version": 1, "sources": [{**entry, "id": "../other"}]}), encoding="utf-8")
    with override_settings(PRONTO_ALIGNMENT_SOURCE_ROOT=str(root), PRONTO_ALIGNMENT_REGISTRY_JSON=str(manifest)):
        with pytest.raises(InvalidAlignmentRegistry):
            lookup_registered("r1", "s1", "GRCh37")
    manifest.write_text(json.dumps({"version": 1, "sources": [{**entry, "role": "UNKNOWN"}]}), encoding="utf-8")
    with override_settings(PRONTO_ALIGNMENT_SOURCE_ROOT=str(root), PRONTO_ALIGNMENT_REGISTRY_JSON=str(manifest)):
        with pytest.raises(InvalidAlignmentRegistry):
            lookup_registered("r1", "s1", "GRCh37")


def test_component_resolution_is_scoped_to_report(tmp_path):
    from pronto_web.reports.alignment_registry import InvalidAlignmentRegistry, resolve_registered_component

    root, manifest = _registry(tmp_path, [_entry("tumour", "TUMOUR_DNA", "tumour.bam", "tumour.bam.bai")])
    with override_settings(PRONTO_ALIGNMENT_SOURCE_ROOT=str(root), PRONTO_ALIGNMENT_REGISTRY_JSON=str(manifest)):
        assert resolve_registered_component("r1", "tumour", "data") == root / "s1" / "tumour.bam"
        with pytest.raises(InvalidAlignmentRegistry):
            resolve_registered_component("r2", "tumour", "data")
        with pytest.raises(InvalidAlignmentRegistry):
            resolve_registered_component("r1", "tumour", "other")
