from html.parser import HTMLParser

from pronto_report.models import ReportData
from pronto_report.renderers.html import render_html
from pronto.tests.reporting.test_pronto_output_adapter import build_report as approved_report


PANEL_NAMES = (
    "key-findings",
    "variant-review",
    "cnv-plots",
    "sequencing-qc",
    "tumour-board",
)


class StructureParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def build_report(sample_id="IPD-TEST-001"):
    return ReportData.from_validated(
        {
            "schemaVersion": "1.0.0",
            "reportId": "report_test_001",
            "sample": {"sampleId": sample_id, "referenceBuild": "GRCh37"},
            "run": {"runId": "run_test_001"},
            "provenance": {
                "generatedAt": "2026-09-22T12:00:00Z",
                "generator": {"name": "PRONTO", "version": "1.0.0"},
                "sourceFiles": [],
            },
            "biomarkers": [],
            "qcMetrics": [],
            "variants": [],
            "attachments": [],
            "diagnostics": [],
        }
    )


def parse(document):
    parser = StructureParser()
    parser.feed(document)
    return parser.tags


def test_renderer_outputs_semantic_page_landmarks_and_modular_assets():
    document = render_html(build_report())
    tags = parse(document)
    tag_names = [tag for tag, _ in tags]

    assert document.startswith("<!doctype html>")
    assert "header" in tag_names
    assert "nav" in tag_names
    assert "main" in tag_names
    assert "footer" in tag_names
    assert any(
        tag == "link" and attrs.get("href") == "/pronto_report/static/report.css"
        for tag, attrs in tags
    )
    assert any(
        tag == "script" and attrs.get("src") == "/pronto_report/static/report.js"
        for tag, attrs in tags
    )
    assert "{{" not in document
    assert "{%" not in document


def test_renderer_connects_all_five_tabs_to_accessible_panels():
    tags = parse(render_html(build_report()))
    tabs = [attrs for _, attrs in tags if attrs.get("role") == "tab"]
    panels = [attrs for _, attrs in tags if attrs.get("role") == "tabpanel"]

    assert len(tabs) == len(PANEL_NAMES)
    assert len(panels) == len(PANEL_NAMES)

    for index, name in enumerate(PANEL_NAMES):
        tab = next(item for item in tabs if item["id"] == f"tab-{name}")
        panel = next(item for item in panels if item["id"] == f"panel-{name}")

        assert tab["aria-controls"] == panel["id"]
        assert panel["aria-labelledby"] == tab["id"]
        assert tab["aria-selected"] == ("true" if index == 0 else "false")
        assert tab["tabindex"] == ("0" if index == 0 else "-1")
        assert ("hidden" not in panel) == (index == 0)


def test_renderer_escapes_report_values_at_the_template_boundary():
    document = render_html(build_report('<script>alert("unsafe")</script>'))

    assert '<script>alert("unsafe")</script>' not in document
    assert "&lt;script&gt;alert(&quot;unsafe&quot;)&lt;/script&gt;" in document


def test_renderer_exposes_identity_and_text_status_without_color_only_meaning():
    document = render_html(build_report())

    assert "IPD-TEST-001" in document
    assert "report_test_001" in document
    assert "Rapportstatus: Utkast" in document


def test_approved_report_renders_source_biomarkers_and_every_variant_occurrence():
    document = render_html(approved_report())
    review_panel = document.split('id="panel-variant-review"', 1)[1].split("</section>", 1)[0]
    tags = parse(review_panel)

    assert "14,9 mut/Mb" in document
    assert "4,13 %" in document
    assert "IPD2225-D01-P01-A08" in document
    assert sum(tag == "tr" and "data-occurrence-id" in attrs for tag, attrs in tags) == 30
    assert document.count("TERT") >= 2


def test_empty_report_explains_missing_biomarkers_and_variants():
    document = render_html(build_report())

    assert "Ingen biomarkørverdier tilgjengelig" in document
    assert "Ingen varianter tilgjengelig" in document


def test_variant_and_measurement_text_is_escaped():
    report = approved_report()
    variant = dict(report.variants[0])
    variant["gene"] = '<img src=x onerror=alert(1)>'
    report = ReportData(
        schema_version=report.schema_version,
        report_id=report.report_id,
        sample=report.sample,
        run=report.run,
        provenance=report.provenance,
        biomarkers=report.biomarkers,
        qc_metrics=report.qc_metrics,
        variants=(variant,),
        attachments=report.attachments,
        diagnostics=report.diagnostics,
    )

    rendered = render_html(report)
    assert '<img src=x onerror=alert(1)>' not in rendered
    assert '&lt;img src=x onerror=alert(1)&gt;' in rendered
