# Report workspace reset, reference fidelity, and HTML export

Date: 2026-09-29

Status: design agreed in chat; written specification awaiting owner review

Reference: `C:/Users/molpa/Documents/Inpred/report.html`

Builds on: `2026-09-23-report-html-fidelity-and-review-persistence-design.md`

## Intent and success

The review workspace should retain the familiar density and interactions of
the local reference while remaining backed by validated PRONTO data and an
audited database review. The owner requested a true reset to the report's
starting state, less intrusive attribution and correction copy, reference-like
TMB colouring, correctly aligned Variant review headings, paired CNV plots,
and a compact downloadable HTML report instead of the current print-first
workflow. The HTML report is a deliverable, not a copy of the editing page.

Success is a molecular biologist being able to review and save, reset a DRAFT
to a clean starting state, then download a standalone, readable HTML file for
the exact saved revision with Key findings, selected variants, and conclusion
notes. Source facts, review history, and provenance must remain distinct.

## Chosen approach and alternatives

Generate the HTML file on the server from validated `ReportData` and the
latest saved `ReviewState`, after a revision-checked, initials-attributed
export request. Do not persist rendered HTML or PDF bytes in the database.

Copying the live DOM was rejected because it could include unsaved or hidden
workspace state. Persisting a generated HTML blob was rejected because it
would duplicate the source of truth and could become stale. The existing
browser print flow records only a print request; it does not currently store
a PDF. This change replaces its primary UI action with HTML download rather
than deleting historical print audit rows or source CNV PDF attachments.

## Workspace behaviour

### Reset

- Show **Reset** only for editable DRAFT reports. FINAL remains locked.
- Before reset, show a confirmation that names the current report and states
  that saved review choices, notes, QC assessment, and source-value corrections
  will return to their initial values. Ask for initials as for saving.
- A confirmed reset creates a new `ReviewRevision` with a blank review state:
  no variant decisions or comments, `NOT_REVIEWED` run QC, empty note fields,
  and no value corrections. The original immutable `ReportData` and its
  attachments are unchanged. Earlier revisions and audit events remain.
- Use the same report authorization, CSRF, validation, and optimistic revision
  check as ordinary save. Record a distinct `RESET_DRAFT` audit action with
  the actor and declared initials in the same transaction as the revision.
  A stale base revision returns a conflict; no reset is applied. A failure
  preserves the open working copy. The button is disabled during save, reset,
  or finalization to prevent double submission.
- Successful reset refreshes the workspace from the returned revision and
  clears the dirty state. No reset occurs merely by reloading or opening the
  page. Demo data may be reset, but no automatic reseeding is introduced.

### Visual fidelity and copy

- Remove the visible text `(self-reported initials)` throughout the workspace
  and export, while retaining `SELF_REPORTED` in attribution records. Display
  the initials plainly with the existing saved/finalized status and revision.
- Reproduce the reference TMB gauge as a 0–30 mut/Mb, green/yellow/red track
  with boundaries at 5 and 20, ticks, and a visible draggable/keyboard
  cursor. Values `<=5` fall in green, `>5` through `20` in yellow, and `>20`
  in red. These are reference-display bands, not new pipeline-derived
  clinical classifications or database fields. Preserve the source fact and
  the existing correction reason requirement.
- Reduce a saved correction's default display to the effective value and a
  compact **Corrected** indicator. An accessible disclosure exposes the
  source value, reason, recorded initials/actor, and timestamp. All audit
  information remains available without occupying the whole KPI card.
- Measure the Variant review table at 320, 768, 1024, and 1440 px. Correct
  any heading-to-cell misalignment without changing the approved data order
  or the one-row-per-occurrence identity model. Keep the compact primary
  columns and Inc/Exc/Path/Uns controls, with longer facts and full controls
  under Details. Desktop should show the primary columns without horizontal
  scrolling; small screens may scroll the table without widening the page.
- On the CNV tab, show the available A1 and A2 plots vertically in one group,
  A1 above A2. Pair the other existing source panels as B2/B3, C1/C2,
  C3/C4, with C6 alone. Never invent B1 or missing panels. Keep each figure's
  own caption and enlarge action. Stack naturally on narrow screens.

## Standalone HTML report

- Replace the workspace's primary **Print MDT report** action with **Download
  report HTML**. The button is available for a saved revision; it refuses a
  dirty working copy and asks the user to save first. A FINAL report may also
  be exported. The export requires declared initials, but not a second
  biologist or a login screen in the demo access mode.
- The server checks report access and active actor, CSRF, the requested
  revision against the latest saved revision, initials format, and a unique
  request ID. On success it records `HTML_DOWNLOAD_REQUESTED` with actor,
  initials, revision, and timestamp.
  The name must not claim that the browser finished saving the file. Repeat
  requests with the same ID are idempotent; conflicting reuse is rejected.
  No HTML/PDF bytes are stored in the database.
- Render from the validated immutable report and that saved review snapshot.
  Include sample/report identification, Key findings (including saved
  corrections shown concisely), only unique variants whose reporting decision
  is `INCLUDE`, and the saved interpretation summary, biomarker/therapeutic
  context, and additional comments. Preserve source-backed AF to three
  decimal places and tumour depth. Keep unavailable OncoKB/biomarker facts
  explicitly unavailable rather than supplying demo clinical claims.
- The output is one UTF-8 `text/html` attachment with inline CSS and no
  JavaScript, remote fonts, URLs, IGV viewer, review controls, CNV/QC workspace
  plots, or data fetches. It must open locally and print cleanly. Escape all
  source/reviewer text; use a restrictive CSP and `nosniff` header. A visible
  report revision and initials provide attribution, while detailed correction
  provenance remains readable in a compact notes area.
- If authorization, validation, audit persistence, rendering, or revision
  comparison fails, return a clear error and do not send an HTML attachment.
  The user's open workspace and unsaved changes remain untouched.

## Boundaries and rollout

`ReportData` remains the source of immutable facts; `ReviewState` owns human
choices and corrections. The review service owns reset semantics and audit,
not the browser. A dedicated export renderer owns the reduced HTML document;
the five-tab workspace renderer continues to own editing. The Django adapter
authorizes and loads the saved snapshot, records the export request, and
returns the attachment. Existing JSON recovery/download and historical print
audits remain available until separately retired, but the print button is no
longer the primary report-delivery action.

Implement in reviewable slices: visual copy/gauge/table/CNV changes, reset
command and tests, standalone renderer, then audited export endpoint and UI.
Keep the existing demo database untouched during implementation. A fresh
isolated demo can verify reset and export without overwriting the user's open
`demo-fidelity-20260929` review.

## Acceptance checks

1. In a DRAFT, make and save a variant decision, QC note, report note, and
   TMB correction; Reset with initials creates exactly one new blank revision
   and distinct audit event. Original report facts and prior revisions remain.
2. Cancel Reset, fail validation, or force a revision conflict: the database
   is unchanged and the working copy is retained. FINAL has no reset action.
3. The reference TMB colour bands, ticks, and cursor are visible and usable
   by pointer and keyboard; correction provenance is accessible without
   expanding the KPI by default.
4. Variant review headings align with their corresponding values at the four
   target widths, including source depth and placeholders. Search, sorting,
   duplicate IDs, quick choices, Details, and database save still work.
5. A1 and A2 appear in that vertical order on one CNV view; all nine approved
   plots remain reachable and enlarge correctly.
6. HTML export includes only saved included variants and saved notes, opens
   offline, and has no scripts or external requests. Unsaved changes or a
   stale revision block download. Repeat request IDs do not duplicate audit.
7. Existing save/finalize, review migration, alignment/IGV, and read-only
   snapshot tests remain green. The full test suite and a real browser check
   pass before updating the PR.
