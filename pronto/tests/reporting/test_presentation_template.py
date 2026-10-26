from io import BytesIO
import json
from pypdf import PdfReader
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto_report.review.source_defaults import upgrade_review
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import validate_review_state
from pronto_report.renderers.report_pdf import render_report_pdf


def test_presentation_matches_reference_structure_and_keeps_manual_context():
    report = build_report()
    data = json.loads(serialize_review_state(upgrade_review(report, draft_review(report))))
    data['variantReviews'][0]['reportingDecision'] = 'INCLUDE'
    data['variantReviews'][0]['reportHighlight'] = True
    data['variantReviews'][0]['presentation'] = {'functionalEffect':'LoF', 'sensitive':'Synthetic treatment context',
        'resistant':'None entered', 'emaTumour':'Manual tumour context', 'emaOther':'Manual other context',
        'description':'Description supplied by the reviewer'}
    review = validate_review_state(data, report=report)
    pdf = PdfReader(BytesIO(render_report_pdf(report, review, layout='PRESENTATION', export_initials='TEST')))
    first = pdf.pages[0]
    assert abs(float(first.mediabox.width) / float(first.mediabox.height) - 16/9) < .001
    text = first.extract_text()
    for heading in ('Mutational signatures', 'Copy number alterations', 'Fusions and splice',
                    'Mutations (N=', 'Key relevant findings', 'Variant description'):
        assert heading in text
    all_text = '\n'.join(page.extract_text() for page in pdf.pages)
    for value in data['variantReviews'][0]['presentation'].values():
        assert value in ' '.join(all_text.split())


def test_overflowing_presentation_annotations_are_not_clipped():
    report = build_report()
    data = json.loads(serialize_review_state(upgrade_review(report, draft_review(report))))
    data['variantReviews'][0]['reportingDecision'] = 'INCLUDE'
    data['variantReviews'][0]['reportHighlight'] = True
    data['variantReviews'][0]['presentation'] = {'description':'Long manual description. ' * 1500 + 'END_OF_DESCRIPTION'}
    review = validate_review_state(data, report=report)
    pdf = PdfReader(BytesIO(render_report_pdf(report, review, layout='PRESENTATION', export_initials='TEST')))
    assert 'END_OF_DESCRIPTION' in '\n'.join(page.extract_text() for page in pdf.pages)
