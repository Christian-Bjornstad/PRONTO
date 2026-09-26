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

## Local initials demo

Set a process-local `PRONTO_DJANGO_SECRET_KEY`, then run:

```powershell
python manage.py run_demo --database fresh-preview.demo.sqlite3 --report demo-preview --port 8768
```

Open `/reports/demo-preview/` directly: no login page. The command requires a
new database filename on each start and refuses existing databases. This protects
existing finalized reports; it is not the production deployment entry point.
The dedicated technical user has report access only. Do not run behind a proxy
or expose externally; only direct loopback connections are accepted.

Save and Finalize require self-reported initials. Application print requests
require initials and an acknowledged audit event for the current saved revision.
The audit means PRINT_REQUESTED, not that paper/PDF was produced. A failed request
can be retried with the same idempotency key. Initials are not authentication.

Offline HTML printing is explicitly local-only: it does not prompt for fresh
requester initials or create a central audit event. Browser-menu printing and
screenshots cannot be comprehensively audited. Clinical deployment, privacy
retention policy and production database concurrency remain outside this demo.
