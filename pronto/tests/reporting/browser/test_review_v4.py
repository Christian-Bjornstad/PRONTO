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
        row.locator('[data-manual-field="Tumor_FC"]').fill('3,5')
        row.get_by_role('button',name='Include',exact=False).click()
        row.get_by_role('button',name='Gain',exact=False).click()
        row.locator('[data-cn-field="cytoband"]').fill('8q24')
        page.locator('[data-section-qc-comment="cnv"]').first.fill('Confirm segmentation')
        page.locator('[data-expand-table="test-cnv"]').click()
        dialog=page.get_by_role('dialog',name='Expanded review table')
        assert dialog.is_visible()
        dialog.get_by_role('slider',name='Table zoom').fill('125')
        assert dialog.locator('output').inner_text()=='125%'
        dialog.get_by_role('button',name='Close table',exact=True).click()
        assert page.locator('#test-cnv tbody tr').first.locator('[data-manual-field="Gene_Symbol"]').input_value()=='MYC'
        page.get_by_role('tab',name='Variant review').click()
        with page.expect_download() as pending:
            page.get_by_role('button',name='Download ReviewState',exact=True).click()
        saved=json.loads(Path(pending.value.path()).read_text())
        assert saved['manualCnvRows'][0]['geneSymbol']=='MYC'
        assert saved['manualCnvRows'][0]['tumorFc']==3.5
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
