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
- [ ] Output is stable for the same logical model.
- [ ] Round-trip preserves values, IDs, warnings, and provenance.
- [ ] Invalid input fails before an internal model is returned.

**Verification:**
- [ ] RED/GREEN serialization and round-trip tests.
- [ ] Two serializations of the same model are byte-identical.

**Dependencies:** Tasks 6–7

**Files likely touched:**
- `pronto_report/serialization.py`
- `pronto/tests/reporting/test_serialization.py`

**Estimated scope:** Small: 2 files

## Task 9: Approved fixture adapter

**Description:** Convert one approved existing OUS public fixture into the v1 contract without hard-coded clinical values.

**Acceptance criteria:**
- [ ] Source fields map with provenance and explicit missing-data warnings.
- [ ] The approved fixture validates and contains stable IDs.
- [ ] No value is invented when the source is absent.

**Verification:**
- [ ] RED/GREEN adapter tests against the approved fixture.
- [ ] Generated JSON validates and round-trips.
- [ ] Manual comparison with the local reference report's key values.

**Dependencies:** Tasks 5–8

**Files likely touched:**
- `pronto_report/adapters/pronto_output.py`
- `pronto_report/cli.py`
- `pronto/tests/reporting/test_pronto_output_adapter.py`
- `pronto/tests/reporting/fixtures/expected-report-data.json`

**Estimated scope:** Medium: 4 files

## Checkpoint: Contract

- [ ] Schema, model, identity, serialization, and adapter tests pass.
- [ ] Approved fixture validates and round-trips deterministically.
- [ ] Human reviews the contract example before renderer implementation.

## Task 10: Accessible renderer shell

**Description:** Create the modular HTML source, design tokens, and five accessible tab panels using the local report as the visual reference.

**Acceptance criteria:**
- [ ] All five panels render with semantic landmarks and correct tab relationships.
- [ ] Design tokens preserve the InPreD blue/neutral/status palette.
- [ ] No whole-page horizontal overflow at target widths.

**Verification:**
- [ ] RED/GREEN renderer structure tests.
- [ ] Browser screenshots at 375, 768, 1024, and 1440 px.
- [ ] Keyboard tab navigation and focus indicators work.

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
- [ ] No clinical value or threshold is hard-coded in the browser.
- [ ] Numeric values use declared display formatting.
- [ ] Search, filters, and sorting are accessible and deterministic.

**Verification:**
- [ ] Focused renderer tests for normal, missing, and empty data.
- [ ] Browser test for search and sorting.
- [ ] Visual comparison with the reference report.

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
- [ ] Decision and classification can vary independently.
- [ ] FINAL state disables editing and shows provenance/status clearly.
- [ ] Mismatched report state is rejected without an override prompt.

**Verification:**
- [ ] RED/GREEN state validation and rendering tests.
- [ ] Browser test covers edit, validation feedback, and FINAL lock.

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
- [ ] Plot switcher, captions, enlargement, and focus return work.
- [ ] QC cards include text status and declared thresholds.
- [ ] Tumour-board view shows only eligible reviewed findings and explicit sign-off state.

**Verification:**
- [ ] Renderer tests cover missing and present plots/QC.
- [ ] Browser keyboard and focus tests pass.
- [ ] Print preview contains the required report sections.

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
- [ ] Export makes no external network request.
- [ ] Content is escaped and CSP-compatible.
- [ ] Output includes schema/generator/source provenance.

**Verification:**
- [ ] RED/GREEN bundling tests.
- [ ] Repeat exports are byte-identical apart from declared timestamp fields.
- [ ] Browser network log shows no external request.

**Dependencies:** Tasks 10–13

**Files likely touched:**
- `pronto_report/renderers/html.py`
- `pronto_report/cli.py`
- `pronto/tests/reporting/test_html_export.py`

**Estimated scope:** Medium: 3 files

## Task 15: Browser and parity quality gate

**Description:** Establish the automated and manual quality gate for the standalone renderer before Django work begins.

**Acceptance criteria:**
- [ ] Critical keyboard, responsive, print, console, and accessibility flows are automated.
- [ ] Key PPTX and HTML values are compared from the same fixture.
- [ ] Known intentional presentation differences are documented.

**Verification:**
- [ ] Full pytest suite passes.
- [ ] Browser suite passes with zero console errors/warnings.
- [ ] Existing OUS/HUS flow still succeeds.

**Dependencies:** Tasks 9–14

**Files likely touched:**
- `pronto/tests/reporting/browser/test_report.py`
- `pronto/tests/reporting/test_renderer_parity.py`
- `docs/report-parity.md`

**Estimated scope:** Medium: 3 files

## Checkpoint: Standalone HTML complete

- [ ] All approved module success criteria are met.
- [ ] Definition of Done passes.
- [ ] Human approves the standalone renderer before `review-workflow` and Django specifications begin.
