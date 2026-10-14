import json
from dataclasses import replace

import pytest

from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import validate_review_state, ContractValidationError


def test_v4_keeps_manual_choices_and_supports_manual_cnv():
    from pronto_report.review.source_defaults import upgrade_review
    report = build_report()
    original = draft_review(report)
    review = upgrade_review(report, original)
    assert review.schema_version == '4.0'
    assert review.variant_reviews[0]['reportingDecision'] == 'EXCLUDE'
    doc = json.loads(serialize_review_state(review))
    doc['manualCnvRows'] = [{'findingId': 'manual-cnv-123', 'geneSymbol': 'MET', 'tumorFc': 0}]
    doc['findingReviews'] = [{'findingId': 'manual-cnv-123', 'reportingDecision': 'INCLUDE',
                             'reportHighlight': True, 'cnChange': 'GAIN', 'cytoband': '7q31'}]
    assert validate_review_state(doc, report=report).manual_cnv_rows[0]['tumorFc'] == 0
    doc['manualCnvRows'][0]['tumorFc'] = -1
    with pytest.raises(ContractValidationError):
        validate_review_state(doc, report=report)


def test_biomarker_exact_matching_and_legacy_igv_conversion():
    from pronto_report.review.gene_registry import gene_in_list
    from pronto_report.review.source_defaults import upgrade_review
    assert gene_in_list(' kras ')
    assert gene_in_list('PDCD1LG2')
    assert gene_in_list('CDKN2B')
    assert not gene_in_list('KRAS2')
    assert not gene_in_list('TMB')
    report = build_report()
    original = draft_review(report)
    activity = {**original.variant_reviews[0], 'igvAssessment': 'SUPPORTS'}
    upgraded = upgrade_review(report, replace(original, variant_reviews=(activity,)))
    assert upgraded.variant_reviews[0]['igvAssessment'] == 'OK'


def test_source_defaults_are_independent_and_conflicts_stay_unreviewed():
    from pronto_report.review.source_defaults import source_defaults
    report = build_report()
    variant = report.variants[0]
    row = {'findingId': variant['variantId'], 'occurrenceId': variant['occurrenceId'],
           'values': ['include', 'Likely_Pathogenic', 'OK']}
    table = {'kind': 'VARIANTS', 'headers': ['Class_judgement', 'CPSR_ClinVar_class', 'IGV_QC'], 'rows': [row]}
    report = replace(report, source_tables=(table,))
    choices = source_defaults(report)
    assert choices[variant['variantId']]['clinicalClassification'] == 'LIKELY_PATHOGENIC'
    assert choices[variant['variantId']]['reportingDecision'] == 'INCLUDE'
    assert choices[variant['variantId']]['igvAssessment'] == 'OK'
    table['rows'].append({**row, 'values': ['exclude', 'Likely_Pathogenic', 'OK']})
    assert source_defaults(report)[variant['variantId']]['reportingDecision'] == 'UNREVIEWED'


def cnv_case():
    from pronto_report.review.source_defaults import upgrade_review
    report = build_report()
    table={'tableId':'test-cnv','kind':'CNV','fileName':'cnv.csv','sheet':'Data','headers':['Chromosome','Gene_Symbol','Tumor_FC'],
           'rows':[{'findingId':'cnv-1','values':['7','MET',2.5],'sourceApproved':False,'record':2}], 'demo':False}
    report=replace(report,source_tables=(table,))
    doc=json.loads(serialize_review_state(upgrade_review(report,draft_review(report))))
    doc['manualCnvRows']=[{'findingId':'manual-cnv-123','geneSymbol':'ERBB2','tumorFc':4.2}]
    doc['findingReviews']=[{'findingId':'manual-cnv-123','reportingDecision':'INCLUDE','reportHighlight':True,'cnChange':'GAIN','cytoband':'17q12'}]
    doc['sectionQc']['cnv']['comment']='Review CNV quality'
    return report,validate_review_state(doc,report=report)


def test_cnv_workspace_and_pdf_projection_share_manual_fields():
    from pronto_report.renderers.html import render_html
    from pronto_report.renderers.report_pdf import project_report_export,render_report_pdf
    from pypdf import PdfReader
    from io import BytesIO
    report,review=cnv_case()
    html=render_html(report,review,inline_assets=True)
    assert 'Add CNV row' in html and 'Expand table' in html
    assert 'data-cn-field="cytoband"' in html
    assert 'data-source-action="INCLUDE"' in html
    assert 'data-exclude-variant=' not in html
    assert html.count('data-section-qc-comment="cnv"')==1
    assert html.count('data-section-qc-comment="rna"')==1
    assert html.index('Gene_Symbol</th>') < html.index('Chromosome</th>') < html.index('Cytoband</th>')
    projected=project_report_export(report,review)
    assert projected['cnv'][0]['fields']['Gene_Symbol']=='ERBB2'
    for layout in ('ESMO','PRESENTATION'):
        pdf=render_report_pdf(report,review,layout=layout,export_initials='writer')
        text=' '.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
        assert '17q12' in text and 'GAIN' in text and '4.2' in text
        assert 'Review CNV quality' in text


@pytest.mark.parametrize('classification',['LIKELY_BENIGN','LIKELY_PATHOGENIC','LIKELY_ONCOGENIC','PATHOGENIC'])
def test_included_extended_classifications_render_live_and_historical(classification):
    from pronto_report.review.source_defaults import upgrade_review
    from pronto_report.renderers.html import render_html
    report=build_report();review=upgrade_review(report,draft_review(report))
    item={**review.variant_reviews[0],'clinicalClassification':classification,'reportingDecision':'INCLUDE'}
    review=replace(review,variant_reviews=(item,))
    assert 'Classification:' in render_html(report,review)
    assert 'Classification:' in render_html(report,review,inline_assets=True,snapshot=True)


def test_manual_fc_is_editable_when_source_does_not_have_fc_column():
    from pronto_report.renderers.html import render_html
    report,review=cnv_case()
    table={**report.source_tables[0],'headers':['Chromosome','Gene_Symbol'],
           'rows':[{'findingId':'cnv-1','values':['7','MET'],'sourceApproved':False,'record':2}]}
    html=render_html(replace(report,source_tables=(table,)),review)
    assert 'Tumor_FC</th>' in html
    assert 'data-manual-field="Tumor_FC"' in html
    assert 'value="4.2"' in html


def test_published_display_does_not_seed_new_source_decisions():
    from pronto_report.review.source_defaults import upgrade_review
    report=build_report()
    final=replace(draft_review(report),status='FINAL',finalized_at='2026-10-14T10:00:00Z',finalized_by='writer')
    display=upgrade_review(report,final,seed_defaults=False)
    assert len(display.variant_reviews)==len(final.variant_reviews)
    assert display.variant_reviews[0]['reportingDecision']==final.variant_reviews[0]['reportingDecision']
