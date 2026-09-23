"""Guard the approved fixture's facts against prototype-only display values."""

from pronto.tests.reporting.test_pronto_output_adapter import build_report


def test_reference_field_map_keeps_source_facts_and_gaps_distinct():
    report = build_report()

    assert set(report.sample) == {"sampleId", "patientPseudonym", "referenceBuild"}
    assert set(report.run) == {"runId"}
    assert {item["metricId"]: item["value"] for item in report.biomarkers} == {
        "tmb": 14.9,
        "msi": 4.13,
    }
    assert {item["metricId"]: item["source"]["rawValue"] for item in report.biomarkers} == {
        "tmb": "14.9 (19)",
        "msi": "4.13 (5/121)",
    }
    assert report.qc_metrics == ()
    assert len(report.variants) == 30
    tert = [variant for variant in report.variants if variant["gene"] == "TERT"]
    assert len(tert) == 2
    assert tert[0]["variantId"] == tert[1]["variantId"]
    assert tert[0]["occurrenceId"] != tert[1]["occurrenceId"]
