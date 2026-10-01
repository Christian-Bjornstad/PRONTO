"""Entirely invented, reproducible report inputs for exercising review workflows."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import random

from pronto_report.models import ReportData, ReviewState
from pronto_report.validation import validate_report_data, validate_review_state
from .synthetic_plots import cnv_overview, rna_domain

GENERATOR = 'PRONTO synthetic demonstration'
VERSION = '1.0'
NOTICE = 'Synthetic demonstration - invented findings, scores and review decisions. No real patient data.'
TUMOURS = ('Lung adenocarcinoma', 'Colorectal adenocarcinoma', 'Melanoma', 'Breast carcinoma',
           'Ovarian carcinoma', 'Prostate carcinoma', 'Pancreatic adenocarcinoma', 'Glioma')
GENES = ('KRAS', 'TP53', 'BRCA1', 'PIK3CA', 'EGFR', 'BRAF', 'PTEN', 'NRAS', 'ATM', 'CHEK2')
SCENARIOS = ('No findings', 'Small variant and CNV', 'Fusion with small variants',
             'RNA fusion and splice', 'Larger result set', 'Small variant follow-up')
NOTE_KEYS = ('summary', 'biomarkerContext', 'additional', 'importedLegacyNote', 'history',
             'variantDescription', 'references', 'followUp', 'assayMethods', 'clinicalEvidence',
             'clinicalTrials', 'patientDetails')


@dataclass(frozen=True)
class SyntheticCase:
    report: ReportData
    initial_review: ReviewState
    prepared_review: ReviewState
    assets: dict[str, bytes]


def synthetic_report_id(index, seed):
    return f'demo-sim-{seed}-{index + 1:03}'


def build_synthetic_case(index, *, seed):
    randomizer = random.Random(f'{seed}:{index}')
    report_id = synthetic_report_id(index, seed)
    patient_id = f'SYN-{seed}-{index + 1:03}'
    sample_id = f'{patient_id}-DNA'
    scenario = (index // 3 + index) % len(SCENARIOS)
    created = datetime(2026, 9, 1, 8, tzinfo=timezone.utc) + timedelta(days=index % 28)
    timestamp = created.isoformat()
    configuration = json.dumps({'seed': seed, 'index': index, 'version': VERSION}, sort_keys=True).encode()
    source_files, tables, assets, attachments = [], [], {}, []

    def table(kind, headers, values, identifiers, occurrences=None):
        filename = f'simulated-{kind.lower()}.json'
        payload = json.dumps({'headers': headers, 'rows': values}, sort_keys=True).encode()
        digest = sha256(payload).hexdigest()
        source_files.append({'name': filename, 'sha256': digest, 'mediaType': 'application/json', 'sizeBytes': len(payload)})
        rows = [{'findingId': identifier, 'record': position + 1, 'values': row,
                 'sourceApproved': position % 3 == 0, 'sourceSampleId': sample_id,
                 **({'occurrenceId': occurrences[position]} if occurrences else {})}
                for position, (identifier, row) in enumerate(zip(identifiers, values))]
        tables.append({'tableId': f'synthetic-{kind.lower()}', 'kind': kind, 'fileName': filename,
                       'sha256': digest, 'sheet': 'Simulated', 'headers': headers, 'rows': rows,
                       'preamble': [NOTICE, f'Scenario: {SCENARIOS[scenario]}; seed={seed}; patient={patient_id}.'], 'demo': True})
        return filename

    variants, variant_values = [], []
    for position in range((0, 2, 5, 9, 20, 4)[scenario]):
        identifier = f'{report_id}-v{position + 1}'
        gene = GENES[(index + position) % len(GENES)]
        chromosome = str(1 + (index + position) % 22)
        locus = 100000 + index * 10000 + position * 101
        depth = randomizer.randint(90, 1400)
        frequency = round(randomizer.uniform(.025, .8), 3)
        protein = f'p.Sim{position + 1}'
        transcript = f'SYN_TX_{position + 1:03}'
        effect = ('missense', 'frameshift', 'stop_gained')[position % 3]
        variants.append({'variantId': identifier, 'occurrenceId': f'{identifier}-row1', 'sampleId': sample_id,
                         'referenceBuild': 'GRCh38', 'chromosome': chromosome, 'position': locus,
                         'reference': 'A', 'alternate': 'T', 'gene': gene, 'genomicLocation': f'{chromosome}:{locus}',
                         'dnaChange': f'c.{position + 1}A>T', 'proteinChange': protein, 'alleleFrequency': frequency,
                         'annotations': [{'key': key, 'value': value} for key, value in (
                             ('refSeqMrna', transcript), ('codingStatus', effect), ('depthTumourDna', depth))],
                         'source': {'fileName': 'simulated-variants.json', 'record': position + 1}})
        variant_values.append([sample_id, gene, transcript, f'{chromosome}:{locus}', f'c.{position + 1}A>T',
                               protein, effect, depth, frequency, 'SIMULATED'])
    table('VARIANTS', ['Sample_ID', 'Gene_symbol', 'RefSeq_mRNA', 'Genomic_location', 'DNA_change',
                      'Protein_change', 'Coding_status', 'Depth_tumor_DNA', 'VAF', 'Source'],
          variant_values, [v['variantId'] for v in variants], [v['occurrenceId'] for v in variants])

    cnv_values = []
    for position in range((0, 1, 2, 0, 4, 1)[scenario]):
        copy_number = (8, 0, 5, 12)[position % 4]
        cnv_values.append([sample_id, ('MYCN', 'RB1', 'ERBB2', 'CDKN2A')[position % 4],
                           str(position + 2), 100000 + position * 20000,
                           'gain' if copy_number > 2 else 'loss', copy_number,
                           round(copy_number * randomizer.uniform(.8, 1.1), 2), 2, 'SIMULATED'])
    table('CNV', ['Sample_ID', 'Gene_Symbol', 'Chromosome', 'Gene_Start', 'Event', 'Tumor_CN',
                  'Adjusted_Tumor_CN', 'Normal_CN', 'Source'], cnv_values,
          [f'{report_id}-cnv{position + 1}' for position in range(len(cnv_values))])

    rna_values = []
    for position in range((0, 0, 1, 2, 1, 0)[scenario]):
        gene_a, gene_b, event_type = (('EML4', 'ALK', 'Fusion'), ('MET', 'MET', 'Splice'))[position % 2]
        rna_values.append([sample_id, f'SIM-{gene_a}-{gene_b}-{position + 1}', event_type, gene_a, gene_b,
                           f'SYN_RNA_TX_{position + 1}', 13 + position, 20 - position,
                           randomizer.randint(8, 180), ('PASS', 'REVIEW')[position % 2], 'SIMULATED'])
    table('RNA', ['Sample_ID', 'Event_ID', 'Provisional_Event_Type', 'Gene_A', 'Gene_B', 'Transcript_A',
                  'Exon_A', 'Exon_B', 'Supporting_Reads', 'QC_Verdict', 'Source'], rna_values,
          [f'{report_id}-rna{position + 1}' for position in range(len(rna_values))])

    def attachment(identifier, name, media_type, payload):
        assets[identifier] = payload
        attachments.append({'assetId': identifier, 'name': name, 'mediaType': media_type,
                            'sha256': sha256(payload).hexdigest(), 'description': NOTICE})

    if cnv_values:
        attachment('synthetic-cnv', f'{sample_id}_CNV_overview_plots.pdf', 'application/pdf',
                   cnv_overview(sample_id, seed, index))
    for position, row in enumerate(rna_values):
        attachment(f'synthetic-rna-{position + 1}', f'{row[3]}-{row[4]}_synthetic_domain_plot.png', 'image/png',
                   rna_domain(sample_id, row[3], row[4], row[2]))
    source_files.append({'name': 'synthetic-configuration.json', 'sha256': sha256(configuration).hexdigest(),
                         'mediaType': 'application/json', 'sizeBytes': len(configuration)})
    scores = (round(randomizer.uniform(.2, 32), 1), round(randomizer.uniform(0, 100), 1),
              None if index % 7 == 3 else randomizer.randint(0, 100))
    if index == 8:
        scores = (147.0, scores[1], scores[2])
    measurements = [{'metricId': name, 'label': label, 'value': value, 'unit': unit,
                     'status': 'NOT_AVAILABLE' if value is None else 'INFO', 'displayRange': display_range,
                     'source': {'fileName': 'synthetic-configuration.json', 'field': name}, 'demo': True}
                    for name, label, value, unit, display_range in (
                        ('tmb', 'Tumour mutational burden', scores[0], 'mut/Mb', '[0-100+]'),
                        ('msi', 'Microsatellite instability', scores[1], '%', '[0-100]'),
                        ('hrd', 'Homologous recombination deficiency', scores[2], 'score', '[0-100]'))]
    qc = ('PASS', 'CONDITIONAL', 'FAIL', 'PASS')[index // 3 % 4]
    coverage = randomizer.randint(500, 1300) if qc == 'PASS' else randomizer.randint(90, 240) if qc == 'CONDITIONAL' else randomizer.randint(15, 70)
    report = validate_report_data({'schemaVersion': '2.0', 'reportId': report_id,
        'sample': {'sampleId': sample_id, 'patientPseudonym': patient_id, 'referenceBuild': 'GRCh38',
                   'tumourType': f'{TUMOURS[index % len(TUMOURS)]} (synthetic demo)',
                   'specimenType': ('FFPE biopsy', 'Resection', 'Cytology')[index % 3]},
        'run': {'runId': f'SIM-RUN-{seed}-{index // 5 + 1:02}', 'assay': 'SIMULATED DNA / RNA panel',
                'instrument': 'Synthetic demonstration'},
        'provenance': {'generatedAt': timestamp, 'generator': {'name': GENERATOR, 'version': VERSION,
                       'configurationHash': sha256(configuration).hexdigest()}, 'sourceFiles': source_files},
        'biomarkers': measurements, 'qcMetrics': [{'metricId': 'synthetic_dna_depth',
            'label': 'Simulated median tumour DNA coverage', 'value': coverage, 'unit': 'x',
            'status': {'PASS': 'PASS', 'CONDITIONAL': 'WARNING', 'FAIL': 'FAIL'}[qc], 'demo': True,
            'source': {'fileName': 'synthetic-configuration.json', 'field': 'simulated_depth'}}],
        'variants': variants, 'sourceTables': tables,
        'attachments': attachments, 'diagnostics': [{'severity': 'INFO', 'code': 'SYNTHETIC_DEMO',
                                                   'path': '/', 'message': NOTICE}]})
    notes = {key: '' for key in NOTE_KEYS}
    notes['importedLegacyNote'] = NOTICE
    initial = {'schemaVersion': '3.0', 'reportId': report_id, 'revision': 1, 'status': 'DRAFT',
               'reviewer': {'reviewerId': 'synthetic-demo'}, 'createdAt': timestamp, 'updatedAt': timestamp,
               'variantReviews': [], 'runQcAssessment': {'status': 'NOT_REVIEWED'}, 'notes': notes,
               'valueCorrections': [], 'findingReviews': [], 'biomarkerReviews': [], 'presentationFigures': [],
               'sectionQc': {key: {'status': 'NOT_REVIEWED'} for key in ('variants', 'cnv', 'rna', 'signatures')}}
    prepared = json.loads(json.dumps(initial))
    prepared['variantReviews'] = [{'variantId': v['variantId'],
        'reportingDecision': 'EXCLUDE' if position % 4 == 2 else 'INCLUDE',
        'clinicalClassification': ('ONCOGENIC', 'VUS', 'BENIGN', 'UNCLASSIFIED')[position % 4],
        'igvAssessment': 'NOT_APPLICABLE', 'reportHighlight': position % 4 in (0, 1),
        'comment': 'Simulated review choice, not a clinical classification.'}
        for position, v in enumerate(variants)]
    prepared['findingReviews'] = [{'findingId': row['findingId'],
        'reportingDecision': 'EXCLUDE' if position % 3 == 2 else 'INCLUDE', 'reportHighlight': position == 0}
        for source in tables if source['kind'] != 'VARIANTS' for position, row in enumerate(source['rows'])]
    prepared['biomarkerReviews'] = [{'metricId': m['metricId'], 'reportHighlight': index % 2 == 0}
                                   for m in measurements if m['value'] is not None]
    prepared['runQcAssessment'] = {'status': qc, 'comment': 'Simulated overall quality assessment.'}
    prepared['sectionQc'] = {key: {'status': qc if key == 'variants' else 'PASS'}
                             for key in ('variants', 'cnv', 'rna', 'signatures')}
    if not cnv_values:
        prepared['sectionQc']['cnv'] = {'status': 'NOT_REVIEWED'}
    if not rna_values:
        prepared['sectionQc']['rna'] = {'status': 'NOT_REVIEWED'}
    prepared['notes'].update({
        'summary': f'Synthetic demonstration - patient {patient_id}. Scenario: {SCENARIOS[scenario]}. '
                   f'{len(variants)} small variants, {len(cnv_values)} CNV events and {len(rna_values)} RNA events are simulated.',
        'history': f'Simulated {TUMOURS[index % len(TUMOURS)].lower()} case for reviewing the reporting workflow.',
        'patientDetails': f'Synthetic patient {patient_id}; simulated age {35 + index * 3 % 45}; '
                          f'{("Female", "Male")[index % 2]}; simulated tumour content {20 + index * 7 % 65}%.',
        'variantDescription': 'All coordinates, transcript identifiers and variants in this case are invented.',
        'assayMethods': 'Synthetic demonstration. No sequencing was performed.',
        'clinicalEvidence': 'Editable demonstration text. No clinical evidence or treatment recommendations are encoded.',
        'followUp': 'Demonstration follow-up text for checking both PDF formats.',
        'additional': NOTICE,
    })
    return SyntheticCase(report, validate_review_state(initial, report=report),
                         validate_review_state(prepared, report=report), assets)
