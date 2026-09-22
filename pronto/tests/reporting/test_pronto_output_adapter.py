from pathlib import Path

import pytest

import pronto_report.adapters.pronto_output as adapter_module
from pronto_report.adapters.pronto_output import AdapterError, adapt_pronto_output
from pronto_report.cli import main
from pronto_report.serialization import deserialize_report_data, serialize_report_data


FIXTURE_ROOT = (
    Path(__file__).parents[3]
    / "test_data"
    / "ous"
    / "251114_A02134_0115_BHCJCKDRX7_TSO_500_LocalApp_postprocessing_results"
)
SAMPLE_ID = "IPD2225-D01-P01-A08"
GENERATED_AT = "2026-09-22T12:00:00Z"


def build_report():
    return adapt_pronto_output(
        FIXTURE_ROOT,
        sample_id=SAMPLE_ID,
        generated_at=GENERATED_AT,
        generator_version="1.0.0",
    )


def by_id(items, key, expected):
    return next(item for item in items if item[key] == expected)


def test_adapter_maps_approved_ous_fixture_into_valid_report_data():
    report = build_report()

    assert report.sample["sampleId"] == SAMPLE_ID
    assert report.sample["patientPseudonym"] == "MRARE-X-xxxx"
    assert report.sample["referenceBuild"] == "GRCh37"
    assert report.run["runId"] == "251114_A02134_0115_BHCJCKDRX7"
    assert report.provenance["generatedAt"] == GENERATED_AT
    assert len(report.variants) == 30


def test_adapter_maps_source_biomarkers_without_recalculating_categories():
    report = build_report()
    tmb = by_id(report.biomarkers, "metricId", "tmb")
    msi = by_id(report.biomarkers, "metricId", "msi")

    assert tmb["value"] == 14.9
    assert tmb["unit"] == "mut/Mb"
    assert tmb["source"]["rawValue"] == "14.9 (19)"
    assert "status" not in tmb
    assert msi["value"] == 4.13
    assert msi["source"]["rawValue"] == "4.13 (5/121)"


def test_adapter_preserves_duplicate_tert_occurrences_with_stable_ids():
    report = build_report()
    tert = [variant for variant in report.variants if variant["gene"] == "TERT"]

    assert len(tert) == 2
    assert tert[0]["variantId"] == tert[1]["variantId"]
    assert tert[0]["occurrenceId"] != tert[1]["occurrenceId"]
    assert any(
        diagnostic["code"] == "DUPLICATE_VARIANT_ID"
        and diagnostic["path"].startswith("variants[")
        for diagnostic in report.diagnostics
    )


def test_adapter_records_missing_data_instead_of_inventing_values():
    report = build_report()
    diagnostic_codes = {item["code"] for item in report.diagnostics}

    assert "tumourType" not in report.sample
    assert report.qc_metrics == ()
    assert "MISSING_CLINICAL_DIAGNOSIS" in diagnostic_codes
    assert "MISSING_STRUCTURED_QC" in diagnostic_codes


def test_adapter_records_relative_hashed_provenance_and_declared_assets():
    report = build_report()
    source_files = report.provenance["sourceFiles"]

    assert len(source_files) == 4
    assert all(len(source["sha256"]) == 64 for source in source_files)
    assert all(not Path(source["name"]).is_absolute() for source in source_files)
    assert len(report.attachments) == 3
    assert all(len(attachment["sha256"]) == 64 for attachment in report.attachments)


def test_adapter_output_is_deterministic_and_round_trips():
    first = build_report()
    second = build_report()

    first_bytes = serialize_report_data(first)
    second_bytes = serialize_report_data(second)

    assert first.report_id == second.report_id
    assert first_bytes == second_bytes
    assert deserialize_report_data(first_bytes) == first


def test_cli_exports_the_approved_ous_fixture(tmp_path):
    output_path = tmp_path / "report-data.json"

    exit_code = main(
        [
            "export",
            "--fixture",
            "ous",
            "--output",
            str(output_path),
            "--generated-at",
            GENERATED_AT,
        ]
    )

    assert exit_code == 0
    exported = deserialize_report_data(output_path.read_bytes())
    assert exported.sample["sampleId"] == SAMPLE_ID
    assert len(exported.variants) == 30


@pytest.mark.parametrize("sample_id", ["../outside", "sample/child", "C:\\outside"])
def test_adapter_rejects_sample_ids_that_can_escape_the_fixture_root(sample_id):
    with pytest.raises(AdapterError, match="Sample identifier is invalid"):
        adapt_pronto_output(
            FIXTURE_ROOT,
            sample_id=sample_id,
            generated_at=GENERATED_AT,
            generator_version="1.0.0",
        )


def test_adapter_rejects_oversized_source_before_reading(monkeypatch):
    monkeypatch.setattr(adapter_module, "MAX_SOURCE_BYTES", 1)

    with pytest.raises(AdapterError, match="Source file exceeds the allowed size"):
        build_report()
