# IGV Alignment Preservation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve a complete BAM/CRAM plus index only after a separate confirmed save action, then reopen it securely in the report.

**Architecture:** Extend the viewing slice with a write permission, managed file metadata, explicit upload sessions, and a pair-atomic publication service. Uploaded bytes are streamed to bounded staging only after confirmation, validated, then promoted to private managed storage; the existing authorized range route serves completed records. A separate deletion operation and deployment guard cover the retained-data lifecycle.

**Tech Stack:** Python 3, Django 5.2, pysam 0.24.1 for format/index validation, igv.js viewer from the viewing plan, pytest/Django TestCase, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-24-igv-alignment-sources-design.md`. **Prerequisite:** all tasks in `docs/superpowers/plans/2026-09-24-igv-viewing.md` are passing.

## Global Constraints

- No alignment bytes reach the server from local viewing or ordinary report **Lagre**. Only confirmed **Lagre filer for senere bruk** begins transfer.
- Save the complete alignment and matching index, never only an IGV image. Do not store them in the database, Git, static/media, or exported HTML.
- Read access permits viewing a pair; a separate explicit write grant is required to preserve or delete one. Authorize every request and keep CSRF protection on mutations.
- The managed root, quotas, approved local reference, backup/retention/deletion policy, and staging root must be configured before clinical saves are enabled. No public URL or default clinical upload destination.
- Do not silently overwrite a different pair for the same report/sample/build/role; identical pairs are idempotent.

## Review Focus

1. An upload begun by a permitted user but continued by a different user must be rejected (Task 3 test).
2. A misleading `.bam` extension with invalid content or a valid BAM with a corrupt index must not become READY (Task 2 test).
3. Duplicate completion/retry must not publish two records or orphan a partial pair (Task 2 test).
4. A user with read but not write access must view an existing pair but cannot save, replace, or delete it (Task 3 test).
5. Reloading during upload must show unsaved/failed state, not a saved badge; the server must later clean expired staging (Task 4/5 tests).

## File map

- `pronto_web/reports/models.py` and new migration: write grant, READY saved-pair metadata, upload session, audit event; no file bytes.
- `pronto_web/reports/alignment_store.py`: bounded private roots, generated keys, streaming chunk writes, checksum, validation, atomic publication, cleanup/deletion.
- `pronto_web/reports/alignment_commands.py`: authorize and coordinate save/copy/delete with database state.
- `pronto_web/reports/views.py`, `pronto_web/urls.py`, `pronto_web/reports/alignment_ranges.py`: save-session, completion, registered-copy, delete routes and range lookup for READY records.
- `pronto_report/static/report-igv.js`, `pronto_report/templates/report/variant-review.html`, `pronto_report/static/report.css`: separate confirmation, upload progress/cancel, unsaved/saved/error states.
- `pronto_web/reports/test_alignment_store.py`, `pronto_web/reports/test_alignment_commands.py`, `pronto_web/reports/tests.py`, `pronto/tests/reporting/browser/test_igv.py`: abuse, lifecycle, and browser tests using synthetic data only.
- `docs/igv-alignment-operations.md`, `requirements.txt`: deployment contract and pinned validation dependency.

---

### Task 1: Metadata, permission, and deployment guard

**Files:** Modify `pronto_web/reports/models.py`, create `pronto_web/reports/migrations/0002_alignment_storage.py`, `pronto_web/reports/test_alignment_models.py`; modify `pronto_web/settings.py`, `requirements.txt`, `docs/igv-alignment-operations.md`.

**Interfaces:** `ReportWriteGrant(report, user)` is distinct from `ReportGrant`. `SavedAlignment` has opaque UUID ID, report FK, sample/build/role/format, opaque data/index keys, sizes, SHA-256 digests, saving actor/time, and READY-only visibility. `AlignmentUploadSession` has owner, report/sample/build/role/format, expected sizes, received offsets, staging keys, expiry and state. `AlignmentEvent` records SAVE/COPY/DELETE and actor/time/record ID without raw reads or sensitive filename logging.

- [ ] **Step 1: Write failing model/config tests.**

```python
assert not ReportWriteGrant.objects.filter(report=record, user=reader).exists()
assert not alignment_saving_enabled(settings)
with override_settings(PRONTO_ALIGNMENT_STORE_ROOT="", PRONTO_ALIGNMENT_STAGING_ROOT=""):
    assert not alignment_saving_enabled(settings)
assert SavedAlignment.objects.filter(report=record).count() == 0
```

- [ ] **Step 2: Run red tests.** Run `python -m pytest pronto_web/reports/test_alignment_models.py -q`; expect missing models/helper.
- [ ] **Step 3: Add schema and fail-closed settings.** Pin `pysam==0.24.1`; add configuration for separate private managed/staging roots, maximum alignment/index bytes, minimum free space, approved reference files by build, and an explicit deployment policy acknowledgement. Defaults disable saving. Use unique constraint on ready identity plus checksums, and database state constraints. Never put bytes in `BinaryField`.

```python
def alignment_saving_enabled(config) -> bool:
    return all((config.PRONTO_ALIGNMENT_STORE_ROOT,
                config.PRONTO_ALIGNMENT_STAGING_ROOT,
                config.PRONTO_ALIGNMENT_POLICY_APPROVED,
                config.PRONTO_ALIGNMENT_MAX_BYTES > 0))
```

- [ ] **Step 4: Run green tests/migration check and commit.** Run `python manage.py makemigrations --check --dry-run`, `python manage.py test pronto_web.reports`, `python -m pip check`; commit as `feat: define private alignment metadata and write grants`.

### Task 2: Pair validation and pair-atomic private storage

**Files:** Create `pronto_web/reports/alignment_store.py`, `pronto_web/reports/test_alignment_store.py`; modify `docs/igv-alignment-operations.md`.

**Interfaces:** `validate_pair(data_path: Path, index_path: Path, format: Literal["bam", "cram"], reference_path: Path) -> AlignmentHeader` opens with pysam and requires index/random access. `publish_pair(staging_data: Path, staging_index: Path, destination_root: Path) -> PublishedPair` writes opaque private keys, sizes and SHA-256; either both are READY or neither is published. `remove_pair(pair: PublishedPair) -> None` verifies root containment and ownership metadata before deletion.

- [ ] **Step 1: Write failing validation/publication tests.** Use tiny synthetic coordinate-sorted BAM/BAI and CRAM/CRAI pairs created inside `tmp_path` with pysam and an explicit local reference; also create a corrupt index and a text file named `.bam`. Include a simulated exception between data/index promotion and assert no READY pair and no final orphan.

```python
assert validate_pair(bam, bai, "bam", reference).has_index is True
with pytest.raises(InvalidAlignmentPair):
    validate_pair(fake_bam, bai, "bam", reference)
with pytest.raises(InvalidAlignmentPair):
    validate_pair(bam, corrupt_bai, "bam", reference)
assert sha256(published.data_path.read_bytes()).hexdigest() == published.data_sha256
```

- [ ] **Step 2: Run red tests.** Run `python -m pytest pronto_web/reports/test_alignment_store.py -q`; expect missing module.
- [ ] **Step 3: Implement streaming and validation.** Use generated opaque names under an allowlisted root; reject symlinks/traversal, enforce quota before and during writes, hash while streaming, and fsync before atomic promotion. Open BAM/CRAM through `pysam.AlignmentFile` with the explicit index/reference shown below and probe a tiny indexed region. Compare available contig names/lengths to the declared local reference; block known mismatch, require explicit user build confirmation even when headers are plausible. Ensure htslib cannot use a remote reference fallback.

```python
with pysam.AlignmentFile(str(data_path), "rb" if format == "bam" else "rc",
                         index_filename=str(index_path),
                         reference_filename=str(reference_path),
                         require_index=True) as alignment:
    if not alignment.has_index():
        raise InvalidAlignmentPair("index unavailable")
```

- [ ] **Step 4: Run green tests and commit.** Run store tests and a test that `remove_pair` refuses a target outside the managed root; commit as `feat: validate and publish complete alignment pairs`.

### Task 3: Explicit save and delete commands

**Files:** Create `pronto_web/reports/alignment_commands.py`, `pronto_web/reports/test_alignment_commands.py`; modify `pronto_web/reports/models.py`, `pronto_web/reports/alignment_registry.py`.

**Interfaces:** `begin_local_save(actor, report, sample_id, build, role, format, sizes) -> AlignmentUploadSession` authorizes a write grant and creates no bytes before this deliberate command. `accept_chunk(actor, session_id, component, start, total, stream) -> int` accepts ordered bounded chunks. `complete_local_save(actor, session_id, declared_build) -> SavedAlignment` validates and publishes the pair. `preserve_registered(actor, report, source_id) -> SavedAlignment` copies a registered pair after explicit confirmation. `delete_saved(actor, report, saved_id) -> None` removes managed bytes/metadata and records the action. The existing registry/range resolver includes only READY saved records.

- [ ] **Step 1: Write failing command tests.**

```python
with pytest.raises(PermissionDenied):
    begin_local_save(reader, report, sample_id, "GRCh37", "TUMOUR_DNA", "bam", sizes)
session = begin_local_save(writer, report, sample_id, "GRCh37", "TUMOUR_DNA", "bam", sizes)
assert SavedAlignment.objects.count() == 0
with pytest.raises(PermissionDenied):
    accept_chunk(other_writer, session.id, "data", 0, sizes.data, stream)
saved = complete_local_save(writer, session.id, "GRCh37")
assert saved.data_sha256 == expected_sha
assert complete_local_save(writer, session.id, "GRCh37").id == saved.id
```

- [ ] **Step 2: Run red tests.** Run `python -m pytest pronto_web/reports/test_alignment_commands.py -q`; expect missing commands.
- [ ] **Step 3: Implement commands and audit.** Use transaction/row locks for session transitions and unique/idempotency checks. An upload belongs to its original actor and report; expired/cancelled sessions reject chunks. Reject different content under an existing report/sample/build/role without an explicit conflict resolution action; this first release offers no overwrite action. Clean staged parts on abort/expiry and on validation failure. Delete requires write grant and exact saved ID; never delete registered originals. Record SAVE/COPY/DELETE events without raw filename/read data.

```python
def require_alignment_write(actor, report):
    if not actor.is_authenticated or not actor.is_active or not ReportWriteGrant.objects.filter(
        report=report, user=actor
    ).exists():
        raise PermissionDenied
```

- [ ] **Step 4: Run green tests and commit.** Test same-pair idempotency, conflict, role isolation, copy of registered pair, no overwrite, expired session cleanup, authorized deletion and refusal to delete a registered original. Commit as `feat: coordinate explicit alignment preservation`.

### Task 4: Authenticated save protocol and retained range access

**Files:** Modify `pronto_web/reports/views.py`, `pronto_web/urls.py`, `pronto_web/reports/alignment_ranges.py`, `pronto_web/reports/tests.py`; create `pronto_web/reports/test_alignment_upload_http.py`.

**Interfaces:** `POST /reports/<id>/alignments/save-sessions/` creates session from small JSON metadata after confirmation; `PUT /reports/<id>/alignments/save-sessions/<uuid>/<data|index>/` carries one `Content-Range` raw chunk (maximum 8 MiB); `POST /reports/<id>/alignments/save-sessions/<uuid>/complete/` validates/publishes; `DELETE /reports/<id>/alignments/save-sessions/<uuid>/` cancels; `POST /reports/<id>/alignments/<source_id>/preserve/` copies registered pair; `DELETE /reports/<id>/alignments/<saved_id>/` deletes saved pair after explicit confirmation. All mutations require CSRF and write grant; read range route from Plan 1 accepts READY saved IDs with read grant.

- [ ] **Step 1: Write failing HTTP tests.**

```python
assert reader_client.post(start_url, data=metadata, content_type="application/json").status_code == 403
assert writer_client.post(start_url, data=metadata, content_type="application/json").status_code == 201
assert writer_client.put(chunk_url, data=chunk, content_type="application/octet-stream",
                         HTTP_CONTENT_RANGE="bytes 0-3/4").status_code == 204
assert writer_client.post(complete_url).status_code == 201
assert reader_client.get(saved_data_url, HTTP_RANGE="bytes=0-3").status_code == 206
assert stranger_client.get(saved_data_url, HTTP_RANGE="bytes=0-3").status_code == 404
```

- [ ] **Step 2: Run red tests.** Run `python -m pytest pronto_web/reports/test_alignment_upload_http.py -q`; expect missing routes.
- [ ] **Step 3: Implement bounded endpoints.** Check actor/report/session permissions before reading chunk body. Read the request stream in bounded blocks, not `request.body`; enforce exact `Content-Range`, contiguous offset, configured quota and session expiry. Return stable 400/403/404/409/413/416/507 errors without internal paths or sample data. Ensure Django CSRF is checked on all mutating routes. Make saved pair IDs resolve through the same authorized range service as registered IDs, without exposing storage keys.

```python
@require_http_methods(["PUT"])
def upload_alignment_chunk(request, report_id, session_id, component):
    session = authorized_upload_session(request.user, report_id, session_id)
    start, total = parse_chunk_range(request.headers["Content-Range"])
    next_offset = accept_chunk(request.user, session.id, component,
                               start, total, request)
    return HttpResponse(status=204, headers={"Upload-Offset": str(next_offset)})
```

- [ ] **Step 4: Run green tests and commit.** Use `Client(enforce_csrf_checks=True)` for missing/wrong CSRF tests, ungranted users, mismatched report/session IDs, oversized chunks, interrupted upload, duplicate completion and saved range retrieval. Run `python manage.py test pronto_web.reports`; commit as `feat: expose guarded alignment save and range routes`.

### Task 5: Save UX, lifecycle operations, and end-to-end verification

**Files:** Modify `pronto_report/static/report-igv.js`, `pronto_report/templates/report/variant-review.html`, `pronto_report/static/report.css`, `pronto/tests/reporting/browser/test_igv.py`, `docs/igv-alignment-operations.md`; create `pronto_web/reports/management/commands/clean_alignment_staging.py` and command test.

**Interfaces:** The IGV panel exposes separate `Lagre filer for senere bruk`, confirmation, progress, cancel, and saved/error states. The ordinary review save button never invokes the alignment protocol. Cleanup command removes only expired, owned staging records/files after allowlisted-root checks; saved READY data is not automatically purged by this command.

- [ ] **Step 1: Write failing browser/lifecycle tests.** Select synthetic BAM/index, open IGV, assert zero upload traffic; click ordinary review **Lagre**, assert zero upload traffic; click alignment save, cancel confirmation, assert zero upload traffic; confirm, assert start/chunk/complete order and saved badge only after completion. Simulate chunk failure/reload, assert unsaved state. Test cleanup refuses a non-expired or out-of-root path.

```python
page.get_by_role("button", name="Lagre filer for senere bruk").click()
assert page.get_by_text("Hele BAM/CRAM-filen og indeksen").is_visible()
page.get_by_role("button", name="Avbryt").click()
assert not alignment_upload_requests
page.get_by_role("button", name="Lagre filer for senere bruk").click()
page.get_by_role("button", name="Bekreft lagring").click()
expect(page.get_by_text("Lagret for senere bruk")).to_be_visible()
```

- [ ] **Step 2: Run red tests.** Run `python -m pytest pronto/tests/reporting/browser/test_igv.py -q` and cleanup command tests; expect missing controls/command.
- [ ] **Step 3: Implement explicit browser and operations flow.** Show sample/build/role/filenames/total bytes in confirmation; stream bounded chunks with progress and cancel, never auto-retry or auto-save; show a separate conflict/error panel. On reload, query only READY server records; local handles and incomplete sessions are not reported saved. Document registry setup, private roots, backup/retention/deletion approval, quota/reverse-proxy limits, locally hosted references, audit/restore, and safe staging cleanup. Synthetic fixtures only in Git.

```javascript
async function saveLocalPair({reportId, dataFile, indexFile, metadata, csrfToken}) {
  const session = await startSession(reportId, metadata, csrfToken);
  await sendChunks(session, "data", dataFile, 8 * 1024 * 1024, csrfToken);
  await sendChunks(session, "index", indexFile, 8 * 1024 * 1024, csrfToken);
  return completeSession(session, csrfToken);
}
```

- [ ] **Step 4: Verify and commit.** Run `python -m pytest -q`, `python manage.py test pronto_web.reports`, `python manage.py makemigrations --check --dry-run`, `python -m pip check`, browser tests, and a manual synthetic-file check of CSP/network requests. Review the diff for secrets and patient data. Commit as `feat: finish explicit IGV pair save workflow`.

## Completion boundary

The feature is not clinically deployable solely because tests pass. A deployment must explicitly configure and approve storage roots, quotas, local references, retention/deletion policy, backup/restore, HTTPS and the remaining Django production security settings. No clinical alignment data may enter the public Git repository or offline exports.
