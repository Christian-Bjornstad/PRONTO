"""Reference-density workspace preserves facts and previews unique selections."""
from dataclasses import replace

import pytest

from pronto.tests.reporting.browser.test_report import _page, _serve, browser, playwright
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html


def test_compact_details_and_preview_count_follow_unique_selection(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            preview = page.get_by_role('link', name='Preview report · 0 selected')
            playwright.expect(preview).to_be_visible()
            headings = page.locator('#variant-table thead').text_content()
            assert 'Forekomst-ID' not in headings
            assert 'Source tier' not in headings
            for label in ('AF tumour', 'Tumour DNA depth', 'OncoKB', 'Biomarker list'):
                assert label in headings
            row = page.locator('#variant-table tbody tr').first
            row.get_by_text('Details', exact=True).click()
            assert report.variants[0]['occurrenceId'] in row.locator('details').inner_text()
            assert report.variants[0]['variantId'] in row.locator('details').inner_text()
            assert 'Source tier' in row.locator('details').inner_text()
            duplicate_id = report.variants[2]['variantId']
            duplicates = page.locator(f'[data-include-variant="{duplicate_id}"]')
            assert duplicates.count() == 2
            duplicates.first.click()
            playwright.expect(page.locator('#preview-report')).to_have_text('Preview report · 1 selected')
            page.locator('#variant-search').fill('CHEK2')
            page.locator('#preview-report').focus()
            page.keyboard.press('Enter')
            playwright.expect(page.locator('#panel-tumour-board')).to_be_visible()
            playwright.expect(page.locator('#tab-tumour-board')).to_be_focused()
            assert page.locator('#board-findings li').count() == 1
            assert 'TERT' in page.locator('#board-findings').inner_text()
            page.get_by_role('tab', name='Variant review').click()
            page.locator('#variant-search').fill('')
            duplicates.last.click()
            playwright.expect(page.locator('#preview-selected-count')).to_have_text('0')
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_variant_review_keeps_primary_facts_and_choices_in_one_desktop_view(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, _requests = _page(browser, html, width=1440)
        try:
            page.goto(url)
            row = page.locator('#variant-table tbody tr').first
            headers = page.locator('#variant-table thead th').all_text_contents()
            assert [item.strip() for item in headers] == [
                'Gene', 'Protein', 'Coding', 'AF tumour (0–1)', 'Tumour DNA depth',
                'OncoKB', 'Biomarker list', 'Report', 'Clinical class', 'Details',
            ]
            assert page.locator('#variant-table').evaluate(
                'table => table.scrollWidth <= table.parentElement.clientWidth'
            )
            playwright.expect(row.get_by_role('button', name='Include in report')).to_be_in_viewport()
            playwright.expect(row.get_by_role('button', name='Pathogenic for')).to_be_in_viewport()
            row.get_by_text('Details', exact=True).click()
            details = row.locator('details')
            assert report.variants[0]['occurrenceId'] in details.inner_text()
            assert 'Genomic location' in details.inner_text()
            assert 'DNA change' in details.inner_text()
            assert details.locator('[data-review-field="comment"]').is_visible()
            assert diagnostics == []
        finally:
            context.close()


@pytest.mark.parametrize('width', [320, 768, 1024, 1440])
def test_variant_review_headers_track_cells_at_all_target_widths(browser, width, tmp_path):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, _requests = _page(browser, html, width=width)
        try:
            page.goto(url)
            page.get_by_role('tab', name='Variant review').click()
            screenshot = tmp_path / f'variant-review-{width}.png'
            page.screenshot(path=str(screenshot), full_page=True)
            print(f'Variant review screenshot: {screenshot}')
            table = page.locator('#variant-table')
            geometry = table.evaluate('''table => ({
                headers: [...table.tHead.rows[0].cells].map(c => [c.offsetLeft, c.offsetWidth]),
                values: [...table.tBodies[0].rows[0].cells].map(c => [c.offsetLeft, c.offsetWidth]),
                overflow: table.scrollWidth > table.parentElement.clientWidth,
                pageOverflow: document.documentElement.scrollWidth > innerWidth,
            })''')
            assert geometry['headers'] == geometry['values']
            assert not geometry['pageOverflow']
            assert geometry['overflow'] == (width < 1024)
            assert table.locator('tbody tr').first.locator('td').nth(4).inner_text() != ''
            assert table.locator('tbody tr').first.locator('td').nth(5).inner_text() == 'Not received'
            assert table.locator('tbody tr').first.locator('td').nth(6).inner_text() == 'Not cross-checked'
            assert diagnostics == []
        finally:
            context.close()


@pytest.mark.parametrize('width', [320, 768, 1024, 1440])
def test_compact_workspace_responsive_layout(browser, width, tmp_path):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, _requests = _page(browser, html, width=width)
        try:
            page.goto(url)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert page.locator('#preview-report').is_visible()
            assert page.locator('body').evaluate('e => getComputedStyle(e).fontSize') == '14px'
            page.screenshot(path=str(tmp_path / f'compact-{width}.png'))
            print(f'Layout screenshot: {tmp_path / f"compact-{width}.png"}')
            if width == 1440:
                page.mouse.wheel(0, 600)
                playwright.expect(page.locator('.report-topbar')).to_be_in_viewport()
                playwright.expect(page.locator('.report-nav')).to_be_in_viewport()
                page.wait_for_function('scrollY > 100')
                header = page.locator('.report-topbar').bounding_box()
                nav = page.locator('.report-nav').bounding_box()
                assert abs(nav['y'] - (header['y'] + header['height'])) <= 1
            page.get_by_role('link', name='Preview report · 0 selected').click()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            cards = page.locator('.board-note-grid > *')
            assert cards.count() == 4
            first, second = cards.nth(0).bounding_box(), cards.nth(1).bounding_box()
            if width > 768:
                assert abs(first['y'] - second['y']) <= 1
                assert second['x'] > first['x']
            else:
                assert second['y'] >= first['y'] + first['height']
            page.screenshot(path=str(tmp_path / f'board-{width}.png'), full_page=True)
            print(f'Board screenshot: {tmp_path / f"board-{width}.png"}')
            assert diagnostics == []
        finally:
            context.close()


@pytest.mark.parametrize('snapshot', [False, True])
def test_preview_is_available_for_saved_and_read_only_selection(browser, snapshot):
    report = build_report()
    draft = draft_review(report)
    review = replace(draft, variant_reviews=(dict(draft.variant_reviews[0], reportingDecision='INCLUDE'),))
    html = render_html(report, review, inline_assets=True, snapshot=snapshot)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            page.get_by_role('link', name='Preview report · 1 selected').click()
            assert page.locator('#panel-tumour-board').is_visible()
            assert page.locator('#board-findings li').count() == 1
            assert page.locator('.board-note-grid > *').count() == 4
            assert page.locator('.board-note-grid > .board-signoff').count() == 1
            assert page.locator('#load-btn, #reset-btn').count() == 0
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()
