"""Included variant judgments must survive read-only HTML export."""
from dataclasses import replace
import pytest

from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html


@pytest.mark.parametrize('snapshot', [False, True])
def test_included_comment_and_classification_survive_server_rendering(snapshot):
    report = build_report()
    draft = draft_review(report)
    activity = dict(draft.variant_reviews[0], reportingDecision='INCLUDE',
                    comment='Kontrollert <ikke HTML> & diskutert i MDT.')
    review = replace(draft, variant_reviews=(activity,))
    html = render_html(report, review, inline_assets=True, snapshot=snapshot)
    board = html.split('id="board-findings"', 1)[1].split('</ul>', 1)[0]
    assert 'Kontrollert &lt;ikke HTML&gt; &amp; diskutert i MDT.' in board
    assert 'Klassifikasjon: Patogen' in board
    # The source contains two TERT occurrences, but the report includes it once.
    assert board.count('<li>') == 1


def test_excluded_variant_comment_does_not_leak_into_board_export():
    report = build_report()
    draft = draft_review(report)
    excluded = dict(draft.variant_reviews[0], comment='Skal ikke inn i sluttrapporten')
    html = render_html(report, replace(draft, variant_reviews=(excluded,)), inline_assets=True, snapshot=True)
    board = html.split('id="panel-tumour-board"', 1)[1].split('</section>', 1)[0]
    assert 'Skal ikke inn i sluttrapporten' not in board
