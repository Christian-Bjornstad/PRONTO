# Implementation Plan: PRONTO reporting foundation

## Overview

Build a clean reporting subsystem beside the existing PRONTO implementation. The local `report.html` is the visual and workflow reference, while a new versioned `ReportData`/`ReviewState` contract becomes the source for PPTX, HTML, and later Django integration. Existing report generation remains available and unchanged during validation.

This plan covers the approved `repo-baseline`, `report-data-contract`, and `html-renderer` modules. `review-workflow` persistence and the Django application receive their own specifications and follow-up plan after the contract and standalone renderer are proven.

## Architecture Decisions

- Keep the existing `Script/PRONTO.py` path operational; introduce a new `pronto_report` package additively.
- Treat `ReportData` as immutable source/calculated facts and `ReviewState` as human decisions, notes, corrections, and finalization state.
- Separate reporting decision from clinical classification.
- Develop HTML as templates, CSS, and JavaScript; bundle them only when producing a self-contained export.
- Preserve the five-surface workflow and InPreD visual language from the local reference report.
- Use public/non-sensitive fixtures only, as approved by the repository owner.
- Keep Django outside this first implementation plan so it consumes a proven contract instead of defining one accidentally.

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
- [ ] Task 13: Render CNV plots, sequencing QC, and the tumour-board surface.
- [ ] Task 14: Produce a deterministic self-contained HTML export.
- [ ] Task 15: Add browser, accessibility, responsive, print, and console verification.

### Checkpoint: Standalone HTML

- [ ] The approved fixture renders all five surfaces from the contract.
- [ ] The visual hierarchy is recognizably based on the local reference report.
- [ ] No whole-page horizontal overflow at 375, 768, 1024, or 1440 px.
- [ ] Keyboard tabs, filtering, sorting, plots, focus return, and print mode work.
- [ ] FINAL output is read-only and carries provenance.
- [ ] Existing PPTX output remains available.

### Phase 4: Next approved planning gate

- [ ] Specify `review-workflow` persistence, audit, locking, and finalization roles.
- [ ] Specify the first Django vertical slice against the proven contract.

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
| HTML drifts from PPTX | High | Add parity assertions before calling the renderer complete |
| Browser edits overwrite source facts | High | Keep corrections in `ReviewState` with reason and authorship |
| Public repository receives inappropriate data | High | Track only owner-approved fixtures; review staged changes before every commit |
| Responsive work harms dense desktop workflow | Medium | Keep desktop table dense; scope horizontal scrolling to the table on narrow widths |
| Django duplicates report logic | Medium | Delay Django until contract and renderer services are proven |

## Open Questions Deferred to Later Modules

- Production authentication source and role mapping.
- Authoritative production database and hosting environment.
- Retention, deletion, backup, and audit requirements for sensitive deployments.
- Whether production finalization requires an independent reviewer and finalizer.
- Integration with IGV, clinical databases, SharePoint, DIPS, or other external systems.

## Definition of Done

Each task must meet its acceptance criteria and verification steps in `tasks/todo.md`, preserve existing tests and outputs, contain no unapproved data or secrets, update relevant documentation, and receive human review before merge.
