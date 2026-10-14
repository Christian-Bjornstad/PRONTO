"""Explicit source defaults; saved human choices always take precedence."""
import json

from pronto_report.migration import migrate_review_state_to_v3
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import validate_review_state

CLASSES = ('BENIGN', 'LIKELY_BENIGN', 'VUS', 'LIKELY_PATHOGENIC', 'PATHOGENIC',
           'ONCOGENIC', 'LIKELY_ONCOGENIC')
IGV = {'SUPPORTS': 'OK', 'DOES_NOT_SUPPORT': 'ARTIFACT', 'INCONCLUSIVE': 'NOT_RELIABLE'}


def normalized(value):
    return str(value or '').strip().upper().replace(' ', '_').replace('-', '_')


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
    for variant in report.variants:
        identifier = variant['variantId']
        choices = {}
        for key, allowed, blank in (('reportingDecision', {'INCLUDE', 'EXCLUDE'}, 'UNREVIEWED'),
                                    ('clinicalClassification', set(CLASSES), 'UNCLASSIFIED'),
                                    ('igvAssessment', {'OK', 'ARTIFACT', 'NOT_RELIABLE'}, 'NOT_REVIEWED')):
            values = {item[key] for item in groups.get(identifier, [])}
            choices[key] = next(iter(values)) if len(values) == 1 and values <= allowed else blank
        result[identifier] = {'variantId': identifier, **choices, 'reportHighlight': False}
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
    return validate_review_state(document, report=report)
