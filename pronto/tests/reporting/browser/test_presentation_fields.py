import json
from playwright.sync_api import expect
from pronto.tests.reporting.browser.test_report import _page, _serve, browser
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto_report.review.source_defaults import upgrade_review
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import validate_review_state
from pronto_report.renderers.html import render_html


def test_manual_presentation_context_is_sent_with_saved_review(browser):
    report=build_report()
    data=json.loads(serialize_review_state(upgrade_review(report,draft_review(report))))
    data['variantReviews'][0].update(reportingDecision='INCLUDE',reportHighlight=True)
    review=validate_review_state(data,report=report)
    html=render_html(report,review,inline_assets=True,save_url='/save/',csrf_token='synthetic',actor_id='test-writer',actor_label='Tester')
    with _serve(html) as url:
        context,page,errors,_=_page(browser,html)
        commands=[]
        def save(route):
            body=route.request.post_data_json
            commands.append(body)
            saved={**body['draft'],'revision':body['baseRevision']+1}
            route.fulfill(status=201,content_type='application/json',body=json.dumps({'review':saved}))
        page.route('**/save/',save)
        try:
            page.goto(url)
            page.locator('#edit-btn').click()
            page.locator('#tab-tumour-board').click()
            page.locator('.presentation-annotations summary').click()
            field=page.locator('[data-presentation-field="sensitive"]').first
            field.fill('Manual treatment context')
            page.locator('[data-presentation-field="description"]').first.fill('Manual description, preserved after save.')
            # Standalone report asks for attribution; use its standard initials dialog.
            page.locator('#save-btn').click()
            initials=page.locator('#declared-initials')
            if initials.is_visible():
                initials.fill('AB')
                page.locator('#initials-confirm').click()
            expect(page.locator('#dirty-lbl')).to_have_text('All changes saved')
            assert commands[0]['draft']['variantReviews'][0]['presentation']['sensitive']=='Manual treatment context'
            assert errors==[]
        finally:
            context.close()
