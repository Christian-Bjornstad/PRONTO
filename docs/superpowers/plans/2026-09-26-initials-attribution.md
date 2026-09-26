# Initials Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open allowlisted local demo reports without login and record self-reported initials on save, finalization and application print requests.

**Architecture:** Keep the permission-bearing technical actor separate from declared initials. Extend the existing revision transaction for save/finalize attribution, and use a separate idempotent print audit. Enable login-free behavior only through a guarded demo startup command.

**Tech Stack:** Existing Python, Django, SQLite demo database, JSON Schema, vanilla JavaScript and Playwright; no new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-09-26-initials-attribution-design.md` (approved).

## Global Constraints

- Initials: trim, uppercase, then 2–8 letters A–Z plus Æ, Ø and Å; validate on server and client.
- Attribution is SELF_REPORTED, not verified identity or a digital signature.
- Local demo binds only to 127.0.0.1, with an isolated demo database and an explicit report allowlist.
- Standard installations retain authenticated authorization, CSRF, CSP and no-store behavior.
- Do not expose alignment upload, preservation, deletion or private clinical assets via demo access.
- Finalization remains locked; historical records and original ReportData remain unchanged.
- PRINT_REQUESTED is not proof that paper or PDF was produced. Browser-menu print and offline copies cannot be centrally guaranteed.
- Preserve the existing uncommitted, user-approved report-workspace increment. Do not reset or mix it into unrelated commits.

## Review Focus

- Two people share initials: record separate actions, never merge accounts (Task 2).
- Unicode lookalike or markup input: reject non-allowlisted letters, safely render accepted initials (Tasks 1, 5).
- A lost print response is retried: return the existing event only for an identical request (Task 4).
- Another tab saves before printing: reject stale revision instead of mislabelling output (Task 4).
- Host/forwarded headers claim locality: never use them to grant demo access; fail closed (Task 3).

## Task 1: Attribution contract and normalization

**Files:** Create `pronto_report/review/attribution.py`, `pronto/tests/reporting/test_attribution.py`; modify `pronto_report/review/contracts.py`, `pronto_report/models.py`, `pronto_report/validation.py`, `pronto_report/serialization.py`, `pronto_report/schemas/review-state-v2.schema.json`.

**Interfaces:** `normalize_initials(value: object) -> str` raises `ReviewCommandError` with INVALID_INITIALS/422. SaveDraftRequest and FinalizeRequest accept optional `declared_initials: str | None = None` from JSON `declaredInitials`. ReviewState gains optional `last_saved_attribution` and `finalization_attribution` mappings, serialized as `lastSavedAttribution` and `finalizationAttribution`, each `{declaredInitials, method: SELF_REPORTED}`. Missing fields remain omitted for historical serialization.

- [ ] Write failing tests `test_normalize_initials` (`' abø ' -> 'ABØ'`), `test_reject_invalid_initials` (`None`, 7, empty, one letter, nine letters, markup, spaces within, Cyrillic lookalikes), and `test_historical_and_attributed_review_round_trip` (old bytes unchanged; new fields retained).
- [ ] Run `python -m pytest pronto/tests/reporting/test_attribution.py -q`; confirm failure for missing behavior.
- [ ] Implement interfaces above. Extend strict field allowlists without allowing arbitrary command keys; validate direct dataclass callers in the service too. Do not accept client-declared verification methods.
- [ ] Run attribution, serialization, migration and review-contract tests; confirm PASS.
- [ ] Commit this contract increment with its tests only.

## Task 2: Persist save/finalization attribution atomically

**Files:** Modify `pronto_report/review/service.py`, `pronto_report/review/contracts.py`, `pronto_web/reports/models.py`, `pronto_web/reports/review_repository.py`, `pronto_web/reports/views.py`; create `pronto_web/reports/migrations/0004_initials_attribution.py`; extend `pronto_web/reports/tests_draft_save.py`.

**Interfaces:** ReviewCommandService adds keyword `require_initials: bool = False`. AuditRecord adds optional `declared_initials` and `attribution_method`; ReviewAudit stores matching nullable fields. Save sets lastSavedAttribution from normalized command initials. Finalize sets finalizationAttribution without replacing the prior saver. Technical actor IDs remain unchanged.

- [ ] Add failing tests: `test_initials_required_mode_rejects_missing_without_write`, `test_save_attribution_commits_with_revision`, `test_same_initials_can_finalize`, `test_two_actors_sharing_initials_remain_distinct`, `test_audit_failure_rolls_back_revision`, `test_old_record_has_no_invented_initials`.
- [ ] Run `python manage.py test pronto_web.reports.tests_draft_save --verbosity 1` with a process-local PRONTO_DJANGO_SECRET_KEY; confirm the new tests fail.
- [ ] Implement Task 1 contracts in the existing transaction; derive method on server. Ignore any draft attempt to rewrite attribution history, taking prior values from current saved state. Preserve existing authorization, conflict and FINAL_LOCKED checks.
- [ ] Run Django draft tests and framework-neutral service tests; run `python manage.py makemigrations --check --dry-run`; expect PASS/no changes.
- [ ] Commit models, migration, service and tests as one increment.

## Task 3: Guarded local demo without a login page

**Files:** Create `pronto_web/reports/demo_access.py`, `pronto_web/reports/management/commands/run_demo.py`, `pronto_web/reports/tests_demo_access.py`; modify `pronto_web/settings.py` and report access integration in `pronto_web/reports/views.py`.

**Interfaces:** `demo_principal(request, report_id: str)` returns the configured restricted user only when demo mode is active, REMOTE_ADDR is loopback, Host is permitted, the resolved route is an allowlisted report/index/save/finalize/print view and report ID is explicitly allowed. Otherwise grant nothing. `python manage.py run_demo --database <dedicated-path> --report <id> --port 8768` binds to 127.0.0.1 only and enables initials-required mode.

- [ ] Write failing tests: allowlisted demo GET returns 200 without a session; standard anonymous GET remains 401; unlisted report stays inaccessible; non-loopback remote, forged forwarded headers and invalid Host never authorize; every alignment route stays inaccessible; absent allowlist/database and non-loopback bind fail startup.
- [ ] Run `python manage.py test pronto_web.reports.tests_demo_access --verbosity 1`; confirm RED.
- [ ] Implement the explicit startup mode and access resolver. Use a dedicated non-superuser with only the configured ReportGrants, no ReportWriteGrants. Reject reuse of the ordinary configured database. Seed only the approved fixture in an isolated demo DB, leaving existing demo and finalized records intact. Never infer allowlist from all database rows. Preserve CSRF validation and existing security middleware.
- [ ] Run demo-access and existing read/access tests; confirm PASS. Document the startup command and the local-only boundary in `docs/report-review-workspace.md`.
- [ ] Commit this demo-specific increment.

## Task 4: Revision-bound, idempotent print-request audit

**Files:** Create `pronto_web/reports/print_audit.py`, `pronto_web/reports/tests_print_audit.py`, `pronto_web/reports/migrations/0005_print_audit.py`; modify `pronto_web/reports/models.py`, `pronto_web/reports/views.py`, `pronto_web/urls.py`.

**Interfaces:** POST `/reports/<report_id>/print-requests/` accepts `{schemaVersion: '1.0', revision: int, requestId: UUID, declaredInitials: str}`. Return event `{requestId, reportId, revision, declaredInitials, method: SELF_REPORTED, action: PRINT_REQUESTED, requestedAt}`. New ReportPrintAudit stores report, revision, technical actor, initials, method, UUID, action and server time with unique `(report, request_id)`.

- [ ] Write failing tests for denied/missing-CSRF requests, invalid initials, stale revision (409), multiple prints for one revision, identical retry returning the same event/time, reused UUID with different payload/actor (409), audit-write failure and unchanged review revision/finalizer.
- [ ] Run `python manage.py test pronto_web.reports.tests_print_audit --verbosity 1`; confirm RED.
- [ ] Implement `record_print_request(record, actor, revision: int, request_id: UUID, initials: str) -> ReportPrintAudit`. Check access, serialize with the report lock, validate current revision for new events, and acknowledge identical existing events on retry. Use server time, CSRF, payload-size limits, no-store and generic errors. No clinical content in print audit.
- [ ] Run print tests and migration checks; confirm PASS.
- [ ] Commit print audit separately from browser work.

## Task 5: Accessible initials dialogs and attributed output

**Files:** Create `pronto_report/static/report-attribution.js`, `pronto_report/renderers/attribution.py`, `pronto/tests/reporting/browser/test_attribution.py`; modify `pronto_report/renderers/html.py`, `pronto_report/templates/report/base.html`, `pronto_report/static/report.js`, `pronto_report/static/report.css` and relevant renderer tests.

**Interfaces:** Expose `requestDeclaredInitials(action: string) -> Promise<string | null>` via a small browser module included before report.js (include its bytes in standalone/CSP generation). Renderer helper `render_attribution(review, snapshot: bool) -> str` distinguishes saver, finalizer and print requester. HTML context explicitly provides initials-required mode and same-origin print URL.

- [ ] Write failing browser tests for dialog labels/focus/keyboard cancellation, invalid input, no write on cancel, normalized initials on save/finalize, save/reload display, same-person finalization, dirty-print refusal, failed print audit refusal, stable UUID on retry, escaped values and absence of persisted identity in localStorage.
- [ ] Run `python -m pytest pronto/tests/reporting/browser/test_attribution.py -q`; confirm RED.
- [ ] Implement Task 1–4 integration. Ask for initials before locking/sending each explicit action. Preserve the finalization confirmation. For printing require clean saved state, POST audit, verify acknowledgment matches requested report/revision, set print-only attribution and call window.print. Never log PRINT_COMPLETED. Disable repeat clicks in flight; reset appropriately on cancellation/failure.
- [ ] Render “Initialer ikke registrert” for historical records and “Selvoppgitte initialer” for new attribution. Label offline exports local-only and preserve draft/final watermark. Keep finalizer unchanged after printing. No global authorization switch in browser code.
- [ ] Run browser and renderer tests; verify 320/768/1440px layouts, keyboard focus and clean console. Commit the UI increment.

## Task 6: Integrated verification and user preview

**Files:** Extend `pronto_web/reports/tests_demo_access.py` and `docs/report-review-workspace.md`; update this plan's completed checkboxes.

**Interfaces:** Use Tasks 1–5 without creating new public APIs.

- [ ] Add integration test `test_demo_save_finalize_print_history`: no login; initials required; distinct saved and final attribution; print request does not mutate final revision; original source unchanged. Assert absence of access to an unlisted report and alignment bytes throughout.
- [ ] Run `python -m pytest pronto/tests/reporting -q`, `python manage.py test pronto_web.reports`, `python manage.py makemigrations --check --dry-run`, and `git diff --check`; all must pass. Do not lower or skip existing checks.
- [ ] Launch `run_demo` with its new isolated fixture DB, open the report directly, and exercise initials dialogs in Chrome. Preserve original report.html and existing finalized demo. Confirm no login screen, inspect visible attribution and print preview, and record limitations honestly.
- [ ] Review all security and migration changes before push/PR; keep credentials and demo database out of Git. Report tests and local preview URL, and attach any created PR. No production deployment or merge without the appropriate existing authorization.

## Execution choice

Recommended: native execution in this session because the six tasks share
contracts and are sequential. User reviews this plan and selects native or
subagent-driven execution before implementation. Native execution was approved;
one independent final reviewer checked the implementation.

## Implementation evidence (2026-09-26)

Tasks 1–6 implemented in the existing isolated worktree. Red/green evidence:
12 contract failures -> 12 passes; attribution/save 16 passes; demo access RED
then green; print audit RED then green; browser dialog RED then green. Final
reporting suite: 203 passed. Final Django suite: 49 passed; migrations clean.
Full project `python -m pytest -q`: 270 passed, 17 skipped (existing optional tests).
Real Chrome-to-Django test: anonymous demo open, save AB, reload AB, finalize CD,
print EF. UI checked at 320/768/1440px. Separate demo databases preserved the
previous final report and kept the user-facing example as a draft.

Independent review found one Important issue: technical finalizer IDs still
appeared in human-facing labels. Regression test failed in live and snapshot
rendering before the fix and passed afterward.

Execution decisions and limits:
- Reject Unicode expansion characters before uppercase conversion; cost: unusual
  initials outside the explicit alphabet require future support.
- Each run_demo start requires a new filename to avoid reusing clinical/final
  databases; cost: command restarts do not resume the previous demo database.
- Offline printing remains local-only, without fresh requester initials or
  central logging; it is not the live database workflow.
- UI and prior approved workspace changes share renderer/JS files and are kept
  together; cost: a larger UI diff, not a rewrite of existing user data.
- Production deployment, clinical validation, print completion, and SQLite load
  concurrency are not claimed verified; they require separate deployment work.

Follow-up fixed the minor stored-initials finding: JSON Schema now explicitly
rejects every character outside A–Z/Æ/Ø/Å, including a terminal newline.
The regression test failed for `AB\n` before the fix; normalized command input
and historical records without attribution remain supported.
