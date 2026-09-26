import json
import pytest

from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto_report.migration import migrate_review_state_v1
from pronto_report.serialization import serialize_review_state, deserialize_review_state
from pronto_report.review.contracts import SaveDraftRequest, ReviewCommandError


def test_normalize_initials():
    from pronto_report.review.attribution import normalize_initials
    assert normalize_initials(' abø ') == 'ABØ'


@pytest.mark.parametrize('value', [None, 7, '', 'A', 'ABCDEFGHI', '<b>AB</b>', 'A B', 'АB', 'ßa'])
def test_reject_invalid_initials(value):
    from pronto_report.review.attribution import normalize_initials
    with pytest.raises(ReviewCommandError) as error:
        normalize_initials(value)
    assert error.value.code == 'INVALID_INITIALS'


def test_historical_and_attributed_review_round_trip():
    report = build_report()
    old = serialize_review_state(migrate_review_state_v1(draft_review(report)))
    assert serialize_review_state(deserialize_review_state(old, report=report)) == old
    raw = json.loads(old)
    raw['lastSavedAttribution'] = {'declaredInitials': 'ABØ', 'method': 'SELF_REPORTED'}
    result = deserialize_review_state(json.dumps(raw), report=report)
    assert json.loads(serialize_review_state(result))['lastSavedAttribution'] == raw['lastSavedAttribution']


@pytest.mark.parametrize('initials', ['AB\n', 'AB\r\n', ' AB', 'ab', 'AB\u2028'])
def test_stored_attribution_requires_already_normalized_initials(initials):
    from pronto_report.validation import ContractValidationError
    report = build_report()
    raw = json.loads(serialize_review_state(migrate_review_state_v1(draft_review(report))))
    raw['lastSavedAttribution'] = {'declaredInitials': initials, 'method': 'SELF_REPORTED'}
    with pytest.raises(ContractValidationError):
        deserialize_review_state(json.dumps(raw), report=report)


def test_command_accepts_initials_without_relaxing_unknown_fields():
    payload = {'schemaVersion': '1.0', 'reportId': 'report', 'baseRevision': 1, 'draft': {}, 'declaredInitials': 'ab'}
    assert SaveDraftRequest.from_dict(payload).declared_initials == 'AB'
    with pytest.raises(ReviewCommandError):
        SaveDraftRequest.from_dict({**payload, 'verified': True})


@pytest.mark.parametrize('snapshot', [False, True])
def test_final_report_labels_declared_finalizer_not_technical_actor(snapshot):
    from dataclasses import replace
    from pronto_report.renderers.html import render_html
    report = build_report()
    review = replace(migrate_review_state_v1(draft_review(report)), status='FINAL',
        finalized_by='1', finalized_at='2026-09-26T12:00:00Z',
        finalization_attribution={'declaredInitials': 'CD', 'method': 'SELF_REPORTED'})
    html = render_html(report, review, snapshot=snapshot, inline_assets=True)
    assert 'Ferdigstilt av 1' not in html
    assert 'Signert av 1' not in html
    assert 'Ferdigstilt av CD' in html


@pytest.mark.parametrize('snapshot', [False, True])
@pytest.mark.parametrize('initials', [None, 'ABØ'])
def test_board_signoff_uses_saved_initials_and_revision_not_technical_user(snapshot, initials):
    from dataclasses import replace
    from pronto_report.renderers.html import render_html
    report = build_report()
    review = replace(migrate_review_state_v1(draft_review(report)),
        reviewer={'reviewerId': 'local-demo-service'}, revision=3,
        last_saved_attribution=({'declaredInitials': initials, 'method': 'SELF_REPORTED'} if initials else None))
    html = render_html(report, review, snapshot=snapshot, inline_assets=True)
    assert 'Gjennomgås av: local-demo-service' not in html
    assert 'id="board-saved-attribution"' in html
    assert ('Sist lagret av: ABØ (selvoppgitte initialer)' if initials else
            'Sist lagret av: initialer ikke registrert') in html
    assert 'id="board-saved-revision">Lagret revisjon: 3</p>' in html
