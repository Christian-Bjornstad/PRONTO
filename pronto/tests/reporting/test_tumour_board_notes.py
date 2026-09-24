"""Tumour-board notes preserve v1 text and expose independent v2 fields."""

import json

from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto.tests.reporting.test_reference_projection import review_document
from pronto_report.renderers.html import render_html
from pronto_report.validation import validate_review_state


def test_v2_board_shows_three_separate_editable_note_fields():
    report = build_report()
    document = review_document(report, report.variants[2]["variantId"])
    review = validate_review_state(document, report=report)

    html = render_html(report, review)
    panel = html.split('id="panel-tumour-board"', 1)[1].split("</section>", 1)[0]

    assert '<textarea id="note-summary"' in panel
    assert '<textarea id="note-biomarker-context"' in panel
    assert '<textarea id="note-additional"' in panel
    assert "Kort oppsummering" in panel
    assert "TMB vurdert" in panel
    assert "Ferdigstilling krever lagret gjennomgang" in panel


def test_v1_board_migrates_legacy_text_without_reinterpreting_it():
    report = build_report()
    review = draft_review(report)
    html = render_html(report, review)
    payload = html.split('id="review-state-data">', 1)[1].split("</script>", 1)[0]
    exported = json.loads(payload)

    assert exported["schemaVersion"] == "2.0"
    assert exported["notes"]["summary"] == ""
    assert exported["notes"]["importedLegacyNote"] == review.report_notes
    assert review.schema_version == "1.0"


def test_final_board_note_fields_are_read_only():
    report = build_report()
    document = review_document(report, report.variants[2]["variantId"])
    document.update({"status": "FINAL", "finalizedAt": "2026-09-23T10:00:00Z", "finalizedBy": "biologist-001"})
    review = validate_review_state(document, report=report)
    html = render_html(report, review)

    assert '<textarea id="note-summary"' in html
    assert html.count('class="board-note"') == 3
    assert html.count('class="board-note" rows="5" maxlength="50000" disabled') == 3


def test_note_text_cannot_escape_editor_or_print_preview():
    report = build_report()
    document = review_document(report, report.variants[2]["variantId"])
    document["notes"]["summary"] = '</textarea><script>alert(1)</script>'
    review = validate_review_state(document, report=report)

    html = render_html(report, review)

    assert '</textarea><script>alert(1)</script>' not in html
    assert html.count('&lt;/textarea&gt;&lt;script&gt;alert(1)&lt;/script&gt;') == 2
