"""Saved corrections must remain visible without rewriting the source facts."""

import json

from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html
from pronto_report.migration import migrate_review_state_v1
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import validate_review_state


def test_saved_corrections_show_source_and_review_values_in_draft_and_final():
    report = build_report()
    document = json.loads(serialize_review_state(migrate_review_state_v1(draft_review(report))))
    tmb_index = next(index for index, item in enumerate(report.biomarkers) if item["metricId"] == "tmb")
    document["valueCorrections"] = [
        {"path": "/sample/tumourType", "originalValue": None,
         "correctedValue": "Syntetisk type", "reason": "Bekreftet i syntetisk kilde",
         "author": "biologist-1", "timestamp": "2026-09-24T12:00:00Z"},
        {"path": f"/biomarkers/{tmb_index}/value", "originalValue": 14.9,
         "correctedValue": 12, "reason": "Syntetisk målekontroll",
         "author": "biologist-1", "timestamp": "2026-09-24T12:00:00Z"},
    ]
    draft = validate_review_state(document, report=report)
    html = render_html(report, draft)

    assert "Kilde: Ikke oppgitt" in html
    assert "Lagret korreksjon: Syntetisk type" in html
    assert "Lagret korreksjon: 12 mut/Mb" in html
    assert "Bekreftet i syntetisk kilde" in html
    assert "14,9 mut/Mb" in html
    assert 'value="Syntetisk type"' in html

    document.update({"status": "FINAL", "finalizedAt": "2026-09-24T13:00:00Z",
                     "finalizedBy": "biologist-1", "updatedAt": "2026-09-24T13:00:00Z"})
    final = validate_review_state(document, report=report)
    final_html = render_html(report, final)
    assert "Lagret korreksjon: Syntetisk type" in final_html
    assert "Lagret korreksjon: 12 mut/Mb" in final_html
    assert 'id="tmb-edit-value"' not in final_html


def test_saved_correction_text_is_escaped_in_notice_and_editor():
    report = build_report()
    document = json.loads(serialize_review_state(migrate_review_state_v1(draft_review(report))))
    document["valueCorrections"] = [{
        "path": "/sample/tumourType", "originalValue": None,
        "correctedValue": '<img src=x onerror="alert(1)">',
        "reason": '<script>alert(2)</script>',
        "author": "biologist-1", "timestamp": "2026-09-24T12:00:00Z",
    }]
    html = render_html(report, validate_review_state(document, report=report))

    assert '<img src=x onerror="alert(1)">' not in html
    assert '<script>alert(2)</script>' not in html
    assert '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;' in html
    assert '&lt;script&gt;alert(2)&lt;/script&gt;' in html
