# Django draft revision endpoint

Task 26 adds `POST /reports/<report-id>/revisions/` for an authenticated user
with a `ReportGrant` on that exact report. Task 27 connects the original
**Lagre** control on the authenticated draft page. A missing grant or report is
reported as 404 without revealing the report data. Mutating requests require
Django session CSRF protection. Responses use `Cache-Control: no-store`.

The request is the complete versioned `SaveDraftRequest` described in
`docs/review-command-contract.md`: `schemaVersion`, `reportId`, `baseRevision`,
and a full validated v2 `draft`. JSON bodies are capped at 1 MiB. A successful
request creates the next `ReviewRevision` and one `ReviewAudit` row in a single
transaction and returns HTTP 201 with the saved review and audit. The report
grant is checked again inside that transaction, so a revoked grant cannot
commit after an earlier authorization check. The actor ID
and timestamp come from the server, not the browser. Repeating an old base
revision returns 409 with `currentRevision`; invalid commands/drafts return
422; oversized bodies return 413. No unsuccessful request creates a revision.

The unique `(report, revision)` constraints on both tables are a final guard
against duplicate commits. Django's `atomic()` encloses both writes, while
`select_for_update()` serializes writers on databases that support row locks.
SQLite is useful for local development but does not implement
`select_for_update()`; production database and concurrent-writer behavior
require deployment review before real patient data is used. This branch adds
`0002_review_audit` independently of the IGV storage branch's migration;
integrating both branches will require a Django merge migration.

The live page starts clean and never autosaves. A click submits its current
base revision with the complete draft and any reasoned source corrections.
Only an acknowledged HTTP 201 advances the local revision and clears the
unsaved indicator. A 409 retains local edits, shows the newer revision, and
offers a JSON export or a confirmed reload. Validation and network failures
likewise retain edits; navigating away with unsaved work warns the user.
Nothing is written to `localStorage`. Offline HTML exports retain their
network-denying CSP, while only the authenticated draft page permits
same-origin requests. The raw ReportData remains immutable; saved correction
projection into the visible fact and metric cards is still a follow-up.

Verify with `python manage.py test pronto_web.reports.tests_draft_save` and
`python manage.py makemigrations --check --dry-run` after setting a local
`PRONTO_DJANGO_SECRET_KEY`. Tests use only the approved synthetic report.
