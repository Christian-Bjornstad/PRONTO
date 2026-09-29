"""Real browser + isolated Django database; no mocked review/export APIs."""
import json
import shutil
from io import BytesIO
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model

from pronto.tests.reporting.browser.test_report import _page, _browser_executable, playwright, pypdf
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.migration import migrate_review_state_v1
from pronto_report.serialization import serialize_report_data, serialize_review_state
from pronto_web.reports.models import ReportRecord, ReportGrant, ReviewRevision, ReviewAudit, ReportHtmlExportAudit


@pytest.fixture
def configured_demo(settings, transactional_db):
    report = build_report()
    source = json.loads(serialize_report_data(report))
    # This workflow tests review persistence; attachment rendering has separate coverage.
    source['attachments'] = []
    record = ReportRecord.objects.create(report_id=report.report_id, report_data=source)
    ReviewRevision.objects.create(report=record, revision=1,
        review_data=json.loads(serialize_review_state(migrate_review_state_v1(draft_review(report)))))
    user = get_user_model().objects.create_user(username='workflow-demo-service')
    ReportGrant.objects.create(report=record, user=user)
    settings.PRONTO_DEMO_ENABLED = True
    settings.PRONTO_DEMO_REPORTS = [report.report_id]
    settings.PRONTO_DEMO_USER_ID = user.pk
    settings.PRONTO_REQUIRE_INITIALS = True
    settings.ALLOWED_HOSTS = ['127.0.0.1']
    settings.MIDDLEWARE = [*settings.MIDDLEWARE, 'pronto_web.reports.demo_access.DemoAccessMiddleware']
    return record, source


@pytest.fixture
def demo_server(configured_demo):
    from pytest_django.live_server_helper import LiveServer
    record, source = configured_demo
    # Construct the handler after demo middleware is configured, not at session start.
    server = LiveServer('127.0.0.1')
    try:
        yield f'{server.url}/reports/{record.pk}/', record, source
    finally:
        server.stop()


def test_demo_review_save_reload_same_person_finalize_and_download_html(demo_server):
    url, record, source = demo_server
    executable = _browser_executable()
    if executable is None:
        pytest.skip('Set PRONTO_BROWSER_EXECUTABLE to run browser quality checks')
    runtime = playwright.sync_playwright().start()
    browser = runtime.chromium.launch(executable_path=executable, headless=True)
    context, page, diagnostics, requests = _page(browser, '')
    try:
        page.goto(url)
        page.locator('[data-include-variant]').first.click()
        page.get_by_role('tab', name='Key findings').click()
        playwright.expect(page.locator('#kpi-inc')).to_have_text('1')
        playwright.expect(page.locator('#key-variant-table tr[data-variant-id]').first.locator(
            '[data-review-summary="decision"]')).to_have_text('Included')
        playwright.expect(page.locator('#kpi-exc')).to_contain_text('unsaved review')
        page.get_by_role('tab', name='Sequencing QC').click()
        page.get_by_label('QC comment', exact=True).fill('DEMO QC-notat – ikke klinisk vurdering')
        page.get_by_role('tab', name='Tumour board report').click()
        page.get_by_label('Interpretation summary', exact=True).fill('DEMO rapportnotat')
        page.get_by_role('button', name='Save', exact=True).click()
        page.get_by_label('Your initials', exact=True).fill('AB')
        page.get_by_role('button', name='Confirm', exact=True).click()
        playwright.expect(page.locator('#dirty-lbl')).to_have_text('All changes saved')
        playwright.expect(page.locator('#board-saved-revision')).to_have_text('Saved revision: 2')
        page.reload()
        playwright.expect(page.locator('#key-variant-table tr[data-variant-id]').first.locator(
            '[data-review-summary="decision"]')).to_have_text('Included')
        playwright.expect(page.locator('#board-findings')).to_contain_text('CHEK2')
        playwright.expect(page.get_by_label('Interpretation summary', exact=True)).to_have_value('DEMO rapportnotat')
        playwright.expect(page.get_by_label('QC comment', exact=True)).to_have_value('DEMO QC-notat – ikke klinisk vurdering')
        playwright.expect(page.locator('#board-saved-attribution')).to_contain_text('Last saved by: AB')
        page.once('dialog', lambda dialog: dialog.accept())
        page.get_by_role('button', name='Finalize', exact=True).click()
        page.get_by_label('Your initials', exact=True).fill('AB')
        page.get_by_role('button', name='Confirm', exact=True).click()
        playwright.expect(page.locator('.status-badge')).to_have_text('Report status: Final')
        playwright.expect(page.get_by_label('Interpretation summary', exact=True)).to_be_disabled()
        playwright.expect(page.locator('.board-signoff')).to_contain_text('Finalized by AB')
        page.get_by_role('button', name='Download report HTML').click()
        page.get_by_label('Your initials', exact=True).fill('CD')
        with page.expect_download() as download_info:
            page.get_by_role('button', name='Confirm', exact=True).click()
        downloaded = download_info.value
        assert downloaded.suggested_filename.endswith('.html')
        html = Path(downloaded.path()).read_text(encoding='utf-8')
        for text in ('Key findings', 'Selected variants', 'CHEK2', 'DEMO rapportnotat', 'Prepared by CD'):
            assert text in html
        assert 'TERT' not in html
        assert '<script' not in html
        playwright.expect(page.locator('#html-export-status')).to_contain_text('HTML download requested for revision 3')
        assert diagnostics == []
    finally:
        context.close()
        browser.close()
        runtime.stop()
    # Stop Playwright's event loop before synchronous Django ORM assertions.
    assert list(ReviewAudit.objects.filter(report=record).order_by('revision').values_list(
        'action', 'declared_initials')) == [('SAVE_DRAFT', 'AB'), ('FINALIZE', 'AB')]
    export_audit = ReportHtmlExportAudit.objects.get(report=record)
    assert (export_audit.revision, export_audit.declared_initials) == (3, 'CD')
    record.refresh_from_db()
    assert record.report_data == source


def test_demo_reset_then_export_new_saved_review_offline(demo_server, tmp_path):
    url, record, source = demo_server
    executable = _browser_executable()
    if executable is None:
        pytest.skip('Set PRONTO_BROWSER_EXECUTABLE to run browser quality checks')
    runtime = playwright.sync_playwright().start()
    browser = runtime.chromium.launch(executable_path=executable, headless=True)
    context, page, diagnostics, _requests = _page(browser, '')
    try:
        page.goto(url)
        page.locator('[data-include-variant]').first.click()
        page.get_by_role('tab', name='Sequencing QC').click()
        page.get_by_label('QC comment', exact=True).fill('Reset this QC note')
        page.get_by_role('tab', name='Tumour board report').click()
        page.get_by_label('Interpretation summary', exact=True).fill('Reset this conclusion')
        page.get_by_role('button', name='Save', exact=True).click()
        page.get_by_label('Your initials', exact=True).fill('AB')
        page.get_by_role('button', name='Confirm', exact=True).click()
        playwright.expect(page.locator('#board-saved-revision')).to_have_text('Saved revision: 2')

        page.once('dialog', lambda dialog: dialog.accept())
        page.get_by_role('button', name='Reset', exact=True).click()
        page.get_by_label('Your initials', exact=True).fill('AB')
        page.get_by_role('button', name='Confirm', exact=True).click()
        playwright.expect(page.locator('#board-saved-revision')).to_have_text('Saved revision: 3')
        playwright.expect(page.get_by_label('Interpretation summary', exact=True)).to_have_value('')
        playwright.expect(page.get_by_label('QC comment', exact=True)).to_have_value('')
        assert page.locator('[data-include-variant][aria-pressed="true"]').count() == 0

        page.get_by_role('tab', name='Variant review').click()
        page.locator('[data-include-variant]').first.click()
        page.get_by_role('tab', name='Key findings').click()
        page.locator('#edit-btn').click()
        page.locator('#tmb-edit-value').fill('17.8')
        page.locator('#tmb-edit-value').dispatch_event('change')
        page.locator('#tmb-correction-reason').fill('Demo correction')
        page.get_by_role('tab', name='Tumour board report').click()
        page.get_by_label('Interpretation summary', exact=True).fill('New saved conclusion')
        page.get_by_role('button', name='Save', exact=True).click()
        page.get_by_label('Your initials', exact=True).fill('CD')
        page.get_by_role('button', name='Confirm', exact=True).click()
        playwright.expect(page.locator('#board-saved-revision')).to_have_text('Saved revision: 4')
        page.get_by_role('button', name='Download report HTML').click()
        page.get_by_label('Your initials', exact=True).fill('EF')
        with page.expect_download() as download_info:
            page.get_by_role('button', name='Confirm', exact=True).click()
        downloaded = download_info.value
        html_path = tmp_path / downloaded.suggested_filename
        shutil.copyfile(downloaded.path(), html_path)
        html = html_path.read_text(encoding='utf-8')
        for value in ('CHEK2', 'New saved conclusion', '17,8 mut/Mb', 'Revision 4', 'Prepared by EF'):
            assert value in html
        assert 'Reset this conclusion' not in html
        assert '<script' not in html
        offline = context.new_page()
        offline_requests = []
        offline.on('request', lambda request: offline_requests.append(request.url))
        context.set_offline(True)
        offline.goto(html_path.as_uri())
        assert offline.get_by_role('heading', name='Key findings').is_visible()
        assert offline_requests == [html_path.as_uri()]
        printed = '\n'.join(sheet.extract_text() or '' for sheet in pypdf.PdfReader(BytesIO(offline.pdf())).pages)
        assert 'New saved conclusion' in printed
        assert diagnostics == []
    finally:
        context.close()
        browser.close()
        runtime.stop()
    assert list(ReviewRevision.objects.filter(report=record).order_by('revision').values_list('revision', flat=True)) == [1, 2, 3, 4]
    assert list(ReviewAudit.objects.filter(report=record).order_by('revision').values_list('action', 'declared_initials')) == [
        ('SAVE_DRAFT', 'AB'), ('RESET_DRAFT', 'AB'), ('SAVE_DRAFT', 'CD')]
    assert ReportHtmlExportAudit.objects.get(report=record).declared_initials == 'EF'
    record.refresh_from_db()
    assert record.report_data == source
