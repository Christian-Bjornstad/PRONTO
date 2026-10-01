"""Saved corrections must remain visible without rewriting the source facts."""

import json
import re

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
        {"path": "/sample/specimenType", "originalValue": None,
         "correctedValue": "Syntetisk prøve", "reason": "Bekreftet i syntetisk kilde",
         "author": "biologist-1", "timestamp": "2026-09-24T12:00:00Z"},
        {"path": f"/biomarkers/{tmb_index}/value", "originalValue": 14.9,
         "correctedValue": 12, "reason": "Syntetisk målekontroll",
         "author": "biologist-1", "timestamp": "2026-09-24T12:00:00Z"},
        {"path": "/biomarkers/1/value", "originalValue": 4.13,
         "correctedValue": 6.25, "reason": "Syntetisk målekontroll",
         "author": "biologist-1", "timestamp": "2026-09-24T12:00:00Z"},
    ]
    draft = validate_review_state(document, report=report)
    html = render_html(report, draft)

    assert "Source: Not reported" in html
    assert '<details class="saved-correction"' in html
    assert "Corrected" in html
    assert "12 mut/Mb" in html
    assert "Bekreftet i syntetisk kilde" in html
    assert "14,9 mut/Mb" in html
    assert 'value="Syntetisk type"' in html
    assert re.search(r'data-fact="tumourType"[^>]*><dt>Tumour type</dt><dd>Syntetisk type</dd>', html)
    assert re.search(r'data-fact="specimenType"[^>]*><dt>Sample type</dt><dd>Syntetisk prøve</dd>', html)
    assert re.search(r'data-metric="tmb"[^>]*>.*?<p class="metric-card__value">12 mut/Mb</p>', html, re.S)
    assert re.search(r'data-metric="msi"[^>]*>.*?<p class="metric-card__value">6,25 %</p>', html, re.S)

    document.update({"status": "FINAL", "finalizedAt": "2026-09-24T13:00:00Z",
                     "finalizedBy": "biologist-1", "updatedAt": "2026-09-24T13:00:00Z"})
    final = validate_review_state(document, report=report)
    final_html = render_html(report, final)
    assert '<details class="saved-correction"' in final_html
    assert "Corrected" in final_html
    assert "12 mut/Mb" in final_html
    assert 'id="tmb-edit-value"' not in final_html
    assert re.search(r'data-fact="tumourType"[^>]*><dt>Tumour type</dt><dd>Syntetisk type</dd>', final_html)
    assert re.search(r'data-metric="msi"[^>]*>.*?<p class="metric-card__value">6,25 %</p>', final_html, re.S)


def test_tmb_gauge_keeps_reference_scale_and_saved_provenance_accessible():
    report = build_report()
    document = json.loads(serialize_review_state(migrate_review_state_v1(draft_review(report))))
    index = next(i for i, item in enumerate(report.biomarkers) if item["metricId"] == "tmb")
    document["valueCorrections"] = [{
        "path": f"/biomarkers/{index}/value", "originalValue": 14.9,
        "correctedValue": 5, "reason": "Confirmed measurement",
        "author": "biologist-1", "timestamp": "2026-09-24T12:00:00Z",
    }]
    document["lastSavedAttribution"] = {"declaredInitials": "AB", "method": "SELF_REPORTED"}
    html = render_html(report, validate_review_state(document, report=report))

    assert 'id="tmb-gauge" type="range" class="tmb-gauge__cursor" min="0" max="30"' in html
    assert 'class="tmb-gauge__scale"' in html
    assert '<span>5</span>' in html and '<span>20</span>' in html
    assert '<details class="saved-correction"' in html
    assert 'Reason: Confirmed measurement' in html
    assert '14,9 mut/Mb' in html
    assert '(self-reported initials)' not in html


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
