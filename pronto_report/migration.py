"""Explicit contract migrations; source documents remain unchanged."""

from __future__ import annotations

import json

from pronto_report.models import ReviewState
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import validate_review_state


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
