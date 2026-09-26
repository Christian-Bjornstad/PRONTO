import json
from pronto.tests.reporting.browser.test_report import _page, _serve, browser, playwright
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto_report.renderers.html import render_html


def test_initials_dialog_cancel_validation_save_and_print_failure(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True,
        save_url='/save/', csrf_token='test', actor_id='1',
        require_initials=True, print_url='/print/')
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        commands = []
        try:
            def save(route):
                command = json.loads(route.request.post_data)
                commands.append(command)
                review = {**command['draft'], 'revision': 2,
                    'lastSavedAttribution': {'declaredInitials': command['declaredInitials'], 'method': 'SELF_REPORTED'}}
                route.fulfill(status=201, content_type='application/json', body=json.dumps({'review': review}))
            page.route('**/save/', save)
            page.route('**/print/', lambda route: route.fulfill(status=503, content_type='application/json', body='{}'))
            page.goto(url)
            page.locator('[data-include-variant]').first.click()
            page.locator('#save-btn').click()
            page.locator('#initials-cancel').click()
            assert commands == []
            page.locator('#save-btn').click()
            page.locator('#declared-initials').fill('<x>')
            page.locator('#initials-confirm').click()
            assert page.locator('#initials-dialog').is_visible()
            assert commands == []
            page.locator('#declared-initials').fill('abø')
            page.locator('#initials-confirm').click()
            playwright.expect(page.locator('#dirty-lbl')).to_have_text('Alle endringer lagret')
            assert commands[0]['declaredInitials'] == 'ABØ'
            assert page.locator('#review-attribution').inner_text().find('ABØ') >= 0
            page.get_by_role('tab', name='Molekylært tumorboard').click()
            page.locator('#print-mdt-btn').click()
            page.locator('#declared-initials').fill('CD')
            page.locator('#initials-confirm').click()
            playwright.expect(page.locator('#print-status')).to_contain_text('ikke loggført')
            assert page.locator('body').get_attribute('class') != 'print-mdt'
            assert all('503' in message for message in diagnostics)
        finally:
            context.close()


def test_print_retry_reuses_id_and_only_prints_after_acknowledgment(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True,
        save_url='/save/', csrf_token='test', actor_id='1', require_initials=True, print_url='/print/')
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        commands = []
        try:
            page.add_init_script("window.printEvents=0; addEventListener('beforeprint',()=>window.printEvents++);")
            def print_route(route):
                command = json.loads(route.request.post_data)
                commands.append(command)
                if len(commands) == 1:
                    route.fulfill(status=503, content_type='application/json', body='{}')
                else:
                    route.fulfill(status=201, content_type='application/json', body=json.dumps({
                        **command, 'reportId': report.report_id, 'method': 'SELF_REPORTED',
                        'action': 'PRINT_REQUESTED', 'requestedAt': '2026-09-26T12:00:00Z'}))
            page.route('**/print/', print_route)
            page.goto(url)
            page.get_by_role('tab', name='Molekylært tumorboard').click()
            for attempt in range(2):
                page.locator('#print-mdt-btn').click()
                page.locator('#declared-initials').fill('AB')
                page.locator('#initials-confirm').click()
                if attempt == 0:
                    playwright.expect(page.locator('#print-status')).to_contain_text('ikke loggført')
                    assert page.evaluate('window.printEvents') == 0
                else:
                    playwright.expect(page.locator('#print-status')).to_contain_text('Utskrift forespurt av AB')
            assert commands[0]['requestId'] == commands[1]['requestId']
            assert page.evaluate('window.printEvents') == 1
        finally:
            context.close()
