# Report reset, reference fidelity, and standalone HTML export

> **Agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan. In this thread, use `superpowers:executing-plans` because the owner asked to carry on here; do not create another agent or checkout.

**Goal:** Make the database-backed review workspace closer to the local `report.html`, add a safe DRAFT reset, and download a compact, standalone HTML report from an audited saved revision.

**Architecture:** Keep immutable facts in `ReportData`, human decisions in versioned `ReviewState`, and all writes in Django's authorized review/export adapters. Extend the review command service for reset; use a separate no-script HTML renderer for delivery. The browser remains a working copy and never supplies export content.

**Tech Stack:** Python, Django, Jinja templates, vanilla JavaScript/CSS, SQLite demo persistence, pytest, Playwright browser tests.

**Spec:** [2026-09-29-report-workspace-reset-and-html-export-design.md](../specs/2026-09-29-report-workspace-reset-and-html-export-design.md)

**Global Constraints:** Work only in the existing `feature/report-review-workspace` worktree. Do not reload or change the user's open `demo-fidelity-20260929` report; use an isolated test database and a new demo ID for manual checks. Preserve existing source data, old revisions, audit rows, JSON recovery, and IGV/alignment behaviour. All new text shown in the product is English. After each slice, run targeted tests and make one focused commit. Do not push or update PR #24 until the full suite and browser checks pass.

**Review Focus:** Check that reset retains the read-only imported legacy note; stale or FINAL reset writes nothing; the HTML file includes each selected occurrence once and never unsaved choices; untrusted text cannot create markup/scripts; duplicate export request IDs are idempotent but conflicting reuse is rejected; the download audit never claims that a file was saved by the browser.

## Task 1 — Match the reference TMB gauge and simplify attribution/correction copy

**Files:** Modify `pronto_report/renderers/html.py`, `pronto_report/templates/report/key-findings.html`, `pronto_report/static/report.js`, and the report CSS file located by `rg --files pronto_report/static`. Test in `pronto/tests/reporting/test_saved_correction_projection.py`, `pronto/tests/reporting/test_reference_shell.py`, `pronto/tests/reporting/browser/test_tumour_board.py`, and `pronto/tests/reporting/browser/test_attribution.py`.

1. Write failing renderer tests for a 0–30 track with green `0–5`, yellow `>5–20`, red `>20`, ticks and cursor; assert the existing value-correction reason/source value is still present in an accessible disclosure and `(self-reported initials)` is absent. Include boundary values 5 and 20. Run `python -m pytest -q pronto/tests/reporting/test_saved_correction_projection.py pronto/tests/reporting/test_reference_shell.py` and confirm the new assertions fail for the intended reason.
2. Write a failing Playwright test that moves the cursor with pointer and arrow keys, verifies the display and dirty state, then saves a reasoned correction. Run `python -m pytest -q pronto/tests/reporting/browser/test_tumour_board.py` and confirm the new test fails.
3. Reproduce the local reference's gauge visuals and keyboard semantics, without creating a clinical classification field. Replace the tall correction paragraph with a compact **Corrected** indicator and native `<details>` disclosure. Remove only the visible parenthetical attribution wording; retain `SELF_REPORTED` in stored records.
4. Rerun the targeted tests plus `python -m pytest -q pronto/tests/reporting/browser/test_attribution.py`. Commit `feat: align TMB gauge and compact attribution display`.

## Task 2 — Align the Variant review table and stack paired CNV plots

**Files:** Modify `pronto_report/renderers/html.py`, `pronto_report/templates/report/variant-review.html`, `pronto_report/templates/report/cnv-plots.html`, relevant report CSS and `pronto_report/static/report.js`. Test in `pronto/tests/reporting/browser/test_compact_workspace.py`, `pronto/tests/reporting/browser/test_report.py`, and `pronto/tests/reporting/test_html_surfaces.py`.

1. Add failing browser assertions at 320, 768, 1024 and 1440 px: every visible Variant review column heading shares its column boundaries with the corresponding value, desktop primary columns need no horizontal scrolling, and narrow screens scroll the table rather than the whole page. Include source depth, absent-value placeholder, search/sort and duplicate variant occurrence checks. Run `python -m pytest -q pronto/tests/reporting/browser/test_compact_workspace.py` and confirm failure.
2. Add failing renderer/browser assertions that A1 appears immediately above A2 in one CNV group, followed by B2/B3, C1/C2, C3/C4 and C6; all nine source plots remain reachable with individual captions and enlarge actions. Run `python -m pytest -q pronto/tests/reporting/test_html_surfaces.py pronto/tests/reporting/browser/test_report.py` and confirm failure.
3. Give headers and cells one shared grid/column definition, keeping Inc/Exc/Path/Uns, row identity, Details, data order and compact desktop layout. Replace the single-plot switcher with stacked pairs, retaining the original image URLs and titles. Avoid a browser-global state change that could affect other tabs.
4. Rerun the three targeted test files and inspect actual 320/768/1024/1440 px screenshots. Commit `feat: align review table and pair CNV plots`.

## Task 3 — Add an atomic, revision-checked DRAFT reset command

**Files:** Modify `pronto_report/review/contracts.py`, `pronto_report/review/service.py`, `pronto_web/reports/models.py`, `pronto_web/reports/review_repository.py` only if needed, and add `pronto_web/reports/migrations/0006_reset_draft.py`. Test in `pronto/tests/reporting/test_review_service.py`, `pronto_web/reports/tests_draft_save.py`, and `pronto_web/reports/tests_attribution.py`.

**Interface:** `ResetDraftRequest.from_dict({schemaVersion, reportId, baseRevision, declaredInitials}) -> ResetDraftRequest`; `ReviewCommandService.reset(request, *, actor_id, report) -> ReviewCommandResponse`. No client-supplied draft on reset.

1. Add failing service tests named `test_reset_creates_blank_revision_and_audit`, `test_reset_preserves_imported_legacy_note_and_source`, and `test_reset_stale_or_final_writes_nothing`. Blank means no variant decisions/comments, QC `NOT_REVIEWED`, empty editable notes and corrections. Preserve `notes.importedLegacyNote` as read-only source-derived context. Run `python -m pytest -q pronto/tests/reporting/test_review_service.py` and confirm failures.
2. Add failing Django transaction tests for one new `ReviewRevision` plus `RESET_DRAFT` audit, actor/initials, revoked grant, missing/invalid initials, stale revision, FINAL lock and rollback when audit insert fails. Run `python -m pytest -q pronto_web/reports/tests_draft_save.py pronto_web/reports/tests_attribution.py` and confirm failures.
3. Implement the reset parser separately from the save/finalize parser; reuse service authorization, base-revision validation, timestamp and repository's atomic commit. Build the new v2 review document from `current` metadata, clearing only editable fields, set new reviewer/last-saved attribution and `revision + 1`, validate against `ReportData`, then commit `RESET_DRAFT`. Add the audit choice migration without touching existing rows.
4. Rerun the targeted tests and `python -m pytest -q pronto/tests/reporting/test_review_migration.py`. Commit `feat: add audited review reset command`.

## Task 4 — Expose reset safely in Django and the workspace

**Files:** Modify `pronto_web/reports/views.py`, `pronto_web/urls.py`, `pronto_web/reports/demo_access.py`, `pronto_report/renderers/html.py`, `pronto_report/templates/report/base.html`, `pronto_report/static/report.js`. Test in `pronto_web/reports/tests_draft_save.py`, `pronto_web/reports/tests_demo_access.py`, and `pronto/tests/reporting/browser/test_save_flow.py`.

**Interface:** `POST /reports/<report_id>/resets/` accepts the reset command JSON and returns the standard `ReviewCommandResponse`; successful UI reloads the returned saved state, not local defaults.

1. Add failing HTTP tests for CSRF, authorized actor/report, initial validation, current revision, FINAL lock, and exactly one revision/audit on success; ensure failed requests have no write. Run `python -m pytest -q pronto_web/reports/tests_draft_save.py pronto_web/reports/tests_demo_access.py` and confirm failures.
2. Add a failing browser test that edits a saved DRAFT, cancels Reset, then confirms Reset with initials; verify canceled action leaves working copy, success clears dirty state and shows original facts. Check a simultaneous stale save/reset produces a conflict message without replacing the working copy. Run `python -m pytest -q pronto/tests/reporting/browser/test_save_flow.py` and confirm failure.
3. Add the route and demo read/write allowlist entry. Render Reset only for DRAFT. Confirm with report-specific warning and initials, use the existing CSRF/error patterns, disable concurrent save/reset/finalize submissions, and rehydrate all controls from the returned review.
4. Rerun targeted tests and manual reset on a new isolated demo report ID. Commit `feat: expose confirmed draft reset in workspace`.

## Task 5 — Render a reduced, offline HTML report from saved data

**Files:** Add `pronto_report/renderers/summary_html.py` and `pronto/tests/reporting/test_summary_html.py`; reuse existing `ReportData`/`ReviewState` projections without modifying source values.

**Interface:** `render_summary_html(report: ReportData, review: ReviewState, *, export_initials: str) -> str`. It accepts only validated domain objects supplied by the adapter, not DOM or raw request JSON.

1. Write failing tests for identification, Key findings, saved TMB correction, exactly one row per `INCLUDE` variant occurrence, three-decimal AF, tumour depth, saved interpretation/therapeutic/additional notes, and visible revision/initials. Exclude undecided/excluded variants, workspace tabs, scripts, external resources and invented OncoKB/biomarker claims. Run `python -m pytest -q pronto/tests/reporting/test_summary_html.py` and confirm failures.
2. Add escaping tests using source and note strings containing `<script>`, quotes, ampersands and hostile URLs; assert none become HTML elements, inline event handlers or external requests. Include empty/missing facts and FINAL snapshot. Run the same test file and confirm failures.
3. Implement a dedicated minimal document with inline print CSS, semantic headings/table and no JavaScript, remote assets, IGV or fetches. Escape every variable interpolation. Keep correction provenance in a compact notes area and use `Not available` for absent external annotations.
4. Rerun `python -m pytest -q pronto/tests/reporting/test_summary_html.py pronto/tests/reporting/test_html_export.py`. Open a generated fixture as a local file, inspect print preview and offline rendering. Commit `feat: render standalone saved-review HTML`.

## Task 6 — Add an audited, idempotent HTML download endpoint and button

**Files:** Add a Django model `ReportHtmlExportAudit`, `pronto_web/reports/migrations/0007_html_export_audit.py`, and `pronto_web/reports/html_export_audit.py`; modify `pronto_web/reports/views.py`, `pronto_web/urls.py`, `pronto_web/reports/demo_access.py`, `pronto_report/renderers/html.py`, `pronto_report/templates/report/base.html`, `pronto_report/static/report.js`. Add `pronto_web/reports/tests_html_export.py` and extend `pronto/tests/reporting/browser/test_save_flow.py`.

**Interface:** `POST /reports/<report_id>/html-exports/` with `{schemaVersion, reportId, revision, declaredInitials, requestId}`. Return a UTF-8 `text/html` attachment only after authorization, validation, saved-revision match, audit write and successful rendering. Audit action is `HTML_DOWNLOAD_REQUESTED`, never `DOWNLOADED`.

1. Add failing Django tests for content/disposition, CSP and `X-Content-Type-Options: nosniff`; actor/grant, CSRF, initials and UUID validation; stale revision and report mismatch; one audit for exact retry, including a retry after a newer revision exists; 409 for same UUID with different actor/initials/revision; no attachment/audit on failure. Assert a retry renders the recorded historical revision, not the current one. Run `python -m pytest -q pronto_web/reports/tests_html_export.py` and confirm failures.
2. Add a failing browser test that a saved DRAFT and FINAL show **Download report HTML**, dirty edits block export with a save-first message, and a clean export sends current revision and initials without refreshing the editor. Run `python -m pytest -q pronto/tests/reporting/browser/test_save_flow.py` and confirm failure.
3. Implement the atomic export-audit service using the print-audit pattern, but a separate model/table. For a new request, check latest saved revision, load its snapshot, render within the transaction, then write the audit before returning bytes; a rendering/audit error rolls back and sends no attachment. For a retry, validate the recorded request identity first and render its recorded historical revision, even if a newer revision exists. Add restrictive CSP (`default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'`) and attachment headers. Replace the primary print button and JS handler; retain historical print route/data for compatibility.
4. Rerun targeted tests plus `python -m pytest -q pronto_web/reports/tests_print_audit.py pronto_web/reports/tests_demo_access.py`. Commit `feat: download audited standalone HTML report`.

## Task 7 — Integrated verification, demo and handoff

**Files:** Extend existing browser tests only where an end-to-end gap remains; update `docs/` demo guidance with the new Reset and Download report HTML flow. Do not alter the user's open demo data.

1. Run `python -m pytest -q` and fix any regression via a new failing test before code changes. Run migration consistency check in the configured Django test environment and confirm no missing migration. Inspect `git diff --check` and review the full diff for unintended copy, authentication, source-data or audit changes.
2. In a fresh isolated demo database/report, save a decision, QC note, interpretation note and TMB correction. Reset with initials; inspect the revision/audit rows and verify immutable report facts and old revisions. Then save new included variants and notes, download HTML, disconnect network, open and print-preview the file. Verify selected variants, correction, revision/initials, escaping and no network requests. At 320/768/1024/1440 px verify table headings, gauge and A1/A2 plot order.
3. Update concise presentation/demo instructions with the new flow and explicit demo ID. Commit `docs: update report review demo for reset and HTML download`. Push the branch and update PR #24 with verified test results and screenshots or a concise checklist; do not merge without owner review.
