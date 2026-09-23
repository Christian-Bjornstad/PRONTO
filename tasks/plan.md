# Implementation Plan: PRONTO reporting foundation

## Overview

Build a clean reporting subsystem beside the existing PRONTO implementation. The local `report.html` is the visual and workflow reference, while a new versioned `ReportData`/`ReviewState` contract becomes the source for PPTX, HTML, and later Django integration. Existing report generation remains available and unchanged during validation.

Tasks 1–15 record the completed reporting foundation. The owner subsequently clarified that the local `report.html` must be the UI and interaction reference, rather than merely inspiration. Tasks 16–29 implement the approved [fidelity and persistence design](../docs/superpowers/specs/2026-09-23-report-html-fidelity-and-review-persistence-design.md) in two checkpoints: faithful UI, then Django-backed review. PR #4 remains unmerged until these checkpoints are reviewed.

## Architecture Decisions

- Keep the existing `Script/PRONTO.py` path operational; introduce a new `pronto_report` package additively.
- Treat `ReportData` as immutable source/calculated facts and `ReviewState` as human decisions, notes, corrections, and finalization state.
- Separate reporting decision from clinical classification.
- Develop HTML as templates, CSS, and JavaScript; bundle them only when producing a self-contained export.
- Preserve the five-surface workflow and InPreD visual language from the local reference report.
- Use public/non-sensitive fixtures only, as approved by the repository owner.
- Keep Django outside Tasks 1–15; the newly approved extension adds it only after contract and UI-projection work.
- Preserve source facts in `ReportData`; put human decisions, distinct notes, and reasoned corrections in a versioned `ReviewState`.
- Treat the local `report.html` as a behavioral and visual baseline. Keep editing local to the page until **Lagre** succeeds. Do not make `localStorage` authoritative.
- Finalize only the latest saved revision, with confirmation and a read-only FINAL state. The same authenticated biologist may finalize.

## Dependency Graph

```text
environment + privacy baseline
             |
      schema contracts
             |
  models + validation + identity
             |
 fixture adapter + deterministic JSON
             |
     HTML renderer foundation
       /                 \
key/variant UI        plots/QC/MDT UI
       \                 /
       browser and parity verification
```

## Task List

### Phase 1: Reproducible baseline

- [x] Task 1: Document and automate the isolated Python development setup.
- [x] Task 2: Make existing tests platform-independent and establish a green unit-test baseline.
- [x] Task 3: Add pull-request CI without publishing Docker images.
- [x] Task 4: Record the approved fixture/privacy policy and local artifact boundaries.

### Checkpoint: Baseline

- [x] Clean environment installs successfully.
- [x] Existing unit tests pass on Windows and CI Linux.
- [x] Existing OUS/HUS behavior remains unchanged.
- [x] No generated report or unapproved artifact is tracked.

### Phase 2: Report data contract

- [x] Task 5: Add failing schema tests and v1 JSON Schema documents.
- [x] Task 6: Implement typed models and structured validation errors.
- [x] Task 7: Implement stable report/variant identity and duplicate diagnostics.
- [x] Task 8: Implement deterministic JSON serialization and round-trip tests.
- [x] Task 9: Adapt one approved public fixture into valid `ReportData`.

### Checkpoint: Contract

- [x] Approved fixture validates and round-trips deterministically.
- [x] Invalid, oversized, mismatched, and duplicate-ID cases produce structured issues.
- [x] Review decision and clinical classification vary independently.
- [x] No hard-coded clinical value is introduced in the new package.

### Phase 3: Clean HTML renderer

- [x] Task 10: Add the renderer shell, design tokens, and five accessible tab panels.
- [x] Task 11: Render key findings and the variant review table from `ReportData`.
- [x] Task 12: Add review-state presentation with separate decision and classification controls.
- [x] Task 13: Render CNV plots, sequencing QC, and the tumour-board surface.
- [x] Task 14: Produce a deterministic self-contained HTML export.
- [x] Task 15: Add browser, accessibility, responsive, print, and console verification.

### Checkpoint: Standalone HTML

- [x] The approved fixture renders all five surfaces from the contract.
- [x] The visual hierarchy is recognizably based on the local reference report.
- [x] No whole-page horizontal overflow at 375, 768, 1024, or 1440 px.
- [x] Keyboard tabs, filtering, sorting, plots, focus return, and print mode work.
- [x] FINAL output is read-only and carries provenance.
- [x] Existing PPTX output remains available.

### Phase 4: Next approved planning gate

- [x] Specify `review-workflow` persistence, audit, locking, and finalization roles.
- [x] Specify the first Django vertical slice against the proven contract.

### Phase 5: Reference-faithful report UI

- [ ] Task 16: Inventory original controls, screen states, and source-field gaps.
- [x] Task 17: Extend review contract for distinct notes and migrate v1 without data loss.
- [ ] Task 18: Project validated report and review snapshots into the reference UI model.
- [ ] Task 19: Rebuild the original top bar, tabs, cards, patient strip, and visual tokens.
- [ ] Task 20: Restore key-findings editing and the accessible TMB gauge.
- [ ] Task 21: Restore variant filters, sorting, judgements, progress, and bulk actions.
- [ ] Task 22: Restore CNV/QC, notes, sign-off, lightbox, and print/MDT output.
- [ ] Task 23: Align offline export with the reference UI as a saved, read-only snapshot.

### Checkpoint: Visual and interaction parity

- [ ] All five surfaces match the local reference in structure and recognizable appearance at desktop and mobile widths.
- [ ] Browser tests cover every original control; keyboard and screen-reader semantics improve where needed.
- [ ] Unavailable source facts remain explicitly unavailable; the reference's example values are not silently copied.
- [ ] Masked side-by-side screenshots are reviewed with a molecular biologist.
- [ ] Legacy PPTX behavior and approved-fixture tests remain green.

### Phase 6: Explicit database save and finalization

- [ ] Task 24: Specify and test review-service commands, revision errors, and audit records.
- [ ] Task 25: Add a minimal authenticated Django report retrieval slice and access rules.
- [ ] Task 26: Persist draft revisions atomically when **Lagre** is pressed.
- [ ] Task 27: Connect frontend dirty, save, failure, and conflict states to the draft endpoint.
- [ ] Task 28: Finalize the latest saved revision and enforce the read-only lock.
- [ ] Task 29: Verify end-to-end concurrency, migration, security, print, and regression behavior.

### Checkpoint: Database-backed review

- [ ] One approved fixture loads through Django and retains source provenance.
- [ ] Typing sends no write; **Lagre** sends one validated write and updates the visible revision only after success.
- [ ] Concurrent saves return 409 and preserve the current user's unsaved work.
- [ ] The same authorized biologist can confirm FINAL; FINAL cannot be edited.
- [ ] All automated tests and clinical-user review pass before PR #4 is considered for merge.

## Verification Strategy

- Every behavior change follows RED → GREEN → REFACTOR with a focused pytest or browser test.
- Existing PRONTO tests run after each integration-affecting increment.
- Browser-facing increments are verified in a real browser with screenshots, accessibility structure, and console inspection.
- Generated fixture outputs are compared semantically; large opaque snapshots are avoided.
- Every completed task is an atomic commit and leaves the branch runnable.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Existing script mixes calculations and rendering | High | Add contract extraction beside existing behavior; do not rewrite the script wholesale |
| Clinical meaning is lost during field mapping | High | Preserve source values/provenance and require explicit validation fixtures |
| Existing test data contains ambiguous identifiers | High | Use stable IDs with fallback warnings and duplicate diagnostics |
| HTML drifts from PPTX or the liked local `report.html` | High | Keep data-parity assertions and add reference interaction inventory and masked visual comparison |
| Browser edits overwrite source facts | High | Keep corrections in `ReviewState` with reason and authorship |
| Public repository receives inappropriate data | High | Track only owner-approved fixtures; review staged changes before every commit |
| Responsive work harms dense desktop workflow | Medium | Keep desktop table dense; scope horizontal scrolling to the table on narrow widths |
| Django duplicates report logic | Medium | Put review commands in a framework-neutral service; Django is an authenticated persistence adapter |
| Concurrent reviewers overwrite each other | High | Atomic base-revision comparison, 409 response, preserve unsaved page state |
| Local reference includes untraceable clinical examples | High | Trace each display field to an approved source or label unavailable; never promote demo values to facts |

## Open Questions Deferred to Later Modules

- Production authentication source and role mapping.
- Authoritative production database and hosting environment.
- Retention, deletion, backup, and audit requirements for sensitive deployments.
- A second finalizer is not required in this first slice; production policy can later add one without rewriting saved revisions.
- Integration with IGV, clinical databases, SharePoint, DIPS, or other external systems.

## Definition of Done

Each task must meet its acceptance criteria and verification steps in `tasks/todo.md`, preserve existing tests and outputs, contain no unapproved data or secrets, update relevant documentation, and receive human review before merge.
