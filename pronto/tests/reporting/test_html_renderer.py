from html.parser import HTMLParser

from pronto_report.models import ReportData
from pronto_report.renderers.html import render_html


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
