import json
from dataclasses import replace

import pytest

from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html
from pronto_report.serialization import serialize_review_state


@pytest.mark.parametrize(('timestamp', 'expected'), [
    ('2026-01-15T12:00:00Z', '15.01.2026 13:00:00 CET'),
    ('2026-07-15T12:00:00Z', '15.07.2026 14:00:00 CEST'),
    ('2026-03-29T00:59:59Z', '29.03.2026 01:59:59 CET'),
    ('2026-03-29T01:00:00Z', '29.03.2026 03:00:00 CEST'),
    ('2026-10-25T00:30:00Z', '25.10.2026 02:30:00 CEST'),
    ('2026-10-25T01:30:00Z', '25.10.2026 02:30:00 CET'),
    ('2026-10-08T14:00:00+02:00', '08.10.2026 14:00:00 CEST'),
    ('2026-10-08', '2026-10-08'),
    ('2026-10-08T12:00:00', '2026-10-08T12:00:00'),
    ('invalid', 'invalid'),
    (None, ''),
])
def test_display_time_uses_oslo_with_dst_and_preserves_unzoned_values(timestamp, expected):
    from pronto_report.renderers.display_time import oslo_time
    assert oslo_time(timestamp) == expected


def test_signoff_displays_oslo_without_changing_saved_timestamp():
    report = build_report()
    review = replace(draft_review(report), status='FINAL',
                     finalized_at='2026-09-22T13:00:00Z', finalized_by='reviewer-002')
    original = serialize_review_state(review)
    html = render_html(report, review)
    assert '<time datetime="2026-09-22T13:00:00Z">22.09.2026 15:00:00 CEST</time>' in html
    assert json.loads(original)['finalizedAt'] == '2026-09-22T13:00:00Z'
    assert serialize_review_state(review) == original


def test_saved_correction_time_matches_in_workspace_and_export():
    from pronto.tests.reporting.test_summary_html import _saved_review
    from pronto_report.renderers.summary_html import render_summary_html
    report = build_report()
    review = _saved_review(report)
    assert '29.09.2026 09:06:49 CEST' in render_html(report, review)
    assert '29.09.2026 09:06:49 CEST' in render_summary_html(report, review, export_initials='AB')
    assert review.value_corrections[0]['timestamp'] == '2026-09-29T07:06:49Z'
