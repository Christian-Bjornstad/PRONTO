# Report.html fidelity and database-backed review

Date: 2026-09-23

Status: proposed for owner review

Reference: local `C:/Users/molpa/Documents/Inpred/report.html`

## Intent and success

The molecular biologists liked the local report's specific visual design and
interactive workflow. That file, not the new renderer in PR #4, is the product
reference. The delivered application should look and behave like it while
reading validated PRONTO data and saving human review to a database. Editing is
local to the open page until the user presses **Lagre**. The same biologist may
finalize the report after saving.

Success requires clinical-user acceptance of the five familiar surfaces and
their interactions, not merely the presence of the same facts in a different
layout. PR #4 stays unmerged until this parity and its persistence behavior are
reviewed. Existing PPTX generation remains available.

## Options considered

1. **Use the original page as the UI baseline (selected).** Extract its
   markup, CSS, and interaction code into maintained assets. Feed it validated
   data and replace browser-only persistence with explicit server save. This
   gives the strongest fidelity while allowing tests and database integration.
2. Restyle the PR #4 renderer. It retains the current contract work but would
   require re-creating most of the interaction model and risks subtle drift.
3. Embed the original file in an iframe. This is quick to demo but leaves two
   state systems and makes secure persistence, accessibility, and audit awkward.

The selected approach reuses the existing contract/asset validation rather
than copying the 2.2 MB monolithic reference file into production unchanged.

## Scope and intentional differences

Retain the original five-tab structure, top bar, palette, density, typography,
KPI cards, editable TMB gauge, patient strip, key-variant table, variant search,
filter chips, sort, judgement controls, progress indicator, quick
include/exclude, CNV selector and enlargement, QC tiles and plot, notes,
sign-off area, and generated print/MDT view. Keep the current control labels
unless the owner requests a separate localization change. Use responsive and
keyboard-accessible equivalents where the original has gaps.

Two owner-approved behavior changes are intentional:

- `localStorage` is not the authoritative store. Changes remain in page memory
  and are marked dirty until **Lagre** succeeds against the database. No
  background or debounce save is allowed.
- **Mark final** becomes a confirmed server operation on the latest saved
  revision. The same authenticated biologist may perform it. A FINAL review is
  read-only; reverting it is not a one-click UI toggle.

The original's export/import JSON may remain as a separate, clearly labeled
backup/transfer action, but it must not be confused with database **Lagre**.
No production medical data or generated patient report is committed to this
public repository.

## Components and boundaries

| Component | Responsibility | Depends on |
| --- | --- | --- |
| PRONTO adapter and `ReportData` | Immutable source/calculated facts, stable IDs, provenance, diagnostics, declared assets | Existing PRONTO output |
| UI projection | Map validated facts, review values, and attachment URLs into the original page's display model; never invent missing clinical values | `ReportData`, `ReviewState` |
| Original-style frontend | Render all five surfaces; hold unsaved edits in memory; show dirty/save/error/conflict/final states; generate print view | UI projection and review commands |
| Review service | Validate full draft, authorize actor, enforce revision compare-and-swap, record audit event, finalize atomically | Versioned review contract and repository |
| Django adapter | Authenticated report retrieval, CSRF-protected save/finalize endpoints, asset delivery, database transaction boundary | Review service and database |
| Offline exporter | Produce a self-contained read-only artifact from a saved snapshot | UI projection and approved assets |

The core review service is framework-neutral so Django does not own PRONTO
calculations or clinical rules. Browser code cannot submit arbitrary
`ReportData` replacements.

## Data model and provenance

`ReportData` continues to represent source facts and is never overwritten by
page edits. `ReviewState` contains reporting decisions, clinical
classification, IGV assessment, comments, notes, and corrections. The current
v1 contract has a single `reportNotes` field, while the reference has separate
summary, biomarker/therapeutic context, and additional-comment fields. A
versioned review-contract extension is therefore required before database
save. Existing v1 JSON must be imported with an explicit migration that
preserves its text and decisions. The old undifferentiated `reportNotes` text
appears as a labeled, read-only "Imported notes" field until a reviewer moves
it into a specific new note field; unknown values must not be silently dropped.

The reference also displays patient/context, LocalApp TMB, categories, QC
tiles, and other values absent from the approved `ReportData` mapping. Each
field must be traced to an approved source and added to a validated contract,
or displayed as unavailable in the original layout. Values in the reference
file alone are not evidence that the adapter may hard-code them. Source-derived
value changes are stored as corrections, with original value, new value,
author, time, and a reason collected in a save dialog when a source-derived
value changed. This audit prompt is an additional safety interaction, not a
visual redesign. Variant decisions use stable contract IDs; duplicate source
occurrences remain visible and share the
appropriate review decision without losing their occurrence IDs.

## Save, conflict, and finalization flows

1. An authenticated user opens a report. The server supplies one validated
   `ReportData` snapshot and the latest saved `ReviewState` revision.
2. Edits update the page's working copy and the dirty indicator only. Leaving
   or reloading a dirty page warns the user. A failed request never clears the
   working copy.
3. **Lagre** submits the full proposed review state with the base revision,
   report ID, and CSRF protection. The service validates it and performs an
   atomic revision check and write. Success returns the new revision and an
   audit entry; only then does the page show saved/clean.
4. If another user saved first, the service returns a conflict (HTTP 409) and
   the page keeps the unsaved work. It shows the current saved revision and
   offers reload or a local draft export; it never silently merges or
   overwrites. Validation and authorization failures are displayed separately.
5. **Mark final** is enabled only when there are no unsaved edits. After an
   explicit confirmation, the service verifies the same latest revision,
   records finalizer/time, and locks subsequent edits. It does not require a
   second person. A conflict or failed finalization leaves the page in draft.

The persistence API is deliberately narrow: retrieve a report/review snapshot,
save a draft revision, and finalize a saved revision. Request/response schemas
and error codes are versioned with the review contract. Database rows for
saved revisions and audit events are written in the same transaction. Access
requires authentication and report-level authorization; no patient data is
cached in `localStorage`.

## Validation and acceptance

- Build a reference interaction inventory and fixtures for every visible
  control before replacing the current renderer. Verify the five tabs, KPI
  edit/gauge, filters, sorting, bulk actions, duplicate variants, plots and
  lightbox, notes, sign-off, and print output in a real browser.
- Compare masked screenshots of the local reference and the rebuilt UI at
  desktop and mobile widths. Review text/content differences caused by
  validated source gaps separately from visual/layout differences. Clinical
  users approve the result; automated pixel comparison alone is insufficient.
- Test that typing does not make a network write, **Lagre** makes exactly one
  authorized write, success clears dirty state, failure preserves edits,
  concurrent save returns conflict, and FINAL cannot be edited.
- Test migration from v1 review JSON, source provenance, HTML escaping/CSP,
  print/MDT selection of included variants, and unchanged PPTX behavior.
- Use approved non-sensitive fixtures in repository tests. Production-like
  access, audit, backups, retention, and deployment need separate operational
  review before real patient use.

## Delivery boundaries

First establish a parity-capable renderer and projection against approved
fixtures. Then add the Django database vertical slice for retrieval, **Lagre**,
conflict, and finalization. Keep the offline export as a saved, read-only
snapshot. These are separate testable increments under one design; neither a
fresh visual redesign nor a full hospital-system integration is in scope.
