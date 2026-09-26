"""Real browser + isolated Django database; no mocked save/finalize/print APIs."""
import json
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model

from pronto.tests.reporting.browser.test_report import _page, _browser_executable, playwright, pypdf
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.migration import migrate_review_state_v1
from pronto_report.serialization import serialize_report_data, serialize_review_state
from pronto_web.reports.models import ReportRecord, ReportGrant, ReviewRevision, ReviewAudit, ReportPrintAudit


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


def test_demo_review_save_reload_same_person_finalize_and_print(demo_server):
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
        page.get_by_role('tab', name='Sekvenserings-QC').click()
        page.get_by_label('QC-kommentar', exact=True).fill('DEMO QC-notat – ikke klinisk vurdering')
        page.get_by_role('tab', name='Molekylært tumorboard').click()
        page.get_by_label('Interpretation summary', exact=True).fill('DEMO rapportnotat')
        page.get_by_role('button', name='Lagre', exact=True).click()
        page.get_by_label('Dine initialer', exact=True).fill('AB')
        page.get_by_role('button', name='Bekreft', exact=True).click()
        playwright.expect(page.locator('#dirty-lbl')).to_have_text('Alle endringer lagret')
        playwright.expect(page.locator('#board-saved-revision')).to_have_text('Lagret revisjon: 2')
        page.reload()
        playwright.expect(page.locator('#board-findings')).to_contain_text('CHEK2')
        playwright.expect(page.get_by_label('Interpretation summary', exact=True)).to_have_value('DEMO rapportnotat')
        playwright.expect(page.get_by_label('QC-kommentar', exact=True)).to_have_value('DEMO QC-notat – ikke klinisk vurdering')
        playwright.expect(page.locator('#board-saved-attribution')).to_contain_text('AB (selvoppgitte initialer)')
        page.once('dialog', lambda dialog: dialog.accept())
        page.get_by_role('button', name='Ferdigstill', exact=True).click()
        page.get_by_label('Dine initialer', exact=True).fill('AB')
        page.get_by_role('button', name='Bekreft', exact=True).click()
        playwright.expect(page.locator('.status-badge')).to_have_text('Rapportstatus: Endelig')
        playwright.expect(page.get_by_label('Interpretation summary', exact=True)).to_be_disabled()
        playwright.expect(page.locator('.board-signoff')).to_contain_text('Ferdigstilt av AB')
        page.get_by_role('button', name='Generer MDT-utskrift').click()
        page.get_by_label('Dine initialer', exact=True).fill('CD')
        page.get_by_role('button', name='Bekreft', exact=True).click()
        playwright.expect(page.locator('#print-status')).to_contain_text('Utskrift forespurt av CD')
        page.emulate_media(media='print')
        printed = '\n'.join(sheet.extract_text() or '' for sheet in pypdf.PdfReader(BytesIO(page.pdf())).pages)
        for text in ('CHEK2', 'DEMO rapportnotat', 'Ferdigstilt av AB', 'Sist lagret av: AB'):
            assert text in printed
        assert 'TERT' not in printed
        assert diagnostics == []
    finally:
        context.close()
        browser.close()
        runtime.stop()
    # Stop Playwright's event loop before synchronous Django ORM assertions.
    assert list(ReviewAudit.objects.filter(report=record).order_by('revision').values_list(
        'action', 'declared_initials')) == [('SAVE_DRAFT', 'AB'), ('FINALIZE', 'AB')]
    printed_audit = ReportPrintAudit.objects.get(report=record)
    assert (printed_audit.revision, printed_audit.declared_initials) == (3, 'CD')
    record.refresh_from_db()
    assert record.report_data == source
