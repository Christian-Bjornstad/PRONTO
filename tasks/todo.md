# Task List: PRONTO reporting foundation

## Task 1: Reproducible Python development setup

**Description:** Add a concise contributor setup and safe ignore rules so the repository can be installed and tested in an isolated environment without manual path changes.

**Acceptance criteria:**
- [x] Windows and Linux setup commands are documented.
- [x] Virtual environments, generated reports, local state, and secrets are ignored without hiding approved fixtures.
- [x] The documented focused and full test commands match CI.

**Verification:**
- [x] Create a clean virtual environment and install committed requirements.
- [x] `python -m pytest -q` reaches test execution.
- [x] `git status --ignored --short` confirms the intended exclusions.

**Dependencies:** None

**Files likely touched:**
- `.gitignore`
- `CONTRIBUTING.md`

**Estimated scope:** Small: 2 files

## Task 2: Green cross-platform unit-test baseline

**Description:** Reproduce and fix the current Windows path assertion failures without changing production path resolution behavior.

**Acceptance criteria:**
- [x] Tests compare paths semantically across Windows and Linux.
- [x] No test is skipped, deleted, or weakened.
- [x] Existing production behavior is unchanged.

**Verification:**
- [x] RED: focused path tests fail on the current assertions.
- [x] GREEN: focused path tests pass after normalization.
- [x] Full unit suite passes in the clean environment.

**Dependencies:** Task 1

**Files likely touched:**
- `pronto/tests/pronto_test.py`

**Estimated scope:** Small: 1 file

## Task 3: Pull-request CI baseline

**Description:** Run unit and non-publishing Docker validation for pull requests while preserving release publishing behavior.

**Acceptance criteria:**
- [x] Test workflow runs for pull requests and pushes to `main`.
- [x] Pull requests build but never push a Docker image.
- [x] Image publishing remains limited to the reviewed release/main policy.

**Verification:**
- [x] Workflow syntax parses successfully.
- [x] Local unit and Docker commands match workflow commands.
- [x] Diff contains no secret values or broadened secret exposure.

**Dependencies:** Tasks 1–2

**Files likely touched:**
- `.github/workflows/test.yml`
- `.github/workflows/build.yml`

**Estimated scope:** Small: 2 files

## Task 4: Fixture and privacy policy

**Description:** Document which repository fixtures are approved, which local artifact classes are excluded by default, and how new fixtures are approved.

**Acceptance criteria:**
- [x] Approved public fixtures are named.
- [x] Generated HTML, Office files, screenshots, and extracted derivatives have explicit handling rules.
- [x] The approval owner and staged-data review process are documented.

**Verification:**
- [x] Manual review against `docs/discovery-html-django.md`.
- [x] Staged files contain no unique local report artifact.

**Dependencies:** Task 1

**Files likely touched:**
- `docs/fixture-and-privacy-policy.md`

**Estimated scope:** Extra small: 1 file

## Checkpoint: Baseline

- [x] Unit suite passes in a clean environment.
- [x] Docker fixture command succeeds where Docker is available.
- [x] CI and documentation agree on commands.
- [x] Human reviews the baseline before contract implementation.

## Task 5: JSON Schema contracts

**Description:** Define v1 `ReportData` and `ReviewState` schemas from failing validation examples.

**Acceptance criteria:**
- [x] Required fields, enums, formats, bounds, and additional-property policy are explicit.
- [x] Review decision and clinical classification are independent fields.
- [x] Unknown major versions and oversized collections are rejected; cross-document report-ID mismatch is assigned to the Task 6 boundary validator.

**Verification:**
- [x] RED: invalid contract examples initially lack a validator or pass incorrectly.
- [x] GREEN: focused schema tests accept valid and reject invalid examples.

**Dependencies:** Baseline checkpoint

**Files likely touched:**
- `pronto_report/schemas/report-data-v1.schema.json`
- `pronto_report/schemas/review-state-v1.schema.json`
- `pronto/tests/reporting/test_schemas.py`

**Estimated scope:** Medium: 3 files

## Task 6: Typed models and validation errors

**Description:** Implement the smallest typed in-process representation and structured validation issue model required by the schemas.

**Acceptance criteria:**
- [x] Models distinguish immutable report facts from review activity.
- [x] Validation failures use stable codes, paths, and safe messages.
- [x] User-facing errors exclude stack traces and input file contents.

**Verification:**
- [x] RED/GREEN focused model and validation tests.
- [x] Type annotations cover public constructors and validators.

**Dependencies:** Task 5

**Files likely touched:**
- `pronto_report/models.py`
- `pronto_report/validation.py`
- `pronto/tests/reporting/test_models.py`
- `pronto/tests/reporting/test_validation.py`

**Estimated scope:** Medium: 4 files

## Task 7: Stable identity and duplicate diagnostics

**Description:** Generate deterministic report, variant, and occurrence identifiers while preserving duplicate source rows and warning about fallback identity.

**Acceptance criteria:**
- [x] Same normalized input produces the same ID.
- [x] Reference/alternate-aware identity is preferred.
- [x] Duplicate occurrences remain traceable and emit structured diagnostics.

**Verification:**
- [x] RED/GREEN identity tests include the duplicate TERT example.
- [x] Tests cover normalization and collision-warning behavior.

**Dependencies:** Task 6

**Files likely touched:**
- `pronto_report/identity.py`
- `pronto/tests/reporting/test_identity.py`

**Estimated scope:** Small: 2 files

## Task 8: Deterministic JSON serialization

**Description:** Serialize and load validated contracts deterministically without semantic loss.

**Acceptance criteria:**
- [x] Output is stable for the same logical model.
- [x] Round-trip preserves values, IDs, warnings, and provenance.
- [x] Invalid input fails before an internal model is returned.

**Verification:**
- [x] RED/GREEN serialization and round-trip tests.
- [x] Two serializations of the same model are byte-identical.

**Dependencies:** Tasks 6–7

**Files likely touched:**
- `pronto_report/serialization.py`
- `pronto/tests/reporting/test_serialization.py`

**Estimated scope:** Small: 2 files

## Task 9: Approved fixture adapter

**Description:** Convert one approved existing OUS public fixture into the v1 contract without hard-coded clinical values.

**Acceptance criteria:**
- [x] Source fields map with provenance and explicit missing-data warnings.
- [x] The approved fixture validates and contains stable IDs.
- [x] No value is invented when the source is absent.

**Verification:**
- [x] RED/GREEN adapter tests against the approved fixture.
- [x] Generated JSON validates and round-trips.
- [x] Manual comparison with the local reference report's key values.

**Dependencies:** Tasks 5–8

**Files likely touched:**
- `pronto_report/adapters/pronto_output.py`
- `pronto_report/cli.py`
- `pronto/tests/reporting/test_pronto_output_adapter.py`
- `pronto/tests/reporting/fixtures/expected-report-data.json`

**Estimated scope:** Medium: 4 files

## Checkpoint: Contract

- [x] Schema, model, identity, serialization, and adapter tests pass.
- [x] Approved fixture validates and round-trips deterministically.
- [x] Human reviews the contract example before renderer implementation.

## Task 10: Accessible renderer shell

**Description:** Create the modular HTML source, design tokens, and five accessible tab panels using the local report as the visual reference.

**Acceptance criteria:**
- [x] All five panels render with semantic landmarks and correct tab relationships.
- [x] Design tokens preserve the InPreD blue/neutral/status palette.
- [x] No whole-page horizontal overflow at target widths.

**Verification:**
- [x] RED/GREEN renderer structure tests.
- [x] Browser screenshots at 375, 768, 1024, and 1440 px.
- [x] Keyboard tab navigation and focus indicators work.

**Dependencies:** Contract checkpoint

**Files likely touched:**
- `pronto_report/renderers/html.py`
- `pronto_report/templates/report/base.html`
- `pronto_report/static/report.css`
- `pronto_report/static/report.js`
- `pronto/tests/reporting/test_html_renderer.py`

**Estimated scope:** Medium: 5 files

## Task 11: Key findings and variant table

**Description:** Render contract-derived biomarkers, case facts, searchable variants, sorting, formatting, and explicit empty/error states.

**Acceptance criteria:**
- [x] No clinical value or threshold is hard-coded in the browser.
- [x] Numeric values use declared display formatting.
- [x] Search, filters, and sorting are accessible and deterministic.

**Verification:**
- [x] Focused renderer tests for normal, missing, and empty data.
- [x] Browser test for search and sorting.
- [x] Visual comparison with the reference report.

**Dependencies:** Task 10

**Files likely touched:**
- `pronto_report/templates/report/key-findings.html`
- `pronto_report/templates/report/variant-review.html`
- `pronto_report/static/report.js`
- `pronto/tests/reporting/test_html_renderer.py`

**Estimated scope:** Medium: 4 files

## Task 12: Review-state presentation

**Description:** Present and edit validated `ReviewState` with independent reporting decision and clinical classification controls.

**Acceptance criteria:**
- [x] Decision and classification can vary independently.
- [x] FINAL state disables editing and shows provenance/status clearly.
- [x] Mismatched report state is rejected without an override prompt.

**Verification:**
- [x] RED/GREEN state validation and rendering tests.
- [x] Browser test covers edit, validation feedback, and FINAL lock.

**Dependencies:** Task 11

**Files likely touched:**
- `pronto_report/templates/report/variant-review.html`
- `pronto_report/static/report.js`
- `pronto_report/static/report.css`
- `pronto/tests/reporting/test_html_review_state.py`

**Estimated scope:** Medium: 4 files

## Task 13: CNV, QC, and tumour-board surfaces

**Description:** Render the remaining reference-report surfaces from declared assets and review notes.

**Acceptance criteria:**
- [x] Plot switcher, captions, enlargement, and focus return work.
- [x] QC cards include text status and declared thresholds.
- [x] Tumour-board view shows only eligible reviewed findings and explicit sign-off state.

**Verification:**
- [x] Renderer tests cover missing and present plots/QC.
- [x] Browser keyboard and focus tests pass.
- [x] Print preview contains the required report sections.

**Dependencies:** Tasks 10–12

**Files likely touched:**
- `pronto_report/templates/report/cnv-plots.html`
- `pronto_report/templates/report/sequencing-qc.html`
- `pronto_report/templates/report/tumour-board.html`
- `pronto_report/static/report.js`
- `pronto/tests/reporting/test_html_surfaces.py`

**Estimated scope:** Medium: 5 files

## Task 14: Self-contained export

**Description:** Bundle validated data, review state, styles, scripts, and approved assets into a deterministic offline HTML artifact.

**Acceptance criteria:**
- [x] Export makes no external network request.
- [x] Content is escaped and CSP-compatible.
- [x] Output includes schema/generator/source provenance.

**Verification:**
- [x] RED/GREEN bundling tests.
- [x] Repeat exports are byte-identical apart from declared timestamp fields.
- [x] Browser network log shows no external request.

**Dependencies:** Tasks 10–13

**Files likely touched:**
- `pronto_report/renderers/html.py`
- `pronto_report/cli.py`
- `pronto/tests/reporting/test_html_export.py`

**Estimated scope:** Medium: 3 files

## Task 15: Browser and parity quality gate

**Description:** Establish the automated and manual quality gate for the standalone renderer before Django work begins.

**Acceptance criteria:**
- [x] Critical keyboard, responsive, print, console, and accessibility flows are automated.
- [x] Key PPTX and HTML values are compared from the same fixture.
- [x] Known intentional presentation differences are documented.

**Verification:**
- [x] Full pytest suite passes.
- [x] Browser suite passes with zero console errors/warnings.
- [x] Existing OUS/HUS flow still succeeds.

**Dependencies:** Tasks 9–14

**Files likely touched:**
- `pronto/tests/reporting/browser/test_report.py`
- `pronto/tests/reporting/test_renderer_parity.py`
- `docs/report-parity.md`

**Estimated scope:** Medium: 3 files

## Checkpoint: Standalone HTML complete

- [x] All approved module success criteria are met.
- [ ] Definition of Done passes (venter på menneskelig gjennomgang før merge).
- [ ] Human approves the standalone renderer before `review-workflow` and Django specifications begin.

The owner has superseded that UI approval checkpoint: the contract and export
work remain useful, but the local `report.html` is now the required visual and
behavioral baseline. Do not mark the old standalone renderer approved or merge
PR #4 on the strength of Tasks 10–15 alone. Follow Tasks 16–29 below.

## Task 16: Reference inventory and source-gap map

**Description:** Inventory each visible control and state in the local reference, and map every displayed value to an approved `ReportData` field, a review field, or an explicit unavailable state.

**Acceptance criteria:**
- [x] A control matrix covers all five tabs, editing, filters, plots, notes, sign-off, and print.
- [x] A source-gap table identifies reference-only example values without copying them into the adapter.
- [ ] Masked local screenshots are captured for desktop and mobile comparison without committing patient-like output.

**Verification:** Review the matrix against `C:/Users/molpa/Documents/Inpred/report.html`; assert fixture field mapping with a focused pytest test; check the staged diff for generated reports.

**Dependencies:** Tasks 9–15. **Files likely touched:** `docs/report-reference-inventory.md`, `pronto/tests/reporting/test_reference_projection.py`. **Estimated scope:** Small: 2 files.

## Task 17: Versioned review notes and v1 migration

**Description:** Extend `ReviewState` to hold the reference's separate summary, biomarker context, and additional comments while preserving v1 decisions and text.

**Acceptance criteria:**
- [x] A new schema version validates distinct notes and the existing independent decision/classification fields.
- [x] v1 import retains its `reportNotes` as labeled imported text rather than guessing a destination.
- [x] Round-trip and malformed-input tests reject silent data loss.

**Verification:** RED/GREEN schema, migration, validation, and serialization tests; `python -m pytest -q pronto/tests/reporting`.

**Dependencies:** Task 16. **Files likely touched:** `pronto_report/schemas/review-state-v2.schema.json`, `pronto_report/models.py`, `pronto_report/validation.py`, `pronto_report/serialization.py`, `pronto/tests/reporting/test_review_migration.py`. **Estimated scope:** Medium: 5 files.

## Task 18: Validated UI projection

**Description:** Map immutable report facts, review fields, and stable variant/occurrence IDs into a frontend display model shaped for the original interaction flow.

**Acceptance criteria:**
- [x] All projected clinical facts carry source provenance or an unavailable marker.
- [x] Duplicate occurrences remain visible while shared decisions use stable `variantId`.
- [x] Corrections remain separate from source facts and require reason/author/time at save.

**Verification:** Fixture-based projection tests including missing fields, duplicate TERT occurrences, and corrections.

**Dependencies:** Tasks 16–17. **Files likely touched:** `pronto_report/renderers/projection.py`, `pronto/tests/reporting/test_reference_projection.py`, `docs/report-reference-inventory.md`. **Estimated scope:** Medium: 3 files.

## Task 19: Reference shell and visual tokens

**Description:** Replace PR #4's simplified shell with maintainable templates and CSS matching the reference top bar, tabs, spacing, palette, density, KPI cards, and patient strip.

**Acceptance criteria:**
- [x] Five familiar tabs and header controls appear in the original hierarchy.
- [ ] Desktop/mobile masked comparisons show no unexplained layout drift.
- [x] Keyboard tab navigation and focus visibility meet the existing accessibility bar.

**Verification:** Browser screenshots at 375, 768, 1024, and 1440 px; tab/console/accessibility checks; owner-visible comparison.

**Dependencies:** Task 18. **Files likely touched:** `pronto_report/templates/report/base.html`, `pronto_report/static/report.css`, `pronto_report/renderers/html.py`, `pronto/tests/reporting/browser/test_report.py`. **Estimated scope:** Medium: 4 files.

## Task 20: Key findings and editable TMB gauge

**Description:** Restore original KPI, patient/context, and gauge interactions using a page-memory working copy, not browser storage or network writes.

**Acceptance criteria:**
- [x] KPI/patient edits and pointer/keyboard gauge changes update the view and dirty indicator only.
- [ ] Source-derived changes are distinguishable from immutable `ReportData` and prompt for a correction reason at save.
- [x] Missing fixture facts remain labeled unavailable.

**Verification:** Browser tests assert live interaction, zero write requests before **Lagre**, keyboard gauge access, and no console errors.

**Dependencies:** Task 19. **Files likely touched:** `pronto_report/templates/report/key-findings.html`, `pronto_report/static/report.js`, `pronto_report/static/report.css`, `pronto/tests/reporting/browser/test_key_findings.py`. **Estimated scope:** Medium: 4 files.

## Task 21: Variant review interaction parity

**Description:** Restore the reference's chips, search, sort, per-variant judgements/comments, progress, and confirmed bulk include/exclude.

**Acceptance criteria:**
- [x] Decision and clinical classification remain independent, including duplicate occurrences.
- [x] Filters and sorting never change the underlying occurrence/review IDs.
- [x] Bulk actions affect only eligible unreviewed variants and require confirmation.

**Verification:** Focused browser tests for search, chips, sorting, duplicate TERT rows, progress, bulk confirmation, and dirty state.

**Dependencies:** Task 20. **Files likely touched:** `pronto_report/templates/report/variant-review.html`, `pronto_report/static/report.js`, `pronto_report/static/report.css`, `pronto/tests/reporting/browser/test_variant_workflow.py`. **Estimated scope:** Medium: 4 files.

## Task 22: Plots, notes, sign-off, and print parity

**Description:** Restore the original CNV/QC controls, enlargement, three note fields, sign-off surface, and generated MDT print layout.

**Acceptance criteria:**
- [x] Declared, hash-verified plots switch and enlarge with focus return.
- [ ] Notes/sign-off edit the page working copy; print includes only included reviewed findings.
- [x] Missing QC values are explicit and do not borrow demo thresholds or categories.

Three v2 notes and live MDT print are implemented. Sign-off stays read-only until authenticated save/finalization in Tasks 26–28; the draft print is explicitly labeled unsigned.

**Verification:** Renderer and browser tests for plots, notes, focus, print-PDF contents, and console/network behavior.

**Dependencies:** Tasks 17 and 21. **Files likely touched:** `pronto_report/templates/report/cnv-plots.html`, `pronto_report/templates/report/sequencing-qc.html`, `pronto_report/templates/report/tumour-board.html`, `pronto_report/static/report.js`, `pronto/tests/reporting/browser/test_plots_and_print.py`. **Estimated scope:** Medium: 5 files.

## Task 23: Reference-style offline snapshot

**Description:** Reuse the new UI projection for a self-contained, read-only export of a saved review revision.

**Acceptance criteria:**
- [x] Export keeps reference appearance but has no editable or server-save controls.
- [x] It embeds approved assets, provenance, status, and supplied review revision without external requests.
- [x] Same validated inputs generate byte-identical output.

`render-html` now creates the read-only snapshot from validated `ReportData` and an optional supplied `ReviewState`. It does not itself verify database persistence; that boundary belongs to Tasks 24–28.

**Verification:** Determinism/escaping/CSP tests and a browser network log; full reporting and legacy PPTX tests.

**Dependencies:** Tasks 18–22. **Files likely touched:** `pronto_report/renderers/html.py`, `pronto_report/cli.py`, `pronto/tests/reporting/test_html_export.py`, `pronto/tests/reporting/browser/test_report.py`. **Estimated scope:** Medium: 4 files.

## Checkpoint: Visual and interaction parity

- [ ] All Task 16–23 acceptance criteria and tests pass.
- [ ] Molecular-biologist review confirms that layout and interactions match the reference apart from documented safety changes and unavailable source data.
- [ ] PR #4 remains unmerged if any clinically important behavior is missing.

## Task 24: Review commands and audit contract

**Description:** Define framework-neutral save/finalize commands with versioned request/response shapes, authorization context, revision checks, and structured errors.

**Acceptance criteria:**
- [x] Save accepts a full validated draft and base revision; stale revisions produce conflict without mutation.
- [x] Finalize accepts only a saved, clean latest revision and locks further writes.
- [x] Audit records identify actor, action, revision, and timestamp in the same logical operation.

Framework-neutral service and fake-repository tests are in place. Database
atomicity, CSRF, and HTTP authorization are implemented in Tasks 25–28.

**Verification:** Service tests with a fake repository for success, 409-equivalent conflicts, validation errors, repeated requests, and FINAL lock.

**Dependencies:** Tasks 17 and 23. **Files likely touched:** `pronto_report/review/service.py`, `pronto_report/review/contracts.py`, `pronto_report/review/repository.py`, `pronto/tests/reporting/test_review_service.py`. **Estimated scope:** Medium: 4 files.

## Task 25: Authenticated Django read slice

**Description:** Add a minimal Django project that serves one approved report and its latest saved review through the reference-style UI, without a write path yet.

**Acceptance criteria:**
- [ ] Unauthenticated users and users without report access cannot retrieve report, review, or assets.
- [ ] An authorized user sees the validated fixture in the familiar UI.
- [ ] Django delegates projection/rendering to `pronto_report` rather than duplicating clinical calculations.

**Verification:** Django request tests for authentication, report-level authorization, fixture rendering, and asset access; existing tests still pass.

**Dependencies:** Task 24. **Files likely touched:** `pronto_web/settings.py`, `pronto_web/urls.py`, `pronto_web/reports/views.py`, `pronto_web/reports/models.py`, `pronto/tests/reporting/test_django_read.py`. **Estimated scope:** Medium: 5 files.

## Task 26: Atomic draft-save endpoint

**Description:** Persist revisions and audit rows in one database transaction when an authorized user presses **Lagre**.

**Acceptance criteria:**
- [ ] CSRF-protected save checks report access and the submitted base revision atomically.
- [ ] One successful request creates one new revision and audit event; stale request returns HTTP 409 with the current revision.
- [ ] Invalid corrections, mismatched report IDs, and FINAL writes make no database change.

**Verification:** Django transaction/request tests, including two clients saving from one base revision; inspect migration behavior.

**Dependencies:** Task 25. **Files likely touched:** `pronto_web/reports/views.py`, `pronto_web/reports/models.py`, `pronto_web/reports/migrations/0001_initial.py`, `pronto_report/review/service.py`, `pronto/tests/reporting/test_django_save.py`. **Estimated scope:** Medium: 5 files.

## Task 27: Explicit frontend save and conflict states

**Description:** Connect the original **Lagre** button to the save endpoint and accurately represent dirty, saving, saved, failure, and conflict states.

**Acceptance criteria:**
- [ ] Typing and local interaction send no write; clicking **Lagre** sends exactly one write with base revision.
- [ ] Success alone clears dirty state and updates revision; network/validation errors preserve unsaved edits.
- [ ] Conflict shows current revision and safe reload/local-draft-export choices without silent overwrite.

**Verification:** Browser tests with successful, failed, and 409 responses; leaving a dirty page warns; no patient data enters `localStorage`.

**Dependencies:** Task 26. **Files likely touched:** `pronto_report/static/report.js`, `pronto_report/templates/report/base.html`, `pronto_report/static/report.css`, `pronto/tests/reporting/browser/test_save_flow.py`. **Estimated scope:** Medium: 4 files.

## Task 28: Confirmed finalization and lock

**Description:** Replace the reference's draft/final toggle with a confirmed server action against the latest saved revision; the same authorized biologist may perform it.

**Acceptance criteria:**
- [ ] Unsaved edits disable finalization and explain why.
- [ ] Success records actor/time, makes UI and service read-only, and retains the final saved snapshot.
- [ ] Conflict or failure keeps the prior draft state; a second reviewer is not required.

**Verification:** Django and browser tests for confirmation, same-user finalization, stale revision, failed request, and post-final write rejection.

**Dependencies:** Tasks 26–27. **Files likely touched:** `pronto_web/reports/views.py`, `pronto_report/review/service.py`, `pronto_report/static/report.js`, `pronto/tests/reporting/test_django_finalization.py`, `pronto/tests/reporting/browser/test_finalization.py`. **Estimated scope:** Medium: 5 files.

## Task 29: End-to-end quality and review gate

**Description:** Verify the full reference UI plus Django flow with approved fixtures and document only intentional deviations from the original.

**Acceptance criteria:**
- [ ] Source/provenance, migration, duplicate variants, audit, concurrency, authorization, CSRF, print, and offline export pass regression tests.
- [ ] Masked desktop/mobile comparisons and clinical-user review are recorded without publishing patient-like artifacts.
- [ ] Existing OUS/HUS and PPTX behavior remains green; PR #4 is updated for human review, not auto-merged.

**Verification:** `python -m pytest -q`, browser suite, Django checks/migrations, existing PRONTO tests, staged privacy review, and CI.

**Dependencies:** Tasks 16–28. **Files likely touched:** `pronto/tests/reporting/browser/test_report.py`, `pronto/tests/reporting/test_renderer_parity.py`, `docs/report-parity.md`, `tasks/plan.md`, `tasks/todo.md`. **Estimated scope:** Medium: 5 files.

## Checkpoint: Database-backed review

- [ ] All Task 24–29 criteria and tests pass.
- [ ] A biologist verifies **Lagre**, conflict warning, and same-user FINAL against the reference-style page.
- [ ] Production authentication, retention, backups, and deployment receive a separate operational approval before real patient use.
