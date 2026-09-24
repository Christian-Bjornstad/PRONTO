# IGV Viewing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open an embedded IGV view at a report variant using an authorized registered alignment pair or a browser-selected local pair, without uploading local bytes.

**Architecture:** Add a web-only IGV surface to the existing report renderer, a strict manifest-backed source registry, and an authenticated byte-range endpoint. Browser code loads igv.js locally and passes selected `File` objects directly to it; the existing offline export remains self-contained and contains no IGV data URLs.

**Tech Stack:** Python 3, Django 5.2, igv.js 3.7.0 (locally vendored ESM), pytest/Django TestCase, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-24-igv-alignment-sources-design.md`. Read it and `docs/superpowers/specs/2026-09-23-report-html-fidelity-and-review-persistence-design.md` before Task 1.

## Global Constraints

- File selection alone makes no upload request; ordinary report **Lagre** never saves alignment bytes.
- Resolve exact report/sample/build identity; do not infer identity from filename or permit a browser-provided filesystem path/URL.
- Keep data/reference requests same-origin, authenticated, and range-capable. Do not enable IGV query-parameter file loading or runtime CDN/default-genome discovery.
- Do not embed BAM/CRAM, indices, paths, or credentials in `ReportData`, `ReviewState`, `ReportAsset.content`, Git, or offline HTML.
- Preserve the local `C:/Users/molpa/Documents/Inpred/report.html` as the visual reference; do not navigate that file in a browser.

## Review Focus

1. A variant whose build is `UNKNOWN` or differs from the sample build must show why IGV is unavailable (Task 1 test).
2. Two registry entries for the same sample/build must be offered as choices, not silently resolved by list order (Task 2 test).
3. A path escaping the configured root through `..` or a symlink must be refused (Task 2 test).
4. A guessed ID or malformed/multi-range request must not disclose bytes or bypass report grants (Task 3 test).
5. Reloading a page after local selection must lose that local pair and never show it as saved (Task 4 browser test).

## File map

- `pronto_report/igv/locus.py`: validated build/coordinate-to-IGV-locus conversion; no Django dependency.
- `pronto_report/renderers/html.py`, `pronto_report/templates/report/variant-review.html`, `pronto_report/templates/report/base.html`: web-only launcher/panel, leaving offline output unchanged.
- `pronto_web/reports/alignment_registry.py`: exact-key manifest lookup and allowlisted path resolution.
- `pronto_web/reports/alignment_ranges.py`, `pronto_web/reports/views.py`, `pronto_web/urls.py`: authorized byte-range delivery.
- `pronto_report/static/igv/igv.esm.min.js`, `pronto_report/static/igv/LICENSE`, `pronto_report/static/igv/PROVENANCE.md`: reviewed pinned dependency; no runtime CDN.
- `pronto_report/static/report-igv.js`, `pronto_report/static/report.css`, `pronto_web/settings.py`: local file picker, source choice, same-origin static/reference configuration, IGV state and errors.
- `pronto/tests/reporting/test_igv_locus.py`, `pronto/tests/reporting/test_html_renderer.py`, `pronto_web/reports/tests.py`, `pronto/tests/reporting/browser/test_igv.py`: contract, authorization, and browser verification.

---

### Task 1: Web-only IGV locus and launcher

**Files:** Create `pronto_report/igv/__init__.py`, `pronto_report/igv/locus.py`, `pronto/tests/reporting/test_igv_locus.py`. Modify `pronto_report/renderers/html.py`, `pronto_report/templates/report/variant-review.html`, `pronto_report/templates/report/base.html`, `pronto_web/reports/views.py`, `pronto/tests/reporting/test_html_renderer.py`.

**Interfaces:** Produce `locus_for_variant(variant: Mapping[str, object], sample_build: str) -> str | None`. Add `web_igv: bool = False` to `render_html`; `web_igv=True` is allowed only for a Django response, not offline export. Each launch button exposes escaped `data-variant-id` and `data-igv-locus`, never paths.

- [ ] **Step 1: Write failing contract and renderer tests.**

```python
assert locus_for_variant({"referenceBuild": "GRCh37", "chromosome": "17", "position": 7577120}, "GRCh37") == "chr17:7577070-7577170"
assert locus_for_variant({"referenceBuild": "UNKNOWN", "chromosome": "17", "position": 7577120}, "UNKNOWN") is None
assert locus_for_variant({"referenceBuild": "GRCh38", "chromosome": "17", "position": 7577120}, "GRCh37") is None
assert 'id="igv-panel"' not in render_html(report, review, inline_assets=True, snapshot=True)
assert 'id="igv-panel"' in render_html(report, review, inline_assets=True, snapshot=True, web_igv=True)
```

- [ ] **Step 2: Run red tests.** Run `python -m pytest pronto/tests/reporting/test_igv_locus.py pronto/tests/reporting/test_html_renderer.py -q`; expect missing function/argument assertions to fail.
- [ ] **Step 3: Implement the converter and web-only projection.** Accept only `GRCh37`/`GRCh38`, canonical autosomes/X/Y/MT, positive integer positions and a 50 bp flank (start clamped to 1). Use validated `chromosome`/`position` or parse `genomicLocation` `chromosome:position`; no gene-name web search. Add launcher and panel only when `web_igv=True`; update the authenticated Django view to pass it. Keep the existing snapshot/read-only review behavior distinct from IGV availability.

```python
def locus_for_variant(variant: Mapping[str, object], sample_build: str) -> str | None:
    if sample_build not in {"GRCh37", "GRCh38"} or variant.get("referenceBuild") != sample_build:
        return None
    match = re.fullmatch(r"(?:chr)?(\d{1,2}|X|Y|M|MT):(\d+)", str(variant.get("genomicLocation", "")))
    chromosome = variant.get("chromosome") or (match.group(1) if match else None)
    position = variant.get("position") or (int(match.group(2)) if match else None)
    if str(chromosome) not in {*(str(i) for i in range(1, 23)), "X", "Y", "M", "MT"} or type(position) is not int or position < 1:
        return None
    return f"chr{chromosome}:{max(1, position - 50)}-{position + 50}"
```

- [ ] **Step 4: Run green tests and commit.** Run the two test files above and `python manage.py test pronto_web.reports` with `PRONTO_DJANGO_SECRET_KEY` set to a check-only value. Commit only Task 1 files as `feat: expose web-only IGV locus controls`.

### Task 2: Exact-key registered source lookup

**Files:** Create `pronto_web/reports/alignment_registry.py`, `pronto_web/reports/test_alignment_registry.py`; modify `pronto_web/settings.py` for optional `PRONTO_ALIGNMENT_SOURCE_ROOT` and `PRONTO_ALIGNMENT_REGISTRY_JSON` settings. Document manifest shape in `docs/igv-alignment-operations.md`.

**Interfaces:** Produce `RegisteredPair(source_id, report_id, sample_id, reference_build, role, format, data_path, index_path)` and `lookup_registered(report_id: str, sample_id: str, reference_build: str) -> Sequence[RegisteredPair]`. `resolve_registered_component(report_id: str, source_id: str, component: Literal["data", "index"]) -> Path` rejects missing/escaping/symlinked files. Manifest version 1 is `{"version":1,"sources":[{"id":"tumour-dna","reportId":"r1","sampleId":"s1","referenceBuild":"GRCh37","role":"TUMOUR_DNA","format":"bam","data":"s1/tumour.bam","index":"s1/tumour.bam.bai"}]}`.

- [ ] **Step 1: Write failing registry tests.**

```python
assert lookup_registered("r1", "s1", "GRCh37") == (expected_tumour, expected_normal)
assert lookup_registered("r1", "s2", "GRCh37") == ()
with pytest.raises(InvalidAlignmentRegistry):
    resolve_registry_path(root, "../outside.bam")
with pytest.raises(InvalidAlignmentRegistry):
    resolve_registry_path(root, "s1/link-to-outside.bam")
```

- [ ] **Step 2: Run red test.** Run `python -m pytest pronto_web/reports/test_alignment_registry.py -q`; expect import failure.
- [ ] **Step 3: Implement strict manifest validation.** Validate version/required fields, unique IDs, role and format allowlists, same exact report/sample/build keys, both file paths, and root containment after `Path.resolve(strict=True)`. Return all matches in stable role/id order. Fail closed on malformed configuration; empty/unset configuration means no sources, not a scan. Never serialize physical paths into HTML or JSON responses.

```python
def resolve_registry_path(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute():
        raise InvalidAlignmentRegistry("absolute path")
    base = root.resolve(strict=True)
    target = (base / relative).resolve(strict=True)
    if base not in target.parents or not target.is_file():
        raise InvalidAlignmentRegistry("outside source root")
    return target
```

- [ ] **Step 4: Run green test and commit.** Run registry tests plus `python manage.py check`; commit as `feat: resolve registered alignment pairs by exact sample identity`.

### Task 3: Authorized alignment and index byte ranges

**Files:** Create `pronto_web/reports/alignment_ranges.py`, `pronto_web/reports/test_alignment_ranges.py`; modify `pronto_web/reports/views.py`, `pronto_web/urls.py`, `pronto_web/reports/tests.py`.

**Interfaces:** Produce `parse_single_range(header: str, size: int) -> tuple[int, int]` with inclusive offsets and `RangeNotSatisfiable`. GET route `/reports/<report_id>/alignments/<source_id>/<component>/` accepts only `component` `data|index`; it resolves by report-scoped ID, checks active user and `ReportGrant`, then streams from an already-opened authorized descriptor. Plan 2 adds managed sources to this resolver without changing the route.

- [ ] **Step 1: Write failing parser and endpoint tests.**

```python
assert parse_single_range("bytes=2-5", 10) == (2, 5)
assert parse_single_range("bytes=8-", 10) == (8, 9)
with pytest.raises(RangeNotSatisfiable):
    parse_single_range("bytes=0-1,4-5", 10)
response = authorized_client.get(url, HTTP_RANGE="bytes=2-5")
assert response.status_code == 206
assert response["Content-Range"] == "bytes 2-5/10"
assert b"".join(response.streaming_content) == fixture_bytes[2:6]
assert ungranted_client.get(url, HTTP_RANGE="bytes=0-1").status_code == 404
```

- [ ] **Step 2: Run red tests.** Run `python -m pytest pronto_web/reports/test_alignment_ranges.py -q` and `python manage.py test pronto_web.reports`; expect missing parser/route.
- [ ] **Step 3: Implement one-range streaming.** Reject malformed and multi-range headers with `416` plus `Content-Range: bytes */<size>`. Require a range for large alignment data; permit a full small index response. Set `Accept-Ranges: bytes`, exact `Content-Length`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, and `application/octet-stream`. Reauthorize every request before opening a file; never redirect to a public media path.

```python
def iter_range(file_handle: BinaryIO, start: int, end: int, chunk_size: int = 1024 * 1024):
    file_handle.seek(start)
    remaining = end - start + 1
    while remaining:
        block = file_handle.read(min(chunk_size, remaining))
        if not block:
            raise OSError("alignment changed during transfer")
        remaining -= len(block)
        yield block
```

- [ ] **Step 4: Run green tests and commit.** Test anonymous, ungranted, wrong report, unknown source/component, valid first/middle/end range, invalid range, HEAD behavior and changed file. Run `python manage.py test pronto_web.reports`; commit as `feat: serve authorized alignment byte ranges`.

### Task 4: Local IGV browser and source selection

**Files:** Create `pronto_report/static/report-igv.js`, `pronto_report/static/igv/igv.esm.min.js`, `pronto_report/static/igv/LICENSE`, `pronto_report/static/igv/PROVENANCE.md`, `pronto/tests/reporting/browser/test_igv.py`; modify `pronto_report/templates/report/base.html`, `pronto_report/templates/report/variant-review.html`, `pronto_report/static/report.css`, `pronto_web/settings.py`, `pronto_web/reports/views.py`, `pronto/tests/reporting/test_html_export.py`, `docs/igv-alignment-operations.md`.

**Interfaces:** The Django view calls `lookup_registered`, then passes only `{sourceId, role, format, referenceBuild, dataURL, indexURL}` descriptors through a new `igv_sources` renderer argument; no physical paths. `report-igv.js` reads escaped locus/build and these same-origin descriptors. Its `openLocalPair(dataFile: File, indexFile: File, locus: string, build: string)` passes `File` objects to `igv.createBrowser`/`loadTrack`. The page loads only the locally vendored, reviewed igv.js 3.7.0 package and approved same-origin references.

- [ ] **Step 1: Write failing browser tests.** A synthetic indexed BAM and index fixture selected through Playwright file inputs opens at the TP53 locus, shows **Ikke lagret**, performs no POST/PUT, and disappears after reload. A two-source registry requires a choice. The offline export contains neither `igv.esm.min.js` nor private URLs. Assert IGV errors appear in `role=status` without changing `igvAssessment`.

```python
page.locator('input[name="igv-data"]').set_input_files(str(bam_path))
page.locator('input[name="igv-index"]').set_input_files(str(bai_path))
page.get_by_role("button", name="Vis i IGV").first.click()
assert page.get_by_text("Ikke lagret").is_visible()
assert not any(request.method in {"POST", "PUT"} for request in alignment_requests)
page.reload()
assert not page.get_by_text("Ikke lagret").is_visible()
```

- [ ] **Step 2: Run red browser/render tests.** Run `python -m pytest pronto/tests/reporting/browser/test_igv.py pronto/tests/reporting/test_html_export.py -q`; expect missing controls.
- [ ] **Step 3: Implement browser integration.** Obtain `igv@3.7.0` without install scripts, review its package/license and checksum, vendor only the ESM distribution and license, and record SHA-256/source in `PROVENANCE.md`. Configure `django.contrib.staticfiles`, `STATICFILES_DIRS`, `STATIC_URL`, and a production `collectstatic` destination for the vendored script; use explicit same-origin URLs, not Django development static serving in production. Initialize lazily, set `loadDefaultGenomes:false` and `queryParametersSupported:false`, provide exact local reference URLs, and use same-origin range URLs for registered sources. Require user-selected data/index `File` objects for local mode; never POST them here. Give the panel keyboard focus/close behavior and visible loading/error/unsaved labels. Keep the CSP as narrow as a real-browser test permits; never add wildcard data hosts.

```javascript
const config = {
  reference: referenceForBuild(build),
  locus,
  loadDefaultGenomes: false,
  queryParametersSupported: false,
  tracks: [{type: "alignment", format, url: dataFile, indexURL: indexFile, name: roleLabel}],
};
const browser = await igv.createBrowser(document.getElementById("igv-viewer"), config);
```

- [ ] **Step 4: Run green/full verification and commit.** Run browser tests with a configured Chrome/Edge executable, `python -m pytest -q`, `python manage.py test pronto_web.reports`, migration check, and a browser network/CSP check. Document any environment-only browser skip. Commit as `feat: view local and registered alignments in report IGV`.

## Handoff to preservation plan

After Task 4, local viewing and registered read-only viewing work without any upload endpoint. Continue with `docs/superpowers/plans/2026-09-24-igv-preservation.md` only after this slice passes its browser and authorization tests. Do not claim the full approved feature complete at this point.
