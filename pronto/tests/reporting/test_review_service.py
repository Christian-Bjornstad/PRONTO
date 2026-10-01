"""Framework-neutral review commands, revision conflicts, and audit writes."""

import json
from datetime import datetime, timezone

import pytest

from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.migration import migrate_review_state_v1
from pronto_report.review.contracts import FinalizeRequest, ReviewCommandError, SaveDraftRequest
from pronto_report.review import contracts
from pronto_report.review.service import ReviewCommandService
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import validate_review_state


class FakeRepository:
    def __init__(self, saved):
        self.saved = saved
        self.audit = []
        self.force_conflict = False

    def latest(self, report_id):
        return self.saved if self.saved.report_id == report_id else None

    def commit(self, report_id, base_revision, review, audit):
        if self.force_conflict or self.saved.report_id != report_id or self.saved.revision != base_revision:
            return False
        self.saved = review
        self.audit.append(audit)
        return True


class FakeAuthorizer:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def can_review(self, actor_id, report_id):
        return self.allowed and actor_id == "biologist-001" and bool(report_id)


@pytest.fixture
def setup():
    report = build_report()
    saved = migrate_review_state_v1(draft_review(report))
    repo = FakeRepository(saved)
    clock = lambda: datetime(2026, 9, 23, 10, 0, tzinfo=timezone.utc)
    service = ReviewCommandService(repo, FakeAuthorizer(), clock=clock)
    return report, saved, repo, service


def document(review):
    return json.loads(serialize_review_state(review))


def test_save_validated_full_draft_advances_revision_and_writes_audit_atomically(setup):
    report, saved, repo, service = setup
    draft = document(saved)
    draft["notes"]["summary"] = "Drøftet med kliniker"
    request = SaveDraftRequest("1.0", report.report_id, saved.revision, draft)

    response = service.save(request, actor_id="biologist-001", report=report)

    assert response.schema_version == "1.0"
    assert response.review.revision == saved.revision + 1
    assert response.review.notes["summary"] == "Drøftet med kliniker"
    assert response.review.reviewer["reviewerId"] == "biologist-001"
    assert response.review.updated_at == "2026-09-23T10:00:00Z"
    assert response.audit.action == "SAVE_DRAFT"
    assert response.audit.actor_id == "biologist-001"
    assert response.audit.revision == response.review.revision
    assert repo.saved == response.review
    assert repo.audit == [response.audit]
    wire = response.as_dict()
    assert wire["schemaVersion"] == "1.0"
    assert wire["review"]["revision"] == saved.revision + 1
    assert wire["audit"] == {
        "reportId": report.report_id,
        "actorId": "biologist-001",
        "action": "SAVE_DRAFT",
        "revision": saved.revision + 1,
        "timestamp": "2026-09-23T10:00:00Z",
    }


def test_repeated_or_stale_save_is_conflict_without_mutation(setup):
    report, saved, repo, service = setup
    request = SaveDraftRequest("1.0", report.report_id, saved.revision, document(saved))
    service.save(request, actor_id="biologist-001", report=report)
    before = (repo.saved, list(repo.audit))

    with pytest.raises(ReviewCommandError) as caught:
        service.save(request, actor_id="biologist-001", report=report)

    assert caught.value.code == "REVISION_CONFLICT"
    assert caught.value.http_status == 409
    assert caught.value.current_revision == repo.saved.revision
    assert (repo.saved, repo.audit) == before


def test_versioned_wire_request_rejects_extra_fields_and_wrong_types(setup):
    report, saved, _, _ = setup
    payload = {
        "schemaVersion": "1.0", "reportId": report.report_id,
        "baseRevision": saved.revision, "draft": document(saved),
    }
    assert SaveDraftRequest.from_dict(payload).base_revision == saved.revision
    assert FinalizeRequest.from_dict(payload).report_id == report.report_id
    for invalid in ({**payload, "extra": "ignored?"}, {**payload, "baseRevision": True}):
        with pytest.raises(ReviewCommandError) as caught:
            SaveDraftRequest.from_dict(invalid)
        assert caught.value.as_dict()["error"]["code"] == "INVALID_COMMAND"
        assert caught.value.http_status == 422


def test_repository_compare_and_swap_race_returns_conflict_without_audit(setup):
    report, saved, repo, service = setup
    repo.force_conflict = True
    request = SaveDraftRequest("1.0", report.report_id, saved.revision, document(saved))

    with pytest.raises(ReviewCommandError, match="revision") as caught:
        service.save(request, actor_id="biologist-001", report=report)

    assert caught.value.http_status == 409
    assert repo.saved == saved
    assert repo.audit == []


@pytest.mark.parametrize("change", [
    {"schemaVersion": "1.0"},
    {"status": "FINAL"},
    {"reportId": "different-report"},
    {"notes": {"summary": "missing other keys"}},
])
def test_invalid_draft_cannot_mutate_review_or_audit(setup, change):
    report, saved, repo, service = setup
    draft = document(saved)
    draft.update(change)
    request = SaveDraftRequest("1.0", report.report_id, saved.revision, draft)

    with pytest.raises(ReviewCommandError) as caught:
        service.save(request, actor_id="biologist-001", report=report)

    assert caught.value.http_status == 422
    assert repo.saved == saved
    assert repo.audit == []


def test_unauthorized_save_has_no_mutation(setup):
    report, saved, repo, _ = setup
    service = ReviewCommandService(repo, FakeAuthorizer(False), clock=lambda: datetime.now(timezone.utc))
    request = SaveDraftRequest("1.0", report.report_id, saved.revision, document(saved))

    with pytest.raises(ReviewCommandError) as caught:
        service.save(request, actor_id="biologist-001", report=report)

    assert caught.value.http_status == 403
    assert repo.audit == []


def test_save_rejects_unknown_variant_id_and_spoofed_new_correction_author(setup):
    report, saved, repo, service = setup
    invalid_variant = document(saved)
    invalid_variant["variantReviews"].append({
        "variantId": "not-in-report",
        "reportingDecision": "INCLUDE",
        "clinicalClassification": "PATHOGENIC",
        "igvAssessment": "SUPPORTS",
    })
    invalid_correction = document(saved)
    invalid_correction["valueCorrections"].append({
        "path": "/sample/tumourType", "originalValue": report.sample.get("tumourType"),
        "correctedValue": "Lunge", "reason": "Bekreftet", "author": "someone-else",
        "timestamp": "2026-09-23T10:00:00Z",
    })
    for draft in (invalid_variant, invalid_correction):
        with pytest.raises(ReviewCommandError) as caught:
            service.save(
                SaveDraftRequest("1.0", report.report_id, saved.revision, draft),
                actor_id="biologist-001", report=report,
            )
        assert caught.value.code == "INVALID_DRAFT"
    assert repo.saved == saved
    assert repo.audit == []


def test_new_source_correction_is_bound_to_validated_path_and_server_time(setup):
    report, saved, repo, service = setup
    draft = document(saved)
    draft["valueCorrections"].append({
        "path": "/sample/tumourType", "originalValue": report.sample.get("tumourType"),
        "correctedValue": "Lunge", "reason": "Bekreftet i rekvisisjon",
        "author": "biologist-001", "timestamp": "2026-09-22T00:00:00Z",
    })
    request = SaveDraftRequest("1.0", report.report_id, saved.revision, draft)

    response = service.save(request, actor_id="biologist-001", report=report)

    assert response.review.value_corrections[-1]["timestamp"] == "2026-09-23T10:00:00Z"
    assert repo.audit[0].timestamp == "2026-09-23T10:00:00Z"


def test_unknown_correction_path_cannot_be_saved(setup):
    report, saved, repo, service = setup
    draft = document(saved)
    draft["valueCorrections"].append({
        "path": "/sample/unknown", "originalValue": None,
        "correctedValue": "x", "reason": "No source",
        "author": "biologist-001", "timestamp": "2026-09-23T10:00:00Z",
    })
    with pytest.raises(ReviewCommandError) as caught:
        service.save(SaveDraftRequest("1.0", report.report_id, saved.revision, draft), actor_id="biologist-001", report=report)
    assert caught.value.http_status == 422
    assert repo.audit == []


def test_finalize_only_clean_latest_saved_review_and_lock_future_writes(setup):
    report, saved, repo, service = setup
    request = FinalizeRequest("1.0", report.report_id, saved.revision, document(saved))

    response = service.finalize(request, actor_id="biologist-001", report=report)

    assert response.review.status == "FINAL"
    assert response.review.revision == saved.revision + 1
    assert response.review.finalized_by == "biologist-001"
    assert response.review.finalized_at == "2026-09-23T10:00:00Z"
    assert response.audit.action == "FINALIZE"
    assert repo.audit == [response.audit]
    with pytest.raises(ReviewCommandError) as caught:
        service.save(SaveDraftRequest("1.0", report.report_id, response.review.revision, document(response.review)), actor_id="biologist-001", report=report)
    assert caught.value.code == "FINAL_LOCKED"
    assert len(repo.audit) == 1


def test_finalize_rejects_unsaved_edits_and_stale_or_repeated_request(setup):
    report, saved, repo, service = setup
    dirty = document(saved)
    dirty["notes"]["summary"] = "Ulagret"
    with pytest.raises(ReviewCommandError) as caught:
        service.finalize(FinalizeRequest("1.0", report.report_id, saved.revision, dirty), actor_id="biologist-001", report=report)
    assert caught.value.code == "UNSAVED_CHANGES"
    assert repo.audit == []

    request = FinalizeRequest("1.0", report.report_id, saved.revision, document(saved))
    service.finalize(request, actor_id="biologist-001", report=report)
    with pytest.raises(ReviewCommandError) as caught:
        service.finalize(request, actor_id="biologist-001", report=report)
    assert caught.value.http_status == 409
    assert len(repo.audit) == 1


def test_reset_creates_blank_revision_and_audit(setup):
    report, saved, repo, service = setup
    edited = document(saved)
    edited['notes']['summary'] = 'Prior interpretation'
    edited['runQcAssessment'] = {'status': 'PASS', 'comment': 'Coverage checked'}
    edited['valueCorrections'] = [{
        'path': '/sample/tumourType', 'originalValue': report.sample.get('tumourType'),
        'correctedValue': 'Corrected type', 'reason': 'Source review',
        'author': 'biologist-001', 'timestamp': '2026-09-23T09:00:00Z',
    }]
    service.save(SaveDraftRequest('1.0', report.report_id, saved.revision, edited),
                 actor_id='biologist-001', report=report)
    before = repo.saved
    request = contracts.ResetDraftRequest.from_dict({
        'schemaVersion': '1.0', 'reportId': report.report_id,
        'baseRevision': before.revision, 'declaredInitials': 'AB',
    })

    response = service.reset(request, actor_id='biologist-001', report=report)

    assert response.review.revision == before.revision + 1
    assert response.review.variant_reviews == ()
    assert response.review.run_qc_assessment['status'] == 'NOT_REVIEWED'
    assert response.review.run_qc_assessment.get('comment', '') == ''
    assert response.review.notes['summary'] == ''
    assert response.review.notes['biomarkerContext'] == ''
    assert response.review.notes['additional'] == ''
    assert response.review.value_corrections == ()
    assert response.review.last_saved_attribution['declaredInitials'] == 'AB'
    assert response.audit.action == 'RESET_DRAFT'
    assert repo.audit[-1] == response.audit


def test_reset_preserves_imported_legacy_note_and_source(setup):
    report, saved, repo, service = setup
    edited = document(saved)
    edited['notes']['importedLegacyNote'] = 'Original imported context'
    repo.saved = validate_review_state(edited, report=report)
    request = contracts.ResetDraftRequest('1.0', report.report_id, saved.revision, 'AB')

    response = service.reset(request, actor_id='biologist-001', report=report)

    assert response.review.notes['importedLegacyNote'] == 'Original imported context'
    assert response.review.created_at == saved.created_at
    assert report.sample.get('tumourType') is None


def test_reset_stale_or_final_writes_nothing(setup):
    report, saved, repo, service = setup
    stale = contracts.ResetDraftRequest('1.0', report.report_id, saved.revision + 1, 'AB')
    with pytest.raises(ReviewCommandError) as caught:
        service.reset(stale, actor_id='biologist-001', report=report)
    assert caught.value.code == 'REVISION_CONFLICT'
    assert repo.saved == saved and repo.audit == []

    finalized = service.finalize(FinalizeRequest('1.0', report.report_id, saved.revision, document(saved)),
                                 actor_id='biologist-001', report=report)
    before = (repo.saved, list(repo.audit))
    with pytest.raises(ReviewCommandError) as caught:
        service.reset(contracts.ResetDraftRequest('1.0', report.report_id, finalized.review.revision, 'AB'),
                      actor_id='biologist-001', report=report)
    assert caught.value.code == 'FINAL_LOCKED'
    assert (repo.saved, repo.audit) == before
