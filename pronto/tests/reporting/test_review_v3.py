import json

import pytest

from pronto_report import migration
from pronto_report.serialization import serialize_review_state, deserialize_review_state
from pronto_report.validation import validate_review_state, ContractValidationError
from pronto.tests.reporting.test_review_migration import v2_document


def v3_review():
    assert hasattr(migration, 'migrate_review_state_to_v3'), 'v3 migration is missing'
    return migration.migrate_review_state_to_v3(validate_review_state(v2_document()))


def test_v3_migration_preserves_text_and_maps_uncertain_to_vus():
    review = v3_review()
    document = json.loads(serialize_review_state(review))
    assert review.schema_version == '3.0'
    assert review.variant_reviews[0]['clinicalClassification'] == 'VUS'
    assert review.variant_reviews[0]['reportHighlight'] is False
    assert document['sectionQc']['rna']['status'] == 'NOT_REVIEWED'
    assert document['presentationFigures'] == []
    assert document['notes']['summary'] == 'Oppsummering'
    assert document['notes']['history'] == ''
    assert deserialize_review_state(serialize_review_state(review)) == review


def test_v3_keeps_legacy_pathogenic_without_reclassifying_as_oncogenic():
    old = v2_document()
    old['variantReviews'][0]['clinicalClassification'] = 'PATHOGENIC'
    assert hasattr(migration, 'migrate_review_state_to_v3'), 'v3 migration is missing'
    review = migration.migrate_review_state_to_v3(validate_review_state(old))
    assert review.variant_reviews[0]['clinicalClassification'] == 'UNCLASSIFIED'
    assert review.variant_reviews[0]['legacyClinicalClassification'] == 'PATHOGENIC'
    assert old['variantReviews'][0]['clinicalClassification'] == 'PATHOGENIC'


@pytest.mark.parametrize('field,value', [('reportHighlight', 'yes'), ('clinicalClassification','PATHOGENIC')])
def test_v3_rejects_ambiguous_class_and_non_boolean_highlight(field, value):
    document = json.loads(serialize_review_state(v3_review()))
    document['variantReviews'][0][field] = value
    with pytest.raises(ContractValidationError):
        validate_review_state(document)
