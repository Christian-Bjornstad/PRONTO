from base64 import b64decode
from dataclasses import replace
import pytest

from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html
from pronto_report.validation import validate_review_state


ONE_PIXEL_PNG = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aQeUAAAAASUVORK5CYII="
)


def test_declared_cnv_pages_and_qc_images_render_with_captions():
    report = build_report()
    cnv = next(item for item in report.attachments if "CNV" in item["name"])
    qc = next(item for item in report.attachments if "sample_QC" in item["name"])
    images = {
        cnv["assetId"]: (("image/png", ONE_PIXEL_PNG), ("image/png", ONE_PIXEL_PNG)),
        qc["assetId"]: (("image/png", ONE_PIXEL_PNG),),
    }

    html = render_html(report, plot_images=images)
    assert "CNV page 1 of 2" in html
    assert "CNV page 2 of 2" in html
    assert 'data-plot-select="cnv-1"' in html
    assert 'data-plot-select="cnv-2"' in html
    assert "data:image/png;base64," in html
    assert "Enlarge plot" in html
    assert "QC plot" in html


def test_nine_page_cnv_pdf_uses_distinct_panel_labels():
    report = build_report()
    cnv = next(item for item in report.attachments if "CNV" in item["name"])
    images = {cnv["assetId"]: tuple(("image/png", ONE_PIXEL_PNG) for _ in range(9))}
    html = render_html(report, plot_images=images)
    for label in ("A1", "A2", "B2", "B3", "C1", "C2", "C3", "C4", "C6"):
        assert f'CNV {label}</strong>' in html
    assert 'data-plot-select="cnv-group-1"' in html
    assert 'data-plot-select="cnv-group-2"' in html


def test_nine_page_cnv_pairs_are_stacked_with_all_source_pages():
    report = build_report()
    cnv = next(item for item in report.attachments if "CNV" in item["name"])
    images = {cnv["assetId"]: tuple(("image/png", ONE_PIXEL_PNG) for _ in range(9))}
    html = render_html(report, plot_images=images)
    assert '<div class="plot-group" id="cnv-group-1">' in html
    assert html.index('id="cnv-1"') < html.index('id="cnv-2"') < html.index('id="cnv-group-2"')
    for pair in ('A1 / A2', 'B2 / B3', 'C1 / C2', 'C3 / C4', 'C6'):
        assert f'>{pair}</button>' in html
    for index in range(1, 10):
        assert f'id="cnv-{index}"' in html
        assert f'data-enlarge="cnv-{index}"' in html


def test_missing_plots_and_qc_are_explicit():
    html = render_html(build_report())
    assert "CNV plot is not available for this report" in html
    assert "No structured QC metrics in source data" in html
    assert "QC plot is not available for this report" in html


@pytest.mark.parametrize("modern_review", [False, True])
def test_imported_cnv_and_rna_plots_are_visible_in_their_own_tabs(modern_review):
    report = replace(build_report(), attachments=(
        {"assetId": "desktop-cnv", "name": "main_cancan_result.png",
         "mediaType": "image/png", "sha256": "a" * 64, "description": "CNV"},
        {"assetId": "desktop-rna", "name": "MET & <fusion>_domain_plot.pdf",
         "mediaType": "application/pdf", "sha256": "b" * 64, "description": "RNA / domene"},
        {"assetId": "desktop-qc", "name": "RNA_sample_QC_plot.png",
         "mediaType": "image/png", "sha256": "c" * 64, "description": "QC"},
    ))
    review = None
    if modern_review:
        from pronto_report.migration import migrate_review_state_to_v3
        review = migrate_review_state_to_v3(draft_review(report))
    images = {item["assetId"]: (("image/png", ONE_PIXEL_PNG),) for item in report.attachments}
    html = render_html(report, review, plot_images=images)
    panels = {name: html.split(f'id="panel-{name}"', 1)[1].split('<section class="report-panel"', 1)[0]
              for name in ("cnv-plots", "rna-review", "sequencing-qc")}
    assert 'id="cnv-' in panels["cnv-plots"]
    assert 'data-enlarge="cnv-' in panels["cnv-plots"]
    assert 'id="rna-' in panels["rna-review"]
    assert 'data-enlarge="rna-' in panels["rna-review"]
    assert "MET &amp; &lt;fusion&gt;_domain_plot.pdf" in panels["rna-review"]
    assert "MET & <fusion>" not in html
    assert 'id="qc-1"' in panels["sequencing-qc"]
    assert 'id="rna-' not in panels["cnv-plots"] + panels["sequencing-qc"]
    assert "MET &amp; &lt;fusion&gt;" not in panels["cnv-plots"] + panels["sequencing-qc"]
    assert 'id="cnv-' not in panels["rna-review"] + panels["sequencing-qc"]


@pytest.mark.parametrize("modern_review", [False, True])
def test_explicit_imported_plot_role_takes_precedence_over_filename(modern_review):
    report = replace(build_report(), attachments=(
        {"assetId": "rna-with-legacy-cnv-name", "name": "sample_CNV_domain_plot.pdf",
         "mediaType": "application/pdf", "sha256": "d" * 64, "description": "RNA / domene"},
    ))
    review = None
    if modern_review:
        from pronto_report.migration import migrate_review_state_to_v3
        review = migrate_review_state_to_v3(draft_review(report))
    html = render_html(report, review, plot_images={"rna-with-legacy-cnv-name": (("image/png", ONE_PIXEL_PNG),)})
    cnv_panel = html.split('id="panel-cnv-plots"', 1)[1].split('<section class="report-panel"', 1)[0]
    rna_panel = html.split('id="panel-rna-review"', 1)[1].split('<section class="report-panel"', 1)[0]
    assert 'class="plot-figure"' not in cnv_panel
    assert 'class="plot-figure"' in rna_panel


def test_qc_cards_show_source_status_and_declared_threshold():
    report = build_report()
    report = replace(report, qc_metrics=({
        "metricId": "coverage", "label": "Median coverage", "value": 703,
        "unit": "x", "status": "PASS",
        "thresholds": ({"operator": "GTE", "value": 150, "label": "minst 150x"},),
        "source": {"fileName": "source.tsv"},
    },))

    html = render_html(report)
    assert "703 x" in html
    assert "Status: PASS" in html
    assert "Threshold: minst 150x" in html


def test_tumour_board_shows_only_included_reviewed_variant_once():
    report = build_report()
    review = draft_review(report)
    document = {
        "schemaVersion": "1.0", "reportId": report.report_id,
        "revision": 2, "status": "DRAFT", "reviewer": {"reviewerId": "reviewer-001"},
        "createdAt": "2026-09-22T12:00:00Z", "updatedAt": "2026-09-22T13:00:00Z",
        "variantReviews": [
            {
                "variantId": report.variants[2]["variantId"],
                "reportingDecision": "INCLUDE",
                "clinicalClassification": "UNCERTAIN",
                "igvAssessment": "NOT_REVIEWED",
            },
            {
                "variantId": report.variants[0]["variantId"],
                "reportingDecision": "EXCLUDE",
                "clinicalClassification": "PATHOGENIC",
                "igvAssessment": "NOT_REVIEWED",
            },
        ],
        "runQcAssessment": {"status": "NOT_REVIEWED"},
        "reportNotes": "Drøftes i MDT", "valueCorrections": [],
    }
    html = render_html(report, validate_review_state(document, report=report))
    panel = html.split('id="panel-tumour-board"')[1].split("</section>")[0]

    assert panel.count("TERT") == 1
    assert "CHEK2" not in panel
    assert "Drøftes i MDT" in panel
    assert "Not signed" in panel


def test_draft_has_compact_review_choices_without_combining_decision_and_classification():
    report = build_report()
    html = render_html(report, draft_review(report))
    assert 'data-quick-field="reportingDecision" data-quick-value="INCLUDE"' in html
    assert 'data-quick-field="reportingDecision" data-quick-value="EXCLUDE"' in html
    assert 'data-quick-field="clinicalClassification" data-quick-value="PATHOGENIC"' in html
    assert 'data-quick-field="clinicalClassification" data-quick-value="UNCERTAIN"' in html
    assert 'data-quick-value="INCLUDE"' in html
    assert 'data-include-variant=' in html
    assert '>Include in report</button>' not in html
