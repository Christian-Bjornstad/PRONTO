"""Real-browser quality checks for the standalone report."""

from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
from threading import Thread

import pytest

from pronto.tests.reporting.test_html_review_state import draft_review
from pronto.tests.reporting.test_html_surfaces import ONE_PIXEL_PNG
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html


playwright = pytest.importorskip("playwright.sync_api")
pypdf = pytest.importorskip("pypdf")


def _browser_executable() -> str | None:
    configured = os.environ.get("PRONTO_BROWSER_EXECUTABLE")
    if configured:
        return configured
    for name in ("chrome", "chromium", "chromium-browser", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    for path in (
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    ):
        if path.is_file():
            return str(path)
    return None


@contextmanager
def _serve(html: str):
    payload = html.encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture(scope="module")
def browser():
    executable = _browser_executable()
    if executable is None:
        pytest.skip("Set PRONTO_BROWSER_EXECUTABLE to run browser quality checks")
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        try:
            yield browser
        finally:
            browser.close()


def _page(browser, html: str, width: int = 1024):
    context = browser.new_context(viewport={"width": width, "height": 812})
    page = context.new_page()
    diagnostics = []
    requests = []
    page.on("console", lambda event: diagnostics.append(event.text) if event.type in ("error", "warning") else None)
    page.on("pageerror", lambda error: diagnostics.append(str(error)))
    page.on("request", lambda request: requests.append(request.url))
    return context, page, diagnostics, requests


def test_offline_export_is_responsive_and_makes_no_external_requests(browser):
    html = render_html(build_report(), inline_assets=True)
    with _serve(html) as url:
        for width in (375, 768, 1024, 1440):
            context, page, diagnostics, requests = _page(browser, html, width)
            try:
                page.goto(url)
                assert page.get_by_role("heading", name="InPreD · MTB Report").is_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
                assert requests == [url]
                assert diagnostics == []
            finally:
                context.close()


def test_saved_snapshot_is_read_only_but_navigation_and_search_still_work(browser):
    report = replace(build_report(), attachments=())
    html = render_html(report, draft_review(report), inline_assets=True, snapshot=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            assert page.locator(".report-topbar__saved").inner_text() == "Skrivebeskyttet eksport"
            assert page.locator("#save-btn, #edit-btn, #download-review, textarea, select").count() == 0
            page.get_by_role("tab", name="Variantgjennomgang").click()
            assert page.get_by_role("cell", name="Ekskluder").count() >= 1
            page.get_by_label("Søk i varianter").fill("CHEK2")
            assert page.locator("#variant-table tbody tr:not([hidden])").count() == 1
            page.get_by_role("tab", name="Molekylært tumorboard").click()
            assert page.locator(".board-note-readonly").count() == 3
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_tmb_gauge_edits_only_page_memory_and_blocks_stale_download(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            page.locator("#edit-btn").click()
            gauge = page.locator("#tmb-gauge")
            gauge.focus()
            gauge.press("ArrowRight")
            assert page.locator('[data-metric="tmb"] .metric-card__value').inner_text() == "15 mut/Mb"
            assert page.locator("#dirty-lbl").inner_text() == "Ulagrede kildekorreksjoner"
            assert page.locator("#tmb-correction-reason").is_enabled()
            assert page.locator("#download-review").is_disabled()
            assert page.locator("#tmb-correction-reason").get_attribute("required") is not None
            assert page.locator("#tmb-correction-status").is_visible()
            gauge.click(position={"x": 12, "y": 10})
            assert gauge.input_value() != "14.9"
            assert requests == [url]
            assert diagnostics == []
            page.reload()
            assert page.locator('[data-metric="tmb"] .metric-card__value').inner_text() == "14,9 mut/Mb"
        finally:
            context.close()


def test_empty_tmb_number_cannot_become_zero_correction(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            page.locator("#edit-btn").click()
            number = page.locator("#tmb-edit-value")
            number.fill("")
            number.blur()
            assert page.locator('[data-metric="tmb"] .metric-card__value').inner_text() == "14,9 mut/Mb"
            assert page.locator("#download-review").is_enabled()
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_patient_context_edit_keeps_source_visible_and_needs_reason(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            page.locator("#edit-btn").click()
            field = page.locator('[data-fact="tumourType"]')
            assert field.locator('[data-source-value="Ikke oppgitt"]').count() == 1
            field.locator('[data-correction-path="/sample/tumourType"]').fill("Lunge")
            field.locator('[data-correction-path="/sample/tumourType"]').blur()
            assert field.locator("dd").inner_text() == "Lunge"
            assert field.locator("#tumourType-correction-reason").is_enabled()
            assert field.get_attribute("data-availability") == "UNAVAILABLE"
            assert page.locator("#download-review").is_disabled()
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_msi_kpi_edit_is_local_and_does_not_change_source_label(browser):
    report = build_report()
    html = render_html(report, draft_review(report), inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            page.locator("#edit-btn").click()
            page.locator("#msi-edit-value").fill("5.2")
            page.locator("#msi-edit-value").blur()
            card = page.locator('[data-metric="msi"]')
            assert card.locator(".metric-card__value").inner_text() == "5,2 %"
            assert "4.13 (5/121)" in card.locator(".metric-card__detail").inner_text()
            assert page.locator("#msi-correction-reason").is_enabled()
            assert page.locator("#download-review").is_disabled()
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_keyboard_table_plots_focus_and_print(browser):
    report = build_report()
    cnv = next(asset for asset in report.attachments if "cnv" in asset["name"].lower())
    report = replace(report, attachments=(cnv,))
    html = render_html(
        report,
        draft_review(report),
        plot_images={cnv["assetId"]: (("image/png", ONE_PIXEL_PNG), ("image/png", ONE_PIXEL_PNG))},
        inline_assets=True,
    )
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html, 375)
        try:
            page.goto(url)
            tab = page.get_by_role("tab", name="Nøkkelfunn")
            tab.focus()
            assert tab.evaluate("element => getComputedStyle(element).outlineStyle !== 'none'")
            tab.press("ArrowRight")
            assert page.get_by_role("tab", name="Variantgjennomgang").get_attribute("aria-selected") == "true"
            page.locator("#variant-search").fill("TERT")
            assert page.locator("#variant-table tbody tr:visible").count() == 2
            page.get_by_role("tab", name="CNV-plott").click()
            page.get_by_role("button", name="Side 2").click()
            assert page.get_by_role("button", name="Side 2").get_attribute("aria-pressed") == "true"
            enlarge = page.locator("#cnv-2 [data-enlarge]")
            enlarge.click()
            assert page.get_by_role("dialog").is_visible()
            page.get_by_role("button", name="Lukk plott").click()
            assert enlarge.evaluate("element => document.activeElement === element")
            page.emulate_media(media="print")
            assert page.locator(".report-panel").evaluate_all(
                "panels => panels.every(panel => getComputedStyle(panel).display !== 'none')"
            )
            assert page.locator(".plot-figure").evaluate_all(
                "figures => figures.every(figure => getComputedStyle(figure).display !== 'none')"
            )
            pdf = page.pdf()
            assert pdf.startswith(b"%PDF")
            printed = "\n".join(page.extract_text() or "" for page in pypdf.PdfReader(BytesIO(pdf)).pages)
            for heading in ("Nøkkelfunn", "Variantgjennomgang", "CNV-plott", "Sekvenserings-QC", "Molekylært tumorboard"):
                assert heading in printed
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()


def test_csp_allows_review_download_without_external_network(browser):
    report = build_report()
    review = draft_review(report)
    html = render_html(report, review, inline_assets=True)
    with _serve(html) as url:
        context, page, diagnostics, requests = _page(browser, html)
        try:
            page.goto(url)
            page.get_by_role("tab", name="Variantgjennomgang").click()
            variant_id = review.variant_reviews[0]["variantId"]
            selector = page.locator(
                f'select[data-variant-id="{variant_id}"][data-review-field="reportingDecision"]'
            ).first
            selector.select_option("INCLUDE")
            with page.expect_download() as pending:
                page.get_by_role("button", name="Last ned ReviewState").click()
            download = pending.value
            saved = json.loads(Path(download.path()).read_text(encoding="utf-8"))
            assert saved["revision"] == 2
            assert saved["variantReviews"][0]["reportingDecision"] == "INCLUDE"
            assert requests == [url]
            assert diagnostics == []
        finally:
            context.close()
