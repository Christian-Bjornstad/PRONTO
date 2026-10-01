# Integrated variant, CNV, RNA and PDF review

Status: implementation authorized by owner on 2026-10-01, including GitHub merge.
Supersedes the open choices in the 2026-09-30 draft; historical documents remain.

## Agreed behaviour

- Both exports are PDF: landscape presentation and portrait ESMO-style Summary,
  Results and Key relevant findings / clinical evidence pages. Approximate the
  supplied screenshots; no editable original template exists. Continue pages
  rather than clipping long text or silently omitting selected findings.
- VUS in Key findings mirrors Review = VUS. Review choices are Benign, VUS,
  Oncogenic, plus an initial unreviewed state. UNCERTAIN migrates to VUS.
  Other old classes retain their source label and require a new classification;
  PATHOGENIC does not silently acquire ONCOGENIC meaning.
- Keep current main variant information and explicit inclusion decisions.
  Exclude overrides highlight; undo Exclude returns to unreviewed. Human review
  determines every decision; source QC/highlight is not report inclusion.
- Report highlight means Key relevant findings. Use this term throughout new
  report UI and output; preserve established technical field names internally.
- Preserve every source variant column in Details and full table mode. CNV
  review has Table / Plots views with Include, Exclude and highlight. The first
  plot group is B3 above C1; remaining panels are individually selectable.
  Include the supplied Cancan image as a separate plot.
- RNA review contains the full fusion/splice table with Include, Exclude and
  highlight, plus domain plots. Original source QC, sample IDs and spreadsheet
  highlighting remain distinguishable from human report decisions.
- Five linked manual QC assessments: small variants, CNV, RNA, mutational
  signatures, overall. PASS = green, CONDITIONAL = orange, FAIL = red;
  NOT_REVIEWED = neutral. Section controls and report controls share state.
  Colour is accompanied by words. Existing numeric/source QC is unchanged.
- Signature cards/table: TMB range [0-100+], MSI [0-100], HRD [0-100]. These are
  display ranges, not clinical classification thresholds. Only explicitly
  synthetic demo measurements may get example values (16, 10, 42).
  Existing source TMB/MSI are retained. HRD missing from source stays unavailable
  unless explicitly populated as a labelled demo measurement.
- Report texts are manual free text: history, summary, therapeutic context,
  variant description, additional comments, follow-up, references, methods,
  clinical evidence and clinical trials. Keep QC comments and imported notes.
- Save is explicit; FINAL is locked; export DRAFT with visible status is allowed.
  Exports use exact saved revision with corrections, not browser DOM.
- Start page lists permitted patient/sample reports with concise facts and
  un-reviewed / under-review / reviewed status. A saved review audit indicates
  under-review, signing indicates reviewed, seeding alone is un-reviewed.
  Each entry opens the latest report and offers prior saved revisions read-only.

## Local files and demo consent

`info/` is outside the repository. Files are local input, never committed to the
public repository. CNV CSV uses semicolons and 26 preamble rows. RNA XLSX has a
40-column header on row 43 and 428 data rows, including source spreadsheet QC
and highlighting. It contains more than one Sample_ID, and a plot filename
does not exactly match a table Event_ID. The owner explicitly chose a marked
demonstration with multiple samples on 2026-10-01. Do not claim patient matching
or infer plot identity from approximate gene/filename matching. Add supplied
plots to a labelled source gallery unless an explicit link is available.

## Boundaries

Versioned ReportData v2 adds complete source tables and display-range/demo
metadata. ReviewState v3 adds report highlights, CNV/RNA decisions, signature
highlights, section QC and free texts. Validate IDs against sources. v1/v2
history is immutable and readable; moving a DRAFT to v3 is not an implicit save.

New PDF audit stores layout, template version and saved revision. Retry renders
the recorded snapshot or fails if unavailable. Access, CSRF, revision check
and audit rollback use existing Django patterns. Authoritative source
measurements and prior reviews are never overwritten by demo input.

## Acceptance

Save/reload preserves decisions, all QC controls and text across tabs. Both
PDFs show only included findings, distinguish Key relevant findings, include
VUS labels, section/overall QC, ranges, status and attribution. Full table
controls work on wide/narrow screens without widening the page. Historical
revisions have no write controls. Ungranted users cannot list, view or export
reports/history. Review, Reset, FINAL, IGV and legacy export regression tests
remain passing. A separate local demo demonstrates supplied files without
changing any existing demo database. GitHub receives code/tests/docs only.
