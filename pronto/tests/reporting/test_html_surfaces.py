from base64 import b64decode
from dataclasses import replace

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
    assert "CNV oversikt – side 1 av 2" in html
    assert "CNV oversikt – side 2 av 2" in html
    assert 'data-plot-select="cnv-1"' in html
    assert 'data-plot-select="cnv-2"' in html
    assert "data:image/png;base64," in html
    assert "Forstørr plott" in html
    assert "QC-plott" in html


def test_missing_plots_and_qc_are_explicit():
    html = render_html(build_report())
    assert "CNV-plott er ikke tilgjengelig" in html
    assert "Ingen strukturerte QC-målinger tilgjengelig" in html
    assert "QC-plott er ikke tilgjengelig" in html


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
    assert "Grense: minst 150x" in html


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
    assert "Ikke signert" in panel
