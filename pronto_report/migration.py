"""Explicit contract migrations; source documents remain unchanged."""

from __future__ import annotations

import json

from pronto_report.models import ReviewState
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import validate_review_state


EXTRA_NOTES = ('history', 'variantDescription', 'references', 'followUp',
               'assayMethods', 'clinicalEvidence', 'clinicalTrials', 'patientDetails')
SECTION_QC = ('variants', 'cnv', 'rna', 'signatures')


def migrate_review_state_to_v3(review: ReviewState) -> ReviewState:
    """Return a detached current working copy; never write a stored revision."""
    if review.schema_version == '3.0':
        return review
    if review.schema_version == '1.0':
        review = migrate_review_state_v1(review)
    document = json.loads(serialize_review_state(review))
    document['schemaVersion'] = '3.0'
    for item in document['variantReviews']:
        old = item['clinicalClassification']
        item['clinicalClassification'] = 'VUS' if old == 'UNCERTAIN' else 'UNCLASSIFIED'
        if old not in {'UNCERTAIN', 'UNCLASSIFIED'}:
            item['legacyClinicalClassification'] = old
        item['reportHighlight'] = False
    document['notes'].update({name: '' for name in EXTRA_NOTES})
    document.update(findingReviews=[], biomarkerReviews=[], presentationFigures=[],
                    sectionQc={key: {'status': 'NOT_REVIEWED'} for key in SECTION_QC})
    return validate_review_state(document)


def migrate_review_state_v1(review: ReviewState) -> ReviewState:
    """Move v1 text to a labeled legacy field without inferring its meaning."""
    if review.schema_version != "1.0":
        raise ValueError("Expected ReviewState v1 for migration")

    document = json.loads(serialize_review_state(review))
    legacy_text = document.pop("reportNotes")
    document["schemaVersion"] = "2.0"
    document["notes"] = {
        "summary": "",
        "biomarkerContext": "",
        "additional": "",
        "importedLegacyNote": legacy_text,
    }
    return validate_review_state(document)
