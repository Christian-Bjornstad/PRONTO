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
                assert page.get_by_role("heading", name="PRONTO-rapport").is_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
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
