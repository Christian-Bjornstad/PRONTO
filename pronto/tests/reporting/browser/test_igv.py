"""Real browser tests of IGV UI state and local-file transfer boundary."""

from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
import shutil
from threading import Thread

import pytest

from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.renderers.html import render_html


playwright = pytest.importorskip("playwright.sync_api")
STATIC_ROOT = Path(__file__).parents[4] / "pronto_report" / "static"
FIXTURE_ROOT = Path(__file__).parent / "fixtures"
REFERENCE = (FIXTURE_ROOT / "synthetic-chr22.fa").read_bytes()
REFERENCE_INDEX = (FIXTURE_ROOT / "synthetic-chr22.fa.fai").read_bytes()


def browser_executable():
    configured = os.environ.get("PRONTO_BROWSER_EXECUTABLE")
    if configured:
        return configured
    for name in ("chrome", "chromium", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    for path in (Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
                 Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")):
        if path.is_file():
            return str(path)
    pytest.skip("Set PRONTO_BROWSER_EXECUTABLE to run IGV browser checks")


@contextmanager
def serve(html):
    payload = html.encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                body, content_type = payload, "text/html; charset=utf-8"
            elif self.path == "/static/report-igv.js":
                body, content_type = (STATIC_ROOT / "report-igv.js").read_bytes(), "text/javascript"
            elif self.path in {"/static/igv/igv.esm.min.js", "/static/igv/igv.esm.real.js"}:
                body, content_type = (STATIC_ROOT / "igv" / "igv.esm.min.js").read_bytes(), "text/javascript"
            elif self.path == "/reference.fa":
                body, content_type = REFERENCE, "application/octet-stream"
            elif self.path == "/reference.fa.fai":
                body, content_type = REFERENCE_INDEX, "text/plain"
            elif self.path.endswith("/alignments/tumour/data/"):
                if not self.headers.get("Range"):
                    self.send_error(416)
                    return
                body, content_type = (FIXTURE_ROOT / "synthetic-chr22.bam").read_bytes(), "application/octet-stream"
            elif self.path.endswith("/alignments/tumour/index/"):
                body, content_type = (FIXTURE_ROOT / "synthetic-chr22.bam.bai").read_bytes(), "application/octet-stream"
            else:
                self.send_error(404)
                return
            range_header = self.headers.get("Range")
            if range_header and range_header.startswith("bytes="):
                first, _, last = range_header[6:].partition("-")
                start = int(first)
                end = min(int(last) if last else len(body) - 1, len(body) - 1)
                original_size = len(body)
                body = body[start:end + 1]
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{original_size}")
            else:
                self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(body)

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


def capture_real_igv(page):
    """Expose only the synthetic test browser object, keeping production JS untouched."""
    wrapper = """import igv from './igv.esm.real.js';
      const original = igv.createBrowser;
      igv.createBrowser = async (...args) => {
        const browser = await original(...args);
        window.__testIgvBrowser = browser;
        return browser;
      };
      export default igv;"""
    page.route("**/static/igv/igv.esm.min.js",
               lambda route: route.fulfill(body=wrapper, content_type="text/javascript"))


def synthetic_read_names(page, track_name):
    return page.evaluate("""async name => {
      const track = window.__testIgvBrowser.findTracks('name', name)[0];
      const container = await track.featureSource.getAlignments('chr22', 50, 150);
      return container.allAlignments().map(read => read.readName);
    }""", track_name)


def test_explicit_local_save_requires_confirmation_and_uploads_whole_pair():
    report = build_report()
    html = render_html(report, inline_assets=True, snapshot=True, web_igv=True,
                       igv_save_enabled=True,
                       igv_references={"GRCh37": {"fastaURL": "/reference.fa", "indexURL": "/reference.fa.fai"}})
    module = b"""export default {
      async createBrowser() { return { search: async () => true }; },
      removeBrowser() {}
    };"""
    with serve(html) as url, playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=browser_executable(), headless=True)
        try:
            page = browser.new_page()
            requests = []
            diagnostics = []
            page.on("request", lambda request: requests.append((request.method, request.url)))
            page.on("pageerror", lambda error: diagnostics.append(str(error)))
            page.route("**/static/igv/igv.esm.min.js", lambda route: route.fulfill(
                body=module, content_type="text/javascript"))
            page.route("**/alignments/save-sessions/**", lambda route: route.fulfill(
                status=201 if route.request.url.endswith("save-sessions/") else
                204 if route.request.method == "PUT" else 201,
                content_type="application/json",
                body='{"sessionId":"11111111-1111-4111-8111-111111111111"}'
                if route.request.url.endswith("save-sessions/") else
                '{"savedId":"22222222-2222-4222-8222-222222222222","sourceId":"saved-22222222222242228222222222222222"}'
                if route.request.url.endswith("complete/") else ""))
            page.goto(url)
            page.context.add_cookies([{"name": "csrftoken", "value": "synthetic-token", "url": url}])
            page.get_by_role("tab", name="Variantgjennomgang").click()
            page.get_by_role("button", name="Vis i IGV").first.click()
            page.locator("#igv-data").set_input_files({"name": "synthetic.bam", "mimeType": "application/octet-stream", "buffer": b"BAM"})
            page.locator("#igv-index").set_input_files({"name": "synthetic.bam.bai", "mimeType": "application/octet-stream", "buffer": b"INDEX"})
            page.get_by_role("button", name="Åpne lokale filer").click()
            page.get_by_text("Ikke lagret · filene brukes bare i denne nettleserfanen.").wait_for(state="visible")
            assert not any(method in {"POST", "PUT"} for method, _ in requests)
            assert page.locator("#save-btn").count() == 0  # read snapshot has no review-save action
            assert not any("save-sessions" in url for _, url in requests)
            page.get_by_role("button", name="Lagre filer for senere bruk").click()
            assert page.get_by_text("Hele BAM/CRAM-filen og indeksen").is_visible()
            page.get_by_role("button", name="Avbryt", exact=True).click()
            assert not any("save-sessions" in url for _, url in requests)
            page.get_by_role("button", name="Lagre filer for senere bruk").click()
            page.get_by_role("button", name="Bekreft lagring").click()
            page.get_by_text("Lagret for senere bruk", exact=True).wait_for(state="visible")
            methods = [method for method, path in requests if "save-sessions" in path]
            assert methods == ["POST", "PUT", "PUT", "POST"]
            assert all(path.startswith(url.rstrip("/")) for _, path in requests)
            assert diagnostics == []
        finally:
            browser.close()


def test_failed_upload_and_reload_never_claim_saved_state():
    report = build_report()
    html = render_html(report, inline_assets=True, snapshot=True, web_igv=True,
                       igv_save_enabled=True,
                       igv_references={"GRCh37": {"fastaURL": "/reference.fa", "indexURL": "/reference.fa.fai"}})
    with serve(html) as url, playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=browser_executable(), headless=True)
        try:
            page = browser.new_page()
            page.route("**/static/igv/igv.esm.min.js", lambda route: route.fulfill(
                body=b"export default { async createBrowser() { return { search: async () => true }; }, removeBrowser() {} };",
                content_type="text/javascript"))
            page.route("**/alignments/save-sessions/**", lambda route: route.fulfill(
                status=201 if route.request.method == "POST" else 507,
                content_type="application/json",
                body='{"sessionId":"11111111-1111-4111-8111-111111111111"}'
                if route.request.method == "POST" else '{"error":"storage_unavailable"}'))
            page.goto(url)
            page.context.add_cookies([{"name": "csrftoken", "value": "synthetic-token", "url": url}])
            page.get_by_role("tab", name="Variantgjennomgang").click()
            page.get_by_role("button", name="Vis i IGV").first.click()
            page.locator("#igv-data").set_input_files({"name": "synthetic.bam", "mimeType": "application/octet-stream", "buffer": b"BAM"})
            page.locator("#igv-index").set_input_files({"name": "synthetic.bam.bai", "mimeType": "application/octet-stream", "buffer": b"INDEX"})
            page.get_by_role("button", name="Åpne lokale filer").click()
            page.get_by_text("Ikke lagret · filene brukes bare i denne nettleserfanen.").wait_for(state="visible")
            page.get_by_role("button", name="Lagre filer for senere bruk").click()
            page.get_by_role("button", name="Bekreft lagring").click()
            page.locator("#igv-save-error").wait_for(state="visible")
            assert not page.get_by_text("Lagret for senere bruk", exact=True).is_visible()
            page.reload()
            assert not page.get_by_text("Lagret for senere bruk", exact=True).is_visible()
        finally:
            browser.close()


def test_finalization_uncertainty_and_source_switch_are_not_mislabeled():
    report = build_report()
    html = render_html(report, inline_assets=True, snapshot=True, web_igv=True,
                       igv_save_enabled=True,
                       igv_references={"GRCh37": {"fastaURL": "/reference.fa", "indexURL": "/reference.fa.fai"}})
    with serve(html) as url, playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=browser_executable(), headless=True)
        try:
            page = browser.new_page()
            page.route("**/static/igv/igv.esm.min.js", lambda route: route.fulfill(
                body=b"export default { async createBrowser() { return { search: async () => true }; }, removeBrowser() {} };",
                content_type="text/javascript"))
            page.goto(url)
            page.context.add_cookies([{"name": "csrftoken", "value": "synthetic-token", "url": url}])
            page.evaluate("""() => {
              const original = window.fetch;
              window.fetch = (input, options = {}) => {
                const path = String(input);
                if (path.endsWith('/save-sessions/') && options.method === 'POST')
                  return Promise.resolve(new Response(JSON.stringify({sessionId: '11111111-1111-4111-8111-111111111111'}), {status: 201}));
                if (options.method === 'PUT') return Promise.resolve(new Response(null, {status: 204}));
                if (path.endsWith('/complete/')) return new Promise((_resolve, reject) => {
                  window.__failSave = () => reject(new DOMException('lost response', 'AbortError'));
                });
                return original(input, options);
              };
            }""")
            page.get_by_role("tab", name="Variantgjennomgang").click()
            page.get_by_role("button", name="Vis i IGV").first.click()
            page.locator("#igv-data").set_input_files({"name": "synthetic.bam", "mimeType": "application/octet-stream", "buffer": b"BAM"})
            page.locator("#igv-index").set_input_files({"name": "synthetic.bam.bai", "mimeType": "application/octet-stream", "buffer": b"INDEX"})
            page.get_by_role("button", name="Åpne lokale filer").click()
            page.get_by_text("Ikke lagret · filene brukes bare i denne nettleserfanen.").wait_for(state="visible")
            page.get_by_role("button", name="Lagre filer for senere bruk").click()
            page.get_by_role("button", name="Bekreft lagring").click()
            page.wait_for_function("typeof window.__failSave === 'function'")
            page.locator("#igv-close").click()
            assert page.locator("#igv-panel").is_visible()
            page.get_by_role("button", name="Åpne lokale filer").click()
            page.evaluate("window.__failSave()")
            page.get_by_text("Lagringsstatus er usikker", exact=False).wait_for(state="visible")
            assert not page.get_by_text("Lagret for senere bruk", exact=True).is_visible()
        finally:
            browser.close()


def test_local_pair_is_browser_only_and_disappears_on_reload():
    report = build_report()
    html = render_html(report, inline_assets=True, snapshot=True, web_igv=True,
                       igv_references={"GRCh37": {"fastaURL": "/reference.fa", "indexURL": "/reference.fa.fai"}})
    module = b"""export default {
      async createBrowser(node, config) {
        node.dataset.localFiles = String(config.tracks[0].url instanceof File && config.tracks[0].indexURL instanceof File);
        node.dataset.locus = config.locus;
        node.dataset.noDefaultGenomes = String(config.loadDefaultGenomes === false && config.queryParametersSupported === false);
        return { search: async () => true };
      },
      removeBrowser() {}
    };"""
    with serve(html) as url, playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=browser_executable(), headless=True)
        try:
            page = browser.new_page()
            requests = []
            page.on("request", lambda request: requests.append((request.method, request.url)))
            page.route("**/static/igv/igv.esm.min.js", lambda route: route.fulfill(body=module, content_type="text/javascript"))
            page.goto(url)
            page.get_by_role("tab", name="Variantgjennomgang").click()
            page.get_by_role("button", name="Vis i IGV").first.click()
            page.locator('input[name="igv-data"]').set_input_files({"name": "synthetic.bam", "mimeType": "application/octet-stream", "buffer": b"BAM"})
            page.locator('input[name="igv-index"]').set_input_files({"name": "synthetic.bam.bai", "mimeType": "application/octet-stream", "buffer": b"INDEX"})
            page.get_by_role("button", name="Åpne lokale filer").click()
            page.get_by_text("Ikke lagret · filene brukes bare i denne nettleserfanen.").wait_for(state="visible")
            assert page.locator("#igv-viewer").get_attribute("data-local-files") == "true"
            assert page.locator("#igv-viewer").get_attribute("data-no-default-genomes") == "true"
            assert page.locator("#igv-viewer").get_attribute("data-locus").startswith("chr")
            assert not any(method in {"POST", "PUT"} for method, _ in requests)
            page.reload()
            assert not page.get_by_text("Ikke lagret · filene brukes bare i denne nettleserfanen.").is_visible()
            assert page.locator('input[name="igv-data"]').input_value() == ""
        finally:
            browser.close()


def test_multiple_registered_sources_require_explicit_choice():
    report = build_report()
    sources = tuple({
        "sourceId": identifier, "role": role, "format": "bam", "referenceBuild": "GRCh37",
        "dataURL": f"/reports/{report.report_id}/alignments/{identifier}/data/",
        "indexURL": f"/reports/{report.report_id}/alignments/{identifier}/index/",
    } for identifier, role in (("tumour", "TUMOUR_DNA"), ("normal", "NORMAL_DNA")))
    html = render_html(report, inline_assets=True, snapshot=True, web_igv=True, igv_sources=sources)
    with serve(html) as url, playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=browser_executable(), headless=True)
        try:
            page = browser.new_page()
            page.goto(url)
            page.get_by_role("tab", name="Variantgjennomgang").click()
            page.get_by_role("button", name="Vis i IGV").first.click()
            assert page.locator("#igv-source option").count() == 3
            assert page.locator("#igv-source").input_value() == ""
            page.get_by_role("button", name="Åpne registrert kilde").click()
            assert "Velg en registrert kilde først" in page.locator("#igv-status").inner_text()
        finally:
            browser.close()


def test_variant_change_during_igv_creation_uses_latest_locus():
    report = build_report()
    html = render_html(report, inline_assets=True, snapshot=True, web_igv=True,
                       igv_references={"GRCh37": {"fastaURL": "/reference.fa", "indexURL": "/reference.fa.fai"}})
    module = b"""export default {
      async createBrowser(node, config) {
        await new Promise(resolve => setTimeout(resolve, 300));
        node.dataset.locus = config.locus;
        return { search: async locus => { node.dataset.locus = locus; } };
      },
      removeBrowser() {}
    };"""
    with serve(html) as url, playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=browser_executable(), headless=True)
        try:
            page = browser.new_page()
            page.route("**/static/igv/igv.esm.min.js", lambda route: route.fulfill(body=module, content_type="text/javascript"))
            page.goto(url)
            page.get_by_role("tab", name="Variantgjennomgang").click()
            buttons = page.get_by_role("button", name="Vis i IGV")
            assert buttons.count() >= 2
            latest_locus = buttons.nth(1).get_attribute("data-igv-locus")
            buttons.first.click()
            page.locator('input[name="igv-data"]').set_input_files({"name": "synthetic.bam", "mimeType": "application/octet-stream", "buffer": b"BAM"})
            page.locator('input[name="igv-index"]').set_input_files({"name": "synthetic.bam.bai", "mimeType": "application/octet-stream", "buffer": b"INDEX"})
            page.get_by_role("button", name="Åpne lokale filer").click()
            buttons.nth(1).click()
            page.get_by_text("Ikke lagret · filene brukes bare i denne nettleserfanen.").wait_for(state="visible")
            assert page.locator("#igv-viewer").get_attribute("data-locus") == latest_locus
        finally:
            browser.close()


def test_vendored_igv_module_loads_same_origin_reference_without_remote_requests():
    report = build_report()
    html = render_html(report, inline_assets=True, snapshot=True, web_igv=True,
                       igv_references={"GRCh37": {"fastaURL": "/reference.fa", "indexURL": "/reference.fa.fai"}})
    with serve(html) as url, playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=browser_executable(), headless=True)
        try:
            page = browser.new_page()
            requests = []
            diagnostics = []
            page.on("request", lambda request: requests.append(request.url))
            page.on("pageerror", lambda error: diagnostics.append(str(error)))
            page.on("console", lambda event: diagnostics.append(event.text) if event.type in ("error", "warning") else None)
            page.goto(url)
            result = page.evaluate("""async () => {
              const igv = (await import('/static/igv/igv.esm.min.js')).default;
              const host = document.createElement('div');
              document.body.append(host);
              const browser = await igv.createBrowser(host, {
                reference: { id: 'GRCh37', fastaURL: '/reference.fa', indexURL: '/reference.fa.fai' },
                locus: 'chr22:1-20', tracks: [], loadDefaultGenomes: false,
                queryParametersSupported: false, showSVGButton: false,
              });
              const found = browser.currentLoci();
              igv.removeBrowser(browser);
              host.remove();
              return found;
            }""")
            assert "chr22" in str(result)
            assert diagnostics == []
            assert all(request.startswith(url.rstrip("/")) for request in requests)
        finally:
            browser.close()


def test_real_igv_opens_indexed_synthetic_bam_at_variant_locus():
    report = build_report()
    first = {**report.variants[0], "chromosome": "22", "position": 100,
             "genomicLocation": "22:100", "referenceBuild": "GRCh37"}
    report = replace(report, variants=(first, *report.variants[1:]))
    html = render_html(report, inline_assets=True, snapshot=True, web_igv=True,
                       igv_references={"GRCh37": {"fastaURL": "/reference.fa", "indexURL": "/reference.fa.fai"}})
    with serve(html) as url, playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=browser_executable(), headless=True)
        try:
            page = browser.new_page()
            capture_real_igv(page)
            requests = []
            diagnostics = []
            page.on("request", lambda request: requests.append((request.method, request.url)))
            page.on("pageerror", lambda error: diagnostics.append(str(error)))
            page.on("console", lambda event: diagnostics.append(event.text) if event.type in ("error", "warning") else None)
            page.goto(url)
            page.get_by_role("tab", name="Variantgjennomgang").click()
            page.get_by_role("button", name="Vis i IGV").first.click()
            page.locator('input[name="igv-data"]').set_input_files(str(FIXTURE_ROOT / "synthetic-chr22.bam"))
            page.locator('input[name="igv-index"]').set_input_files(str(FIXTURE_ROOT / "synthetic-chr22.bam.bai"))
            page.get_by_role("button", name="Åpne lokale filer").click()
            page.get_by_text("Ikke lagret · filene brukes bare i denne nettleserfanen.").wait_for(state="visible", timeout=20000)
            values = page.locator("#igv-viewer").evaluate("element => [...element.shadowRoot.querySelectorAll('input')].map(input => input.value)")
            assert any("chr22" in value for value in values), values
            assert "Lokal fil" in page.locator("#igv-viewer").evaluate("element => element.shadowRoot.textContent")
            assert "synthetic-read" in synthetic_read_names(page, "Lokal fil")
            assert not any(method in {"POST", "PUT"} for method, _ in requests)
            assert all(request_url.startswith(url.rstrip("/")) for _, request_url in requests)
            assert diagnostics == []
        finally:
            browser.close()


def test_registered_source_opens_through_same_origin_ranges():
    report = build_report()
    first = {**report.variants[0], "chromosome": "22", "position": 100,
             "genomicLocation": "22:100", "referenceBuild": "GRCh37"}
    report = replace(report, variants=(first, *report.variants[1:]))
    source = {
        "sourceId": "tumour", "role": "TUMOUR_DNA", "format": "bam", "referenceBuild": "GRCh37",
        "dataURL": f"/reports/{report.report_id}/alignments/tumour/data/",
        "indexURL": f"/reports/{report.report_id}/alignments/tumour/index/",
    }
    html = render_html(report, inline_assets=True, snapshot=True, web_igv=True,
                       igv_sources=(source,),
                       igv_references={"GRCh37": {"fastaURL": "/reference.fa", "indexURL": "/reference.fa.fai"}})
    with serve(html) as url, playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=browser_executable(), headless=True)
        try:
            page = browser.new_page()
            capture_real_igv(page)
            requests = []
            diagnostics = []
            page.on("request", lambda request: requests.append((request.method, request.url, request.headers)))
            page.on("pageerror", lambda error: diagnostics.append(str(error)))
            page.on("console", lambda event: diagnostics.append(event.text) if event.type in ("error", "warning") else None)
            page.goto(url)
            page.get_by_role("tab", name="Variantgjennomgang").click()
            page.get_by_role("button", name="Vis i IGV").first.click()
            page.locator("#igv-source").select_option("tumour")
            page.get_by_role("button", name="Åpne registrert kilde").click()
            page.get_by_text("Registrert kilde åpnet: TUMOUR_DNA.").wait_for(state="visible", timeout=20000)
            alignment_requests = [(method, request_url, headers) for method, request_url, headers in requests
                                  if "/alignments/tumour/" in request_url]
            assert any(request_url.endswith("/data/") and "range" in headers for _, request_url, headers in alignment_requests)
            assert any(request_url.endswith("/index/") for _, request_url, _ in alignment_requests)
            assert all(method == "GET" for method, _, _ in alignment_requests)
            assert "synthetic-read" in synthetic_read_names(page, "TUMOUR_DNA")
            assert diagnostics == []
        finally:
            browser.close()
