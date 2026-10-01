from importlib import import_module, util
from io import BytesIO
import json
from uuid import uuid4
from PIL import Image

from pypdf import PdfReader
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto_report.migration import migrate_review_state_to_v3
from pronto_report.serialization import serialize_review_state
from pronto_report.serialization import serialize_report_data
from pronto_report.validation import validate_report_data
from pronto_report.validation import validate_review_state


def renderer():
    assert util.find_spec('pronto_report.renderers.report_pdf'), 'PDF renderer missing'
    return import_module('pronto_report.renderers.report_pdf').render_report_pdf


def test_both_pdf_formats_use_same_saved_selection_and_text_and_orientation():
    report=build_report();document=json.loads(serialize_review_state(migrate_review_state_to_v3(draft_review(report))))
    identifier=report.variants[0]['variantId']
    document['variantReviews']=[{'variantId':identifier,'reportingDecision':'INCLUDE','clinicalClassification':'VUS','igvAssessment':'NOT_REVIEWED','reportHighlight':True}]
    document['variantReviews'].append({'variantId':report.variants[2]['variantId'],'reportingDecision':'EXCLUDE','clinicalClassification':'VUS','igvAssessment':'NOT_REVIEWED','reportHighlight':True})
    document['notes']['history']='Synthetic clinical history'
    document['sectionQc']['variants']['status']='CONDITIONAL'
    review=validate_review_state(document,report=report)
    for layout in ('PRESENTATION','ESMO'):
        payload=renderer()(report,review,layout=layout,export_initials='AB')
        pdf=PdfReader(BytesIO(payload)); text='\n'.join(p.extract_text() for p in pdf.pages)
        assert payload.startswith(b'%PDF')
        assert 'Synthetic clinical history' in text and 'VUS' in text
        assert 'Key relevant findings' in text and 'CONDITIONAL' in text
        assert 'DRAFT' in text and 'AB' in text
        assert 'MSI' in text and '[0-100]' in text
        assert report.variants[2]['gene'] not in text
        page=pdf.pages[0]
        assert (float(page.mediabox.width)>float(page.mediabox.height)) == (layout=='PRESENTATION')
        if layout=='ESMO': assert len(pdf.pages)>=3


def test_long_report_text_survives_pagination_without_clipping():
    report=build_report();document=json.loads(serialize_review_state(migrate_review_state_to_v3(draft_review(report))))
    document['notes']['summary']='Repeated synthetic sentence. '*1200+'LAST_MARKER'
    review=validate_review_state(document,report=report)
    for layout in ('PRESENTATION','ESMO'):
        pdf=PdfReader(BytesIO(renderer()(report,review,layout=layout,export_initials='AB')))
        assert 'LAST_MARKER' in '\n'.join(p.extract_text() for p in pdf.pages)
        assert len(pdf.pages)>3


def test_tall_figure_and_caption_stay_together_on_last_presentation_page():
    report=build_report();document=json.loads(serialize_review_state(migrate_review_state_to_v3(draft_review(report))))
    identifier=str(uuid4());document['presentationFigures']=[{'figureId':identifier,'caption':'Tall pathway figure caption'}]
    output=BytesIO();Image.new('RGB',(200,600),'green').save(output,'PNG')
    review=validate_review_state(document,report=report)
    pdf=PdfReader(BytesIO(renderer()(report,review,layout='PRESENTATION',export_initials='AB',figure_assets={identifier:output.getvalue()})))
    assert 'Tall pathway figure caption' in pdf.pages[-1].extract_text()
    assert len(pdf.pages[-1].images)==1


def test_included_rna_duplicates_keep_all_transcript_annotations(tmp_path):
    from pronto_report.adapters.source_tables import read_source_table
    from pronto_report.renderers.report_pdf import project_report_export
    file=tmp_path/'rna.csv'
    file.write_text('Provisional_Event_Type;Sample_ID;Gene_A;Gene_B;Transcript_A\nFusion;DEMO;A;B;ENST_FIRST\nFusion;DEMO;A;B;ENST_SECOND\n')
    table=read_source_table(file,kind='RNA',demo=True)
    report_doc=json.loads(serialize_report_data(build_report()));report_doc['sourceTables'].append(table)
    report=validate_report_data(report_doc)
    document=json.loads(serialize_review_state(migrate_review_state_to_v3(draft_review(report))))
    document['findingReviews']=[{'findingId':table['rows'][0]['findingId'],'reportingDecision':'INCLUDE','reportHighlight':True}]
    review=validate_review_state(document,report=report)
    model=project_report_export(report,review)
    assert len(model['rna'])==1
    assert model['rna'][0]['fields']['Transcript_A']=='ENST_FIRST / ENST_SECOND'
    for layout in ('PRESENTATION','ESMO'):
        text=''.join(p.extract_text() for p in PdfReader(BytesIO(renderer()(report,review,layout=layout,export_initials='AB'))).pages)
        assert 'ENST_FIRST' in text and 'ENST_SECOND' in text


def test_all_qc_assessments_export_even_when_no_cnv_or_rna_is_included():
    report=build_report();document=json.loads(serialize_review_state(migrate_review_state_to_v3(draft_review(report))))
    document['sectionQc']['cnv']['status']='FAIL';document['sectionQc']['rna']['status']='CONDITIONAL'
    review=validate_review_state(document,report=report)
    for layout in ('PRESENTATION','ESMO'):
        text=''.join(page.extract_text() for page in PdfReader(BytesIO(renderer()(report,review,layout=layout,export_initials='AB'))).pages)
        assert 'CNV QC: FAIL' in text and 'RNA QC: CONDITIONAL' in text
