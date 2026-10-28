import json

from playwright.sync_api import expect

from pronto.tests.reporting.browser.test_report import browser,_serve,_page
from pronto.tests.reporting.test_review_v4 import cnv_case
from pronto_report.renderers.html import render_html


def test_table_modes_keep_manual_inputs_inside_expanded_workspace(browser):
    report,review=cnv_case()
    with _serve(render_html(report,review,inline_assets=True)) as url:
        context,page,errors,_=_page(browser,'')
        try:
            page.goto(url);page.locator('#edit-btn').click();page.locator('#tab-cnv-plots').click()
            table=page.locator('#test-cnv')
            workspace=table.locator('xpath=ancestor::*[contains(@class,"source-table-block")]')
            modes=workspace.locator('.table-view-controls')
            expect(table).to_have_attribute('data-table-view','compact')
            manual=table.locator('[data-manual-field="Tumor_CN"]').first
            manual.fill('1,25')
            modes.get_by_role('button',name='Full table',exact=True).click()
            expect(manual).to_have_value('1,25')
            page.locator('[data-expand-table="test-cnv"]').click()
            dialog=page.get_by_role('dialog',name='Expanded review table')
            dialog.locator('.table-view-controls').get_by_role('button',name='Table',exact=True).click()
            expect(manual).to_have_value('1,25')
            dialog.get_by_role('button',name='Close table',exact=True).click()
            expect(modes).to_have_count(1)
            manual.fill('-1')
            page.locator('#tab-variant-review').click()
            page.get_by_role('button',name='Download ReviewState',exact=True).click()
            expect(table).to_have_attribute('data-table-view','full')
            expect(page.locator('#review-feedback')).to_contain_text('Correct invalid values')
            assert errors==[]
        finally:context.close()


def test_variant_compact_search_still_finds_hidden_source_fields(browser):
    report,review=cnv_case()
    from dataclasses import replace
    variant=report.variants[0]
    table={'tableId':'hidden-source','kind':'VARIANTS','headers':['Internal_technical_column'],
           'rows':[{'findingId':variant['variantId'],'occurrenceId':variant['occurrenceId'],'values':['HIDDEN-SEARCH-TOKEN']} ]}
    report=replace(report,source_tables=(*report.source_tables,table))
    with _serve(render_html(report,review,inline_assets=True)) as url:
        context,page,errors,_=_page(browser,'')
        try:
            page.goto(url);page.locator('#tab-variant-review').click()
            table=page.locator('#variant-table')
            hidden=table.get_by_role('columnheader',name='Internal_technical_column',exact=True,include_hidden=True)
            expect(hidden).not_to_be_visible()
            page.locator('#variant-search').fill('HIDDEN-SEARCH-TOKEN')
            visible=table.locator('tbody tr:visible')
            expect(visible).to_have_count(1)
            assert visible.get_attribute('data-occurrence-id')==variant['occurrenceId']
            modes=table.locator('xpath=ancestor::*[contains(@class,"table-view-workspace")]').locator('.table-view-controls')
            modes.get_by_role('button',name='Full table',exact=True).click()
            expect(hidden).to_be_visible()
            page.set_viewport_size({'width':375,'height':812})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert errors==[]
        finally:context.close()
