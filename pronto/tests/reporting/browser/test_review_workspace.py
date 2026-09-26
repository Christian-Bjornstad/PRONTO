import json
from pathlib import Path

import pytest

from pronto.tests.reporting.browser.test_report import _page, _serve, browser, playwright
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html
from pronto_report.serialization import deserialize_review_state


def test_selection_and_qc_are_preserved_in_download(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            assert page.locator('#panel-variant-review').is_visible()
            row = page.locator('#variant-table tbody tr').first
            row.locator('[data-include-variant]').click()
            assert row.locator('[data-include-variant]').get_attribute('aria-pressed') == 'true'
            assert row.locator('[data-review-field="clinicalClassification"]').input_value() == 'UNCLASSIFIED'
            page.get_by_role('tab', name='Molekylært tumorboard').click()
            assert 'CHEK2' in page.locator('#board-findings').inner_text()
            page.get_by_role('tab', name='Sekvenserings-QC').click()
            page.locator('#qc-review-status').select_option('CONDITIONAL')
            page.locator('#qc-review-comment').fill('Demo: kontroller dybde.')
            page.get_by_role('tab', name='Variantgjennomgang').click()
            with page.expect_download() as pending:
                page.get_by_role('button', name='Last ned ReviewState').click()
            saved = json.loads(Path(pending.value.path()).read_text(encoding='utf-8'))
            assert saved['runQcAssessment'] == {'status': 'CONDITIONAL', 'comment': 'Demo: kontroller dybde.'}
            assert any(v['variantId'] == report.variants[0]['variantId'] and v['reportingDecision'] == 'INCLUDE' for v in saved['variantReviews'])
            assert diagnostics == []
        finally:
            context.close()


@pytest.mark.parametrize('failure', ['conflict', 'server', 'network'])
def test_failed_save_preserves_workspace_and_blocks_audited_print(browser, failure):
    report = build_report()
    html = render_html(
        report, draft_review(report), inline_assets=True,
        save_url='/save/', csrf_token='test', actor_id='1',
        require_initials=True, print_url='/print/',
    )
    commands = []
    print_requests = []
    comment = 'Kontroller dybde før ferdigstilling. ÆØÅ <behold teksten>.'
    with _serve(html) as url:
        context, page, diagnostics, _requests = _page(browser, html)
        try:
            def fail_save(route):
                commands.append(json.loads(route.request.post_data))
                if failure == 'network':
                    route.abort('failed')
                else:
                    route.fulfill(
                        status=409 if failure == 'conflict' else 503,
                        content_type='application/json',
                        body=json.dumps({'error': {
                            'code': 'REVISION_CONFLICT' if failure == 'conflict' else 'UNAVAILABLE',
                            'currentRevision': 3,
                        }}),
                    )

            page.route('**/save/', fail_save)
            page.route('**/print/', lambda route: (
                print_requests.append(route.request.url), route.abort('failed'),
            ))
            page.goto(url)
            row = page.locator('#variant-table tbody tr').first
            row.locator('[data-include-variant]').click()
            page.get_by_role('tab', name='Sekvenserings-QC').click()
            page.locator('#qc-review-status').select_option('CONDITIONAL')
            page.locator('#qc-review-comment').fill(comment)
            assert commands == []
            page.locator('#save-btn').click()
            page.locator('#declared-initials').fill('abø')
            page.locator('#initials-confirm').click()
            playwright.expect(page.locator('#save-error')).to_be_visible()
            playwright.expect(page.locator('#save-btn')).to_be_enabled()
            assert len(commands) == 1
            assert commands[0]['baseRevision'] == 1
            assert commands[0]['declaredInitials'] == 'ABØ'
            assert commands[0]['draft']['runQcAssessment'] == {
                'status': 'CONDITIONAL', 'comment': comment,
            }
            assert page.locator('#qc-review-status').input_value() == 'CONDITIONAL'
            assert page.locator('#qc-review-comment').input_value() == comment
            assert page.locator('#dirty-lbl').inner_text() == 'Ulagret gjennomgang'
            if failure == 'conflict':
                playwright.expect(page.locator('#save-error')).to_contain_text('revisjon 3')
            with page.expect_download() as pending:
                page.locator('#export-local-draft').click()
            exported = deserialize_review_state(
                Path(pending.value.path()).read_text(encoding='utf-8'), report=report,
            )
            assert exported.revision == 1
            assert exported.run_qc_assessment == {'status': 'CONDITIONAL', 'comment': comment}
            assert any(v['variantId'] == report.variants[0]['variantId'] and
                       v['reportingDecision'] == 'INCLUDE' for v in exported.variant_reviews)
            page.get_by_role('tab', name='Variantgjennomgang').click()
            assert row.locator('[data-include-variant]').get_attribute('aria-pressed') == 'true'
            page.get_by_role('tab', name='Molekylært tumorboard').click()
            assert 'CHEK2' in page.locator('#board-findings').inner_text()
            page.locator('#print-mdt-btn').click()
            playwright.expect(page.locator('#print-status')).to_have_text('Lagre endringene før utskrift.')
            assert page.locator('#initials-dialog').is_visible() is False
            assert print_requests == []
            expected_error = {'conflict': '409', 'server': '503', 'network': 'ERR_FAILED'}[failure]
            assert all(expected_error in message for message in diagnostics)
        finally:
            context.close()
