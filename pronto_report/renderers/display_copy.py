"""Remove known generator boilerplate from presentation, retaining source snapshots."""
from dataclasses import replace
import re
from types import MappingProxyType


NOTICE = 'Synthetic demonstration - invented findings, scores and review decisions. No real patient data.'
GENERATED_NOTES = {
    'variantDescription': 'All coordinates, transcript identifiers and variants in this case are invented.',
    'assayMethods': 'Synthetic demonstration. No sequencing was performed.',
    'clinicalEvidence': 'Editable demonstration text. No clinical evidence or treatment recommendations are encoded.',
    'followUp': 'Demonstration follow-up text for checking both PDF formats.',
    'additional': NOTICE,
}


def patient_display(sample):
    """The synthetic patient code remains visible; omit its repeated label."""
    values = dict(sample)
    if str(values.get('patientPseudonym', '')).startswith('SYN-'):
        values['tumourType'] = str(values.get('tumourType') or '').removesuffix(' (synthetic demo)')
    return MappingProxyType(values)


def presentation_copy(report, review):
    if not any(d['code'] == 'SYNTHETIC_DEMO' for d in report.diagnostics):
        return report, review
    run = dict(report.run)
    for key, expected in (('assay', 'SIMULATED DNA / RNA panel'), ('instrument', 'Synthetic demonstration')):
        if run.get(key) == expected:
            run[key] = None
    report = replace(report, sample=patient_display(report.sample), run=MappingProxyType(run))
    if review is None:
        return report, review
    notes = dict(review.notes or {})
    for key, expected in GENERATED_NOTES.items():
        if notes.get(key) == expected:
            notes[key] = ''
    if notes.get('additional') == NOTICE + '\nSimulated second save: version history demonstration.':
        notes['additional'] = ''
    patient = re.escape(str(report.sample['patientPseudonym']))
    summary = re.fullmatch(
        rf'Synthetic demonstration - patient {patient}\. Scenario: [^.]+\. '
        r'(\d+ small variants, \d+ CNV events and \d+ RNA events) are simulated\.',
        str(notes.get('summary', '')),
    )
    if summary:
        notes['summary'] = summary[1] + '.'
    tumour = str(report.sample.get('tumourType', '')).lower()
    if notes.get('history') == f'Simulated {tumour} case for reviewing the reporting workflow.':
        notes['history'] = ''
    if re.fullmatch(rf'Synthetic patient {patient}; simulated age \d+; (Female|Male); simulated tumour content \d+%\.', str(notes.get('patientDetails', ''))):
        notes['patientDetails'] = ''
    assessment = dict(review.run_qc_assessment)
    if assessment.get('comment') == 'Simulated overall quality assessment.':
        assessment['comment'] = ''
    activities = tuple(MappingProxyType({key: value for key, value in item.items()
                       if not (key == 'comment' and value == 'Simulated review choice, not a clinical classification.')})
                       for item in review.variant_reviews)
    return report, replace(review, notes=MappingProxyType(notes), variant_reviews=activities,
                           run_qc_assessment=MappingProxyType(assessment))
