"""Explicit source defaults; saved human choices always take precedence."""
import json
import re

from pronto_report.migration import migrate_review_state_to_v3
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import validate_review_state

CLASSES = ('BENIGN', 'LIKELY_BENIGN', 'VUS', 'LIKELY_PATHOGENIC', 'PATHOGENIC',
           'ONCOGENIC', 'LIKELY_ONCOGENIC')
IGV = {'SUPPORTS': 'OK', 'DOES_NOT_SUPPORT': 'ARTIFACT', 'INCONCLUSIVE': 'NOT_RELIABLE'}


def normalized(value):
    return str(value or '').strip().upper().replace(' ', '_').replace('-', '_')


def exclusion_reason(gene, coding_status, localapp_class):
    """User-defined reporting defaults; never delete a source variant."""
    if normalized(localapp_class) in {'BL', 'GL_BL'}:
        return 'LocalApp: ' + normalized(localapp_class)
    coding = re.split(r'[;|,&\s/]+', str(coding_status or '').strip().casefold())
    if 'synonymous_variant' in coding:
        return 'Synonymous variant'
    if any(value.startswith('x:noncoding') for value in coding) and normalized(gene) != 'TERT':
        return 'Noncoding variant (except TERT)'
    return ''


def exclusion_ids(report):
    identifiers = set()
    for table in report.source_tables:
        if table['kind'] != 'VARIANTS':
            continue
        for row in table['rows']:
            fields = {normalized(k): v for k, v in zip(table['headers'], row['values'])}
            if exclusion_reason(fields.get('GENE_SYMBOL'), fields.get('CODING_STATUS') or fields.get('CODING_SASTUS'),
                                fields.get('TSO500_LOCALAPP_CLASS')):
                identifiers.add(row['findingId'])
    for variant in report.variants:
        annotations = {item['key']: item['value'] for item in variant['annotations']}
        if exclusion_reason(variant.get('gene'), annotations.get('codingStatus'), annotations.get('tso500LocalAppClass')):
            identifiers.add(variant['variantId'])
    return sorted(identifiers)


def source_defaults(report):
    groups = {}
    for table in report.source_tables:
        if table['kind'] != 'VARIANTS':
            continue
        for row in table['rows']:
            fields = {normalized(k): v for k, v in zip(table['headers'], row['values'])}
            classification = normalized(fields.get('CPSR_CLINVAR_CLASS', fields.get('CP3RCLINVARCLASS')))
            if classification in {'UNCERTAIN', 'UNCERTAIN_SIGNIFICANCE'}:
                classification = 'VUS'
            item = {'reportingDecision': normalized(fields.get('CLASS_JUDGEMENT')),
                    'clinicalClassification': classification, 'igvAssessment': normalized(fields.get('IGV_QC'))}
            groups.setdefault(row['findingId'], []).append(item)
    result = {}
    excluded = set(exclusion_ids(report))
    for variant in report.variants:
        identifier = variant['variantId']
        choices = {}
        for key, allowed, blank in (('reportingDecision', {'INCLUDE', 'EXCLUDE'}, 'UNREVIEWED'),
                                    ('clinicalClassification', set(CLASSES), 'UNCLASSIFIED'),
                                    ('igvAssessment', {'OK', 'ARTIFACT', 'NOT_RELIABLE'}, 'NOT_REVIEWED')):
            values = {item[key] for item in groups.get(identifier, [])}
            choices[key] = next(iter(values)) if len(values) == 1 and values <= allowed else blank
        result[identifier] = {'variantId': identifier, **choices, 'reportHighlight': False}
        if identifier in excluded:
            result[identifier]['reportingDecision'] = 'EXCLUDE'
    return result


def upgrade_review(report, review, *, seed_defaults=True):
    if review.schema_version == '4.0':
        return review
    old_classes = {item['variantId']: item['clinicalClassification'] for item in review.variant_reviews}
    document = json.loads(serialize_review_state(migrate_review_state_to_v3(review)))
    document['schemaVersion'] = '4.0'
    document['manualCnvRows'] = []
    defaults = source_defaults(report) if seed_defaults else {}
    for item in document['variantReviews']:
        if old_classes[item['variantId']] in CLASSES:
            item['clinicalClassification'] = old_classes[item['variantId']]
        item['igvAssessment'] = IGV.get(item['igvAssessment'], item['igvAssessment'])
        defaults.pop(item['variantId'], None)
    document['variantReviews'].extend(defaults.values())
    # Seed only new review entries. Existing human report choices stay intact.
    existing = {item['findingId'] for item in document['findingReviews']}
    if seed_defaults:
        for table in report.source_tables:
            if table['kind'] != 'RNA' or not table['fileName'].casefold().endswith('withqc.xlsx'):
                continue
            for row in table['rows']:
                if row['findingId'] not in existing:
                    document['findingReviews'].append({'findingId':row['findingId'],
                        'reportingDecision':'INCLUDE' if row.get('sourceApproved') else 'EXCLUDE', 'reportHighlight':False})
                    existing.add(row['findingId'])
    return validate_review_state(document, report=report)
