"""The save model exists only as private metadata behind explicit policy."""

import pytest
from django.test import override_settings


@pytest.fixture(autouse=True)
def _django_settings_environment(monkeypatch):
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "pronto_web.settings")
    monkeypatch.setenv("PRONTO_DJANGO_SECRET_KEY", "metadata-test-only-secret")
    import django
    django.setup()


def test_save_guard_is_off_without_explicit_private_configuration():
    from django.conf import settings
    from pronto_web.reports.alignment_config import alignment_saving_enabled

    assert not alignment_saving_enabled(settings)
    with override_settings(PRONTO_ALIGNMENT_STORE_ROOT="", PRONTO_ALIGNMENT_STAGING_ROOT=""):
        assert not alignment_saving_enabled(settings)
    with override_settings(PRONTO_ALIGNMENT_STORE_ROOT="/tmp/managed",
                           PRONTO_ALIGNMENT_STAGING_ROOT="/tmp/staging",
                           PRONTO_ALIGNMENT_POLICY_APPROVED=False):
        assert not alignment_saving_enabled(settings)


def test_save_guard_requires_distinct_roots_and_linux(tmp_path, monkeypatch):
    from django.conf import settings
    from pronto_web.reports import alignment_config

    managed = tmp_path / "managed"
    staging = tmp_path / "staging"
    managed.mkdir()
    staging.mkdir()
    reference = tmp_path / "reference.fa"
    index = tmp_path / "reference.fa.fai"
    reference.write_bytes(b">chr22\nA\n")
    index.write_bytes(b"chr22\t1\t7\t1\t2\n")
    common = dict(PRONTO_ALIGNMENT_STORE_ROOT=str(managed),
                  PRONTO_ALIGNMENT_POLICY_APPROVED=True,
                  PRONTO_ALIGNMENT_MAX_BYTES=1024,
                  PRONTO_ALIGNMENT_MAX_INDEX_BYTES=128,
                  PRONTO_ALIGNMENT_MAX_REPORT_BYTES=2048,
                  PRONTO_ALIGNMENT_MIN_FREE_BYTES=0,
                  PRONTO_ALIGNMENT_REFERENCE_FILES={"GRCh37": {"fasta": str(reference), "index": str(index)}})
    monkeypatch.setattr(alignment_config, "_supported_platform", lambda: False)
    with override_settings(**common, PRONTO_ALIGNMENT_STAGING_ROOT=str(staging)):
        assert not alignment_config.alignment_saving_enabled(settings)

    monkeypatch.setattr(alignment_config, "_supported_platform", lambda: True)
    with override_settings(**common, PRONTO_ALIGNMENT_STAGING_ROOT=str(managed)):
        assert not alignment_config.alignment_saving_enabled(settings)
    with override_settings(**common, PRONTO_ALIGNMENT_STAGING_ROOT=str(staging)):
        assert alignment_config.alignment_saving_enabled(settings)
    with override_settings(**{**common, "PRONTO_ALIGNMENT_STAGING_ROOT": str(staging),
                              "PRONTO_ALIGNMENT_MAX_REPORT_BYTES": 0}):
        assert not alignment_config.alignment_saving_enabled(settings)
    public = tmp_path / "public"
    public.mkdir()
    public_managed = public / "alignments"
    public_managed.mkdir()
    with override_settings(**{**common, "PRONTO_ALIGNMENT_STORE_ROOT": str(public_managed),
                              "PRONTO_ALIGNMENT_STAGING_ROOT": str(staging),
                              "STATIC_ROOT": str(public)}):
        assert not alignment_config.alignment_saving_enabled(settings)
    with override_settings(**{**common, "PRONTO_ALIGNMENT_STAGING_ROOT": str(staging),
                              "STATIC_ROOT": str(tmp_path)}):
        assert not alignment_config.alignment_saving_enabled(settings)


def test_metadata_models_contain_no_alignment_binary_field():
    from pronto_web.reports.models import (AlignmentEvent, AlignmentUploadSession,
                                           ReportWriteGrant, SavedAlignment)
    from django.db.models import BinaryField

    for model in (ReportWriteGrant, SavedAlignment, AlignmentUploadSession, AlignmentEvent):
        assert all(not isinstance(field, BinaryField) for field in model._meta.get_fields())
    assert SavedAlignment._meta.get_field("id").primary_key
