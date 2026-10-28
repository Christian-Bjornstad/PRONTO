"""Reporting defaults and display corrections must preserve the source meaning."""
import json
from dataclasses import replace

import pytest

from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto.tests.reporting.test_review_v4 import cnv_case
from pronto_report.review.source_defaults import exclusion_reason, source_defaults
from pronto_report.renderers.report_pdf import project_report_export
from pronto_report.renderers.source_fields import rna_display_fields
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import validate_review_state


@pytest.mark.parametrize('gene,coding,localapp,excluded', [
    ('MLH1','synonymous_variant','',True), ('TERT','synonymous_variant','',True),
    ('VHL','x:noncoding_variant','',True), ('TERT','x:noncoding_variant','',False),
    ('TERT','x:noncoding_variant','GL_BL',True), ('VHL','missense_variant','BL',True),
    ('VHL','nonsynonymous_variant','',False), ('VHL','missense_variant','',False),
])
def test_explicit_exclusion_rules(gene,coding,localapp,excluded):
    assert bool(exclusion_reason(gene,coding,localapp)) is excluded


def test_typo_in_coding_status_still_overrides_source_include():
    report=build_report();variant={**report.variants[0],'annotations':[]}
    table={'kind':'VARIANTS','headers':['Gene_symbol','coding_sastus','Class_judgement'],
           'rows':[{'findingId':variant['variantId'],'values':['VHL','synonymous_variant','Include']}]}
    report=replace(report,variants=(variant,),source_tables=(table,))
    assert source_defaults(report)[variant['variantId']]['reportingDecision']=='EXCLUDE'


def test_manual_copy_number_reaches_export_and_can_be_zero():
    report,review=cnv_case()
    assert project_report_export(report,review)['cnv'][0]['fields']['Tumor_CN']==4.2
    data=json.loads(serialize_review_state(review));data['manualCnvRows'][0]['tumorCn']=0
    model=project_report_export(report,validate_review_state(data,report=report))
    assert model['cnv'][0]['fields']['Tumor_CN']==0
    assert model['cnv'][0]['fields']['Tumor_FC']==4.2


def test_fusion_names_use_declared_exons_without_inference():
    fields={'Gene_A':'EWSR1','Gene_B':'ATF1','Provisional_Event_Type':'Fusion','Exon_A':'Exon8','Exon_B':'4th'}
    result=rna_display_fields(fields)
    assert result['Gene_Label']=='EWSR1::ATF1'
    assert result['Alteration_Label']=='EWSR1(ex8)::ATF1(ex4)'
    result=rna_display_fields({'Gene_A':'EGFR','Gene_B':'EGFR','Provisional_Event_Type':'Splice_variant',
                              'Event_ID':'EGFR-splice-variant','Exon_A':'.','Exon_B':'.'})
    assert result['Alteration_Label']=='EGFR-splice-variant'
