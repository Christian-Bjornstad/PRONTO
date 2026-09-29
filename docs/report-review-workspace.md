# Review workspace increment — 2026-09-26

Approved workflow: inspect source information, explicitly select findings, then
view the selected findings in the tumour-board report. The original report.html
remains the visual reference; this increment is not a claim of full visual parity.

- Default navigation opens Variant review; explicit panel links still work.
- Per-variant selection uses existing reportingDecision and does not classify a
  variant. Deselecting returns it to UNREVIEWED; EXCLUDE remains available.
- AF is a fraction (0–1), displayed with exactly three decimal places using a
  decimal comma. Underlying precision and numeric sorting are unchanged.
- Tumour DNA depth is displayed from the existing depthTumourDna annotation.
- Expandable details expose the currently imported annotations, not every column
  that may exist in the source spreadsheet.
- QC status and comment use runQcAssessment and the existing explicit save,
  revision, and finalization flow. Source measurements remain unchanged.
- OncoKB and local biomarker matching currently have **display placeholders
  only**: “Ikke mottatt” and “Ikke krysssjekket”. No API request or matching is
  performed, and no negative finding is inferred. Pipeline field contracts and
  the versioned local list/match rules require a subsequent increment.

Verification covers browser selection, report output, exported QC state, exact
AF display with preserved source precision, and database persistence of QC and
selection without mutation of source ReportData.

## Compact reference-style workspace

The owner-approved density increment restores the reference's 14 px body and
12.5 px table text, tighter header/tab/table spacing and smaller section titles.
Touch-sized header/preview controls remain on narrow screens; the variant table
scrolls within its own region rather than widening the whole page. The sticky
tabs follow the measured header height when the desktop header wraps.

Occurrence ID, stable variant ID, source tier and imported annotations are
available under each row's **Detaljer** disclosure. They are not removed from
the underlying report. AF, tumour DNA depth, OncoKB/biomarker placeholders and
selection controls remain in the table. Tier remains searchable.

**Forhåndsvis rapport** opens the existing tumour-board panel and moves keyboard
focus to its tab. The count represents unique included variant IDs, not source
occurrences or only the filtered rows. The link works for saved/read-only
snapshots as well. Previewing neither saves, finalizes, logs a print request nor
asks for initials; those remain separate explicit actions. The preview control
is omitted from print layout.

Browser coverage exercises duplicate inclusion/deselection, filtered-out
findings, keyboard navigation, read-only preview, source details and layouts at
320, 768, 1024 and 1440 px. This increment is not full reference parity or
clinical-user acceptance.

## Recovery after an unsuccessful save

If saving fails, do not close the page before securing the working copy:

1. The page keeps the variant selection, QC assessment and QC comment marked
   unsaved. A failed request does not advance the visible base revision.
2. Use the offered local draft download to preserve those edits. This JSON is
   a working-copy backup, not confirmation of a database save or a final report.
3. For a network/server failure, retry once the service is available. If the
   first request actually committed but its response was lost, the retry can
   produce a revision conflict; compare against the saved revision.
4. For a conflict, secure the local copy before loading the latest saved
   revision. Reconcile the differences explicitly. There is no automatic merge
   or overwrite, and the download does not itself resolve the conflict.

The application's audited print action remains blocked while edits are unsaved.
This does not claim to prevent browser-menu printing or screenshots.

Regression coverage includes browser-level simulated HTTP 409, HTTP 503 and
network failures with initials, variant selection, QC assessment/comment,
schema-validated backup and blocked print requests. A separate Django test
uses two authorized users with distinct initials and conflicting content;
the stale request cannot replace the first saved revision, create a new audit
entry or mutate source ReportData. These are complementary browser/API tests,
not a simultaneous production-database load test.

## Local initials demo

For the Tuesday walkthrough, use the [Norwegian startup guide and checklist](demo-walkthrough-nb.md).
The note/sign-off panel follows the reference's two-column, four-card layout,
collapsing to one column on narrow screens. Sign-off displays the last saved
self-reported initials and revision, updated only after an acknowledged save;
historical records without initials say so instead of presenting a technical
service account as the biologist. Snapshot exports retain these labels.
Reset is now available for DRAFT reviews. It requires confirmation and initials,
creates a new blank saved revision, and leaves source facts, older revisions and
audit rows intact. It is not available after finalization.
Report copy is operational: no generic quality-process footer or commentary
about which biologist should finalize. Finalization still confirms that the
report will be locked; draft status, attribution and actionable errors remain.

`browser/test_demo_workflow.py` exercises real Chrome against an isolated Django
test database without mocking the save/reset/finalize/HTML endpoints: selection,
QC and report notes, TMB correction, initials, save/reload, reset, same-person
finalization, downloaded offline HTML, print preview and audit records. The in-app browser's
native finalization confirmation stalled during manual verification; use
Chrome/Edge for the walkthrough. The user-facing demo remains an untouched draft.

Set a process-local `PRONTO_DJANGO_SECRET_KEY`, then run:

```powershell
python manage.py run_demo --database fresh-preview.demo.sqlite3 --report demo-preview --port 8768
```

Open `/reports/demo-preview/` directly: no login page. The command requires a
new database filename on each start and refuses existing databases. This protects
existing finalized reports; it is not the production deployment entry point.
The dedicated technical user has report access only. Do not run behind a proxy
or expose externally; only direct loopback connections are accepted.

Save, Reset and Finalize require self-reported initials. The Download report HTML
action requires initials and an acknowledged audit event for the exact saved
revision. The audit means HTML_DOWNLOAD_REQUESTED, not that the browser saved or
opened the file. An exact failed retry keeps the same request ID and renders
the same historical revision; changed request details conflict. Initials are
not authentication. The older print-request endpoint and its audit records
remain for compatibility, but the live workspace now offers HTML download.

Offline HTML printing is explicitly local-only: it does not prompt for fresh
requester initials or create a central audit event. Browser-menu printing and
screenshots cannot be comprehensively audited. Clinical deployment, privacy
retention policy and production database concurrency remain outside this demo.
