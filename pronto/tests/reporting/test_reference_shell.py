"""The report shell keeps the recognizable reference hierarchy without fake facts."""

from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto_report.renderers.html import render_html


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []

    def handle_starttag(self, tag, attrs):
        self.items.append((tag, dict(attrs)))


def test_reference_shell_has_sticky_topbar_actions_and_five_tabs():
    html = render_html(build_report())
    parser = Tags()
    parser.feed(html)
    attrs = [item for _, item in parser.items]

    assert any(item.get("class") == "report-topbar" for item in attrs)
    assert any(item.get("id") == "edit-btn" and "disabled" in item for item in attrs)
    assert any(item.get("id") == "save-btn" and "disabled" in item for item in attrs)
    assert not any(item.get("id") in {"load-btn", "reset-btn"} for item in attrs)
    assert 'class="report-tab__count"' in html
    assert ">30</span>" in html
    assert len([item for item in attrs if item.get("role") == "tab"]) == 5
    assert 'Rapporten er et beslutningsstøtteverktøy' not in html
    assert 'må følge gjeldende kvalitetssikringsprosess' not in html


def test_patient_strip_and_kpis_use_approved_facts_with_explicit_gaps():
    html = render_html(build_report())

    assert 'class="patient-strip"' in html
    assert 'data-fact="tumourType"' in html
    assert 'data-availability="UNAVAILABLE"' in html
    assert "14,9 mut/Mb" in html
    assert "4,13 %" in html
    assert "LocalApp TMB" in html
    assert "Variants · include" in html
    assert "CNV / amplifications" in html
    assert "Fusions / splicing" in html
    assert "Not reported" in html
    assert "CNS/Brain" not in html


def test_key_findings_summary_uses_only_source_backed_protein_changes():
    report = build_report()
    html = render_html(report)
    panel = html.split('id="panel-key-findings"', 1)[1].split("</section>", 1)[0]
    expected = [variant for variant in report.variants if variant.get("proteinChange")]

    assert "Variants with a protein change" in panel
    assert '<th scope="col">Coding</th>' in panel
    assert panel.count('class="key-variant-row"') == len(expected)
    for variant in expected:
        assert f'data-occurrence-id="{variant["occurrenceId"]}"' in panel


def test_key_findings_summary_handles_missing_protein_changes():
    report = build_report()
    report = replace(report, variants=tuple({**variant, "proteinChange": ""} for variant in report.variants))
    html = render_html(report)
    panel = html.split('id="panel-key-findings"', 1)[1].split("</section>", 1)[0]

    assert 'class="key-variant-row"' not in panel
    assert "No variants with a reported protein change" in panel


def test_key_findings_summary_displays_zero_frequency_with_three_decimals():
    report = build_report()
    variants = list(report.variants)
    variants[0] = {**variants[0], "proteinChange": "p.Test", "alleleFrequency": 0.0}
    panel = render_html(replace(report, variants=tuple(variants))).split(
        'id="panel-key-findings"', 1
    )[1].split("</section>", 1)[0]

    test_row = next(row for row in panel.split('</tr>') if 'p.Test</td>' in row)
    assert '<td>0,000</td>' in test_row


def test_key_findings_joins_source_depth_and_coding_annotation_with_review():
    report = build_report()
    review = replace(draft_review(report), variant_reviews=({
        'variantId': report.variants[0]['variantId'], 'reportingDecision': 'EXCLUDE',
        'clinicalClassification': 'UNCLASSIFIED', 'igvAssessment': 'NOT_REVIEWED',
    },))
    panel = render_html(report, review).split(
        'id="panel-key-findings"', 1
    )[1].split('</section>', 1)[0]

    assert '<th scope="col">Tumour DNA depth</th>' in panel
    assert '<th scope="col">IGV QC</th>' in panel
    assert '<th scope="col">Report</th>' in panel
    assert 'data-review-summary="decision" data-status="EXCLUDE">Exclude</span>' in panel
    assert 'data-review-summary="igv">Not reviewed</span>' in panel
    assert '<th scope="col">Coding</th>' in panel


def test_reference_visual_tokens_are_used_without_remote_font_dependency():
    stylesheet = (Path(__file__).parents[3] / "pronto_report/static/report.css").read_text(encoding="utf-8")

    assert "--color-primary: #0284c7" in stylesheet.lower()
    assert "--color-canvas: #f0f9ff" in stylesheet.lower()
    assert "--font-sans: \"Fira Sans\"" in stylesheet
    assert ".report-topbar" in stylesheet
    assert "position: sticky" in stylesheet
    assert "@import" not in stylesheet
