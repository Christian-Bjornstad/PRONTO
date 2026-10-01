import json
from dataclasses import replace
from uuid import uuid4
from io import BytesIO
from PIL import Image

from pronto.tests.reporting.browser.test_report import _page, _serve, browser, playwright
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto_report.migration import migrate_review_state_to_v3
from pronto_report.renderers.html import render_html

expect=playwright.expect


def test_vus_highlight_exclude_and_qc_are_linked_and_in_explicit_save(browser):
    report=build_report();review=migrate_review_state_to_v3(draft_review(report))
    html=render_html(report,review,inline_assets=True,save_url='/save/',csrf_token='test',actor_id='7')
    context,page,errors,_requests=_page(browser,html)
    sent=[]
    try:
        def save(route):
            data=json.loads(route.request.post_data);sent.append(data)
            result=data['draft'];result['revision']+=1
            route.fulfill(status=201,content_type='application/json',body=json.dumps({'review':result}))
        page.route('**/save/',save)
        with _serve(html) as url:
            page.goto(url)
            page.get_by_role('tab',name='Key findings',exact=True).click()
            identifier=page.locator('[data-vus-variant]').first.get_attribute('data-vus-variant')
            page.locator('[data-vus-variant]').first.check()
            page.locator('[data-highlight-variant]').first.check()
            page.get_by_role('tab',name='Variant review').click()
            select=page.locator(f'select[data-variant-id="{identifier}"][data-review-field="clinicalClassification"]').first
            expect(select).to_have_value('VUS')
            page.locator(f'[data-exclude-variant="{identifier}"]').first.check()
            expect(page.locator(f'[data-exclude-variant="{identifier}"]').first).to_be_checked()
            page.locator('[data-section-qc="variants"]').first.select_option('CONDITIONAL')
            page.get_by_role('tab',name='Tumour board report').click()
            expect(page.locator('[data-section-qc="variants"]').last).to_have_value('CONDITIONAL')
            page.get_by_label('History / Reason for testing',exact=True).fill('Synthetic history')
            assert sent == []
            page.get_by_role('button',name='Save',exact=True).click()
            expect(page.locator('#dirty-lbl')).to_have_text('All changes saved')
            activity=next(a for a in sent[0]['draft']['variantReviews'] if a['variantId']==identifier)
            assert activity['reportHighlight'] is True
            assert activity['clinicalClassification']=='VUS'
            assert activity['reportingDecision']=='EXCLUDE'
            assert sent[0]['draft']['sectionQc']['variants']['status']=='CONDITIONAL'
            assert sent[0]['draft']['notes']['history']=='Synthetic history'
            assert errors == []
    finally:
        context.close()


def test_uploaded_figures_keep_caption_focus_and_order_and_pdf_requires_save(browser):
    report=build_report();review=migrate_review_state_to_v3(draft_review(report))
    html=render_html(report,review,inline_assets=True,save_url='/save/',csrf_token='test',actor_id='7',
        pdf_export_url='/pdf/',figure_upload_url='/upload/')
    context,page,errors,_=_page(browser,html);saves=[];exports=[]
    output=BytesIO();Image.new('RGB',(120,60),'green').save(output,'PNG');payload=output.getvalue()
    try:
        def upload(route):
            identifier=str(uuid4());route.fulfill(status=201,content_type='application/json',body=json.dumps({'figureId':identifier,'url':f'/reports/demo/figures/{identifier}/'}))
        def save(route):
            command=json.loads(route.request.post_data);saves.append(command);result=command['draft'];result['revision']+=1
            route.fulfill(status=201,content_type='application/json',body=json.dumps({'review':result}))
        def pdf(route):
            exports.append(json.loads(route.request.post_data));route.fulfill(status=200,content_type='application/pdf',body=b'%PDF-1.4\n%%EOF')
        page.route('**/upload/',upload);page.route('**/reports/demo/figures/**',lambda route:route.fulfill(content_type='image/png',body=payload))
        page.route('**/save/',save);page.route('**/pdf/',pdf)
        with _serve(html) as url:
            page.goto(url);page.get_by_role('tab',name='Tumour board report').click()
            page.locator('#figure-upload').set_input_files([{'name':'pathway.png','mimeType':'image/png','buffer':payload},{'name':'second.png','mimeType':'image/png','buffer':payload}])
            expect(page.locator('#figure-list textarea')).to_have_count(2)
            caption=page.get_by_label('Figure 1 caption',exact=True)
            caption.click();caption.press('ControlOrMeta+A');caption.press_sequentially('My pathway context')
            expect(caption).to_have_value('My pathway context');expect(caption).to_be_focused()
            page.get_by_role('button',name='Move down figure 1',exact=True).click()
            expect(page.get_by_label('Figure 2 caption',exact=True)).to_have_value('My pathway context')
            page.get_by_role('button',name='Presentation PDF',exact=True).click()
            expect(page.locator('#pdf-export-status')).to_have_text('Save changes before exporting a PDF.')
            assert exports==[]
            page.get_by_role('button',name='Save',exact=True).click();expect(page.locator('#dirty-lbl')).to_have_text('All changes saved')
            assert saves[0]['draft']['presentationFigures'][1]['caption']=='My pathway context'
            revised=page.get_by_label('Figure 2 caption',exact=True)
            revised.fill('Caption edited after saving')
            expect(revised).to_have_value('Caption edited after saving')
            page.get_by_role('button',name='Save',exact=True).click();expect(page.locator('#dirty-lbl')).to_have_text('All changes saved')
            assert saves[1]['draft']['presentationFigures'][1]['caption']=='Caption edited after saving'
            page.evaluate("window.requestDeclaredInitials=async()=> 'AB'")
            with page.expect_download() as download:
                page.get_by_role('button',name='Presentation PDF',exact=True).click()
            assert download.value.suggested_filename.endswith('-presentation.pdf')
            assert exports[0]['revision']==review.revision+2 and exports[0]['declaredInitials']=='AB'
            assert errors==[]
    finally: context.close()


def test_historical_snapshot_can_switch_cnv_views_and_individual_plots(browser):
    from pronto.tests.reporting.browser.test_report import ONE_PIXEL_PNG
    report=build_report()
    cnv=next(item for item in report.attachments if item['name'].endswith('_CNV_overview_plots.pdf'))
    report=replace(report,attachments=(cnv,))
    review=migrate_review_state_to_v3(draft_review(report))
    html=render_html(report,review,inline_assets=True,snapshot=True,
        plot_images={cnv['assetId']:tuple(('image/png',ONE_PIXEL_PNG) for _ in range(9))})
    context,page,errors,_=_page(browser,html)
    try:
        with _serve(html) as url:
            page.goto(url);page.get_by_role('tab',name='CNV review',exact=True).click()
            page.get_by_role('button',name='Plots',exact=True).click()
            expect(page.locator('#cnv-plots-view')).to_be_visible()
            expect(page.locator('#cnv-panel-B3')).to_be_visible();expect(page.locator('#cnv-panel-C1')).to_be_visible()
            page.get_by_role('button',name='A1',exact=True).click()
            expect(page.locator('#cnv-panel-A1')).to_be_visible();expect(page.locator('#cnv-panel-B3')).to_be_hidden()
            assert page.locator('[data-save-url]').count()==0 and errors==[]
    finally: context.close()
