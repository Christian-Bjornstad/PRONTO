"""The delivered HTML is a saved, reduced report, never the editable workspace."""

import json

from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.migration import migrate_review_state_v1
from pronto_report.serialization import serialize_report_data, serialize_review_state
from pronto_report.validation import validate_report_data, validate_review_state


def _saved_review(report):
    document = json.loads(serialize_review_state(migrate_review_state_v1(draft_review(report))))
    selected = report.variants[2]['variantId']
    document['variantReviews'] = [{
        'variantId': selected, 'reportingDecision': 'INCLUDE',
        'clinicalClassification': 'PATHOGENIC', 'igvAssessment': 'NOT_REVIEWED',
        'comment': 'Checked in IGV',
    }, {
        'variantId': report.variants[0]['variantId'], 'reportingDecision': 'EXCLUDE',
        'clinicalClassification': 'UNCLASSIFIED', 'igvAssessment': 'NOT_REVIEWED',
    }]
    document['notes'].update(summary='Interpretation saved',
                             biomarkerContext='Therapeutic context saved',
                             additional='Additional saved note')
    document['valueCorrections'] = [{
        'path': '/biomarkers/0/value', 'originalValue': 14.9, 'correctedValue': 17.8,
        'reason': 'Checked source', 'author': 'biologist-1',
        'timestamp': '2026-09-29T07:06:49Z',
    }]
    return validate_review_state(document, report=report)


def test_summary_html_contains_saved_findings_once_with_depth_af_and_notes():
    from pronto_report.renderers.summary_html import render_summary_html
    report = build_report()
    review = _saved_review(report)

    html = render_summary_html(report, review, export_initials='AB')

    assert '<!doctype html>' in html.lower()
    assert report.report_id in html
    assert str(report.sample['sampleId']) in html
    assert 'Key findings' in html
    assert '17,8 mut/Mb' in html
    assert '14,9 mut/Mb' in html
    assert 'Checked source' in html
    assert f'data-variant-id="{report.variants[2]["variantId"]}"' in html
    assert html.count(f'data-variant-id="{report.variants[2]["variantId"]}"') == 1
    assert f'data-variant-id="{report.variants[0]["variantId"]}"' not in html
    assert '0,467' in html
    assert '>15</td>' in html
    assert 'Interpretation saved' in html
    assert 'Therapeutic context saved' in html
    assert 'Additional saved note' in html
    assert 'Revision 1' in html
    assert 'AB' in html
    assert 'OncoKB' in html and 'Not available' in html
    assert 'Not cross-checked' in html
    for absent in ('<script', '<link', 'http://', 'https://', 'IGV viewer', 'Variant review', 'Sequencing QC'):
        assert absent not in html


def test_summary_html_escapes_untrusted_facts_and_final_notes():
    from pronto_report.renderers.summary_html import render_summary_html
    report = build_report()
    source = json.loads(serialize_report_data(report))
    source['sample']['tumourType'] = '<script>alert("source")</script>&'
    report = validate_report_data(source)
    review_doc = json.loads(serialize_review_state(_saved_review(report)))
    review_doc['notes']['summary'] = '<img src="https://evil.example/x" onerror="alert(1)">&'
    review_doc.update(status='FINAL', finalizedAt='2026-09-29T14:00:00Z',
                      finalizedBy='biologist-1', updatedAt='2026-09-29T14:00:00Z')
    review = validate_review_state(review_doc, report=report)

    html = render_summary_html(report, review, export_initials='CD')

    assert '&lt;script&gt;alert(' in html
    assert '&lt;img src=' in html
    assert '&amp;' in html
    assert '<script' not in html
    assert '<img' not in html
    assert 'onerror=' not in html.replace('&quot;', '') or '&lt;img' in html
    assert '<link' not in html and '<iframe' not in html
    assert 'Final' in html and 'Revision 1' in html
