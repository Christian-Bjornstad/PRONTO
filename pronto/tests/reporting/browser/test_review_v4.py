import json
from pathlib import Path
from dataclasses import replace
import pytest

from pronto.tests.reporting.browser.test_report import browser, playwright, _serve
from pronto.tests.reporting.test_review_v4 import cnv_case
from pronto_report.renderers.html import render_html


def test_manual_cnv_zoom_qc_and_download_share_one_working_copy(browser):
    report,review=cnv_case()
    context=browser.new_context(accept_downloads=True)
    page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    try:
        server=_serve(render_html(report,review,inline_assets=True))
        url=server.__enter__()
        page.goto(url)
        page.get_by_role('button',name='Edit mode: OFF').click()
        page.get_by_role('tab',name='CNV review',exact=True).click()
        page.get_by_role('button',name='Add CNV row',exact=True).click()
        row=page.locator('#test-cnv tbody tr').first
        row.locator('[data-manual-field="Gene_Symbol"]').fill('MYC')
        row.locator('[data-manual-field="Tumor_CN"]').fill('3,5')
        row.get_by_role('button',name='Include',exact=False).click()
        row.get_by_role('button',name='Gain',exact=False).click()
        row.locator('[data-cn-field="cytoband"]').fill('8q24')
        page.locator('[data-section-qc-comment="cnv"]').first.fill('Confirm segmentation')
        page.locator('[data-expand-table="test-cnv"]').click()
        dialog=page.get_by_role('dialog',name='Expanded review table')
        assert dialog.is_visible()
        baseline=row.locator('[data-manual-field="Gene_Symbol"]').bounding_box()['width']
        dialog.get_by_role('slider',name='Table zoom').fill('75')
        reduced=row.locator('[data-manual-field="Gene_Symbol"]').bounding_box()['width']
        assert reduced == pytest.approx(baseline * .75, rel=.03)
        dialog.get_by_role('slider',name='Table zoom').fill('125')
        assert row.locator('[data-manual-field="Gene_Symbol"]').bounding_box()['width'] == pytest.approx(baseline * 1.25, rel=.03)
        assert dialog.locator('output').inner_text()=='125%'
        dialog.get_by_role('button',name='Close table',exact=True).click()
        assert page.locator('#test-cnv').evaluate('(table)=>table.style.zoom')==''
        assert page.locator('#test-cnv tbody tr').first.locator('[data-manual-field="Gene_Symbol"]').input_value()=='MYC'
        page.get_by_role('tab',name='Variant review').click()
        with page.expect_download() as pending:
            page.get_by_role('button',name='Download ReviewState',exact=True).click()
        saved=json.loads(Path(pending.value.path()).read_text())
        assert saved['manualCnvRows'][0]['geneSymbol']=='MYC'
        assert saved['manualCnvRows'][0]['tumorCn']==3.5
        activity=next(i for i in saved['findingReviews'] if i['findingId']==saved['manualCnvRows'][0]['findingId'])
        assert activity['reportingDecision']=='INCLUDE' and activity['cnChange']=='GAIN' and activity['cytoband']=='8q24'
        assert saved['sectionQc']['cnv']['comment']=='Confirm segmentation'
        assert errors==[]
    finally:
        context.close()
        server.__exit__(None,None,None)


@pytest.mark.parametrize('action', ['RESET','FINALIZE','REOPEN'])
def test_working_response_and_selected_revision_wiring(browser, action):
    from pronto_report.serialization import serialize_review_state
    report,review=cnv_case()
    review=replace(review,revision=2)
    html=render_html(report,review,inline_assets=True,save_url='/working/',reset_url='/working/',
                     finalize_url='/working/',csrf_token='test',actor_id='1',actor_label='writer')
    config={'url':'/working/','reportId':report.report_id,'version':0,'revision':2,'sourceRevision':1,'csrf':'test'}
    html=html.replace('<body>','<body><script type="application/json" id="working-config">'+json.dumps(config)+'</script><button id="start-new-revision">Start new revision</button><span id="working-message"></span>')
    calls=[]
    with _serve(html) as url:
        context=browser.new_context();page=context.new_page();page.on('dialog',lambda dialog:dialog.accept())
        def respond(route):
            payload=route.request.post_data_json;calls.append(payload)
            doc=payload.get('draft',json.loads(serialize_review_state(review)))
            if payload['action']=='FINALIZE': doc={**doc,'status':'FINAL'}
            route.fulfill(status=201,content_type='application/json',body=json.dumps({'review':doc,'workingVersion':len(calls)}))
        page.route('**/working/',respond)
        try:
            page.goto(url)
            page.get_by_role('button',name='Edit mode: OFF').click()
            page.get_by_role('tab',name='CNV review',exact=True).click()
            page.locator('[data-manual-field="Gene_Symbol"]').fill('MYC')
            page.get_by_role('button',name='Save',exact=True).click()
            page.wait_for_function("document.getElementById('dirty-lbl').textContent === 'All changes saved'")
            assert calls[0]['action']=='SAVE' and calls[0]['expectedVersion']==0
            if action=='REOPEN': button=page.get_by_role('button',name='Start new revision',exact=True)
            else: button=page.get_by_role('button',name='Reset' if action=='RESET' else 'Finalize',exact=True)
            with page.expect_navigation(): button.click()
            assert calls[-1]['action']==action and calls[-1]['expectedVersion']==1
            if action=='REOPEN': assert calls[-1]['sourceRevision']==2
        finally: context.close()


def test_initial_working_draft_can_be_saved_without_edits(browser):
    report, review = cnv_case()
    html = render_html(report, review, inline_assets=True, save_url='/working/',
                       finalize_url='/working/', csrf_token='test', actor_id='1', actor_label='writer')
    config = {'url': '/working/', 'reportId': report.report_id, 'version': 0,
              'revision': review.revision, 'sourceRevision': review.revision, 'csrf': 'test'}
    html = html.replace('<body>', '<body><script type="application/json" id="working-config">'
                        + json.dumps(config) + '</script>')
    calls = []
    with _serve(html) as url:
        context = browser.new_context()
        page = context.new_page()

        def respond(route):
            payload = route.request.post_data_json
            calls.append(payload)
            route.fulfill(status=201, content_type='application/json', body=json.dumps({
                'review': payload['draft'], 'workingVersion': 1}))

        page.route('**/working/', respond)
        try:
            page.goto(url)
            assert page.locator('#dirty-lbl').inner_text() == 'Save to start working draft'
            assert page.get_by_role('button', name='Finalize', exact=True).is_disabled()
            page.get_by_role('button', name='Save', exact=True).click()
            playwright.expect(page.locator('#dirty-lbl')).to_have_text('All changes saved', timeout=3000)
            assert len(calls) == 1
            assert calls[0]['action'] == 'SAVE' and calls[0]['expectedVersion'] == 0
            assert page.get_by_role('button', name='Finalize', exact=True).is_enabled()
            assert page.get_by_role('button', name='Save', exact=True).is_disabled()
        finally:
            context.close()


@pytest.mark.parametrize('assessment, label', [('OK', 'OK'), ('ARTIFACT', 'Artifact'), ('NOT_RELIABLE', 'Not reliable')])
def test_key_findings_shows_current_igv_qc_labels(browser, assessment, label):
    report, review = cnv_case()
    variant_id = report.variants[0]['variantId']
    reviews = tuple({**item, 'igvAssessment': assessment} if item['variantId'] == variant_id else item
                    for item in review.variant_reviews)
    review = replace(review, variant_reviews=reviews)
    with _serve(render_html(report, review, inline_assets=True)) as url:
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(url)
            summary = page.locator('#key-variant-table tr[data-variant-id]').filter(
                has=page.locator(f'[data-highlight-variant="{variant_id}"]')).first
            assert summary.locator('[data-review-summary="igv"]').inner_text() == label
            choice = page.locator(f'#variant-table select[data-variant-id="{variant_id}"][data-review-field="igvAssessment"]').first
            choice.select_option('NOT_REVIEWED')
            assert summary.locator('[data-review-summary="igv"]').inner_text() == 'Not reviewed'
            choice.select_option(assessment)
            assert summary.locator('[data-review-summary="igv"]').inner_text() == label
        finally:
            context.close()


def test_invalid_manual_cnv_value_cannot_download_a_stale_review(browser):
    report, review = cnv_case()
    with _serve(render_html(report, review, inline_assets=True)) as url:
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        try:
            page.goto(url)
            page.get_by_role('button', name='Edit mode: OFF').click()
            page.get_by_role('tab', name='CNV review', exact=True).click()
            value = page.locator('[data-manual-field="Tumor_CN"]').first
            value.fill('invalid')
            page.get_by_role('tab', name='Variant review').click()
            with pytest.raises(playwright.TimeoutError):
                with page.expect_download(timeout=500):
                    page.get_by_role('button', name='Download ReviewState', exact=True).click()
            assert 'Correct invalid values' in page.locator('#review-feedback').inner_text()
            page.get_by_role('tab', name='CNV review', exact=True).click()
            value.fill('3,5')
            page.get_by_role('tab', name='Variant review').click()
            with page.expect_download() as pending:
                page.get_by_role('button', name='Download ReviewState', exact=True).click()
            saved = json.loads(Path(pending.value.path()).read_text())
            assert saved['manualCnvRows'][0]['tumorCn'] == 3.5
        finally:
            context.close()
