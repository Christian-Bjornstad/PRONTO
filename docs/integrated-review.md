# Integrated review and PDF exports

The workspace saves small variants, CNV, RNA, QC, free text and presentation
figures in one explicit working copy. Source facts remain separate from review
decisions. See [review and revision behavior](report-review-workspace.md) and
the [local startup guide](oppstart-nb.md).

## Review surfaces

- Small variants expose all available source columns in one table. Inc/Exc,
  Review, Report highlight and IGV QC are separate choices. Source defaults use
  Class_judgement and CPSR_ClinVar_class, preserving saved manual choices.
- Review supports Benign, Likely benign, VUS, Pathogenic, Likely pathogenic,
  Oncogenic and Likely oncogenic, with Not reviewed as the empty state.
- CNV has a full source table, Inc/Exc, Report highlight, Gain/Loss, Cytoband and
  manual top rows. The plots view starts with B3 above C1, then offers individual
  panels and the Cancan plot when supplied.
- RNA shows fusion/splice source columns, reporting choices and domain plots.
  Source QC highlighting is independent of manual report selection.
- Report highlights are **Key relevant findings**. Exclude overrides highlight.
- Five QC assessments cover small variants, CNV, RNA, mutational signatures and
  overall assessment: Green/Pass, Orange/Conditional, Red/Fail and Not reviewed.
  CNV and RNA comments are edited in their own tabs and included in PDFs.
- TMB, MSI and HRD display score and range. Ranges describe display bounds, not
  clinical thresholds. Missing scores remain unavailable.
- The Report page accepts history, summary, therapeutic context, variant
  description, clinical actionability, trials, follow-up, methods, references,
  patient details and additional comments as free text.

## PDF formats

**Presentation PDF** is landscape A4 with a patient sidebar, Key relevant
findings and compact findings tables. Selected CNV/RNA and free text continue
on subsequent pages when necessary. **ESMO PDF** is portrait A4 with Summary,
Results and clinical evidence sections. Layouts follow the supplied visual
references; long content continues instead of being clipped.

Both formats contain saved selections, corrections, QC, ranges, DRAFT/FINAL
status, revision and recorded reviewer identity. Export requires saved changes.
The backend checks report access, CSRF and saved revision/version, then records
a transactional audit for the exact exported snapshot. Repeating the same
request ID returns that snapshot; changing its identity conflicts. Exporting
does not finalize a report.

## Presentation figures

PNG, JPEG and WebP uploads support previews, captions, ordering and removal from
the selected list. Save records the selection, captions and order. Figures
appear only at the end of the landscape PDF. Historical snapshots retain their
selected immutable assets.

Images are decoded and re-encoded as PNG without original metadata. Each upload
is limited to 8 MB and 64 million source pixels, then scaled proportionally to
at most 16 million stored pixels. Up to 30 figures can be selected. The private
per-report store is limited to 64 MB and 100 assets. Access requires the report
grant; local uploads and generated PDFs must stay outside Git.

## Patient overview and history

`/` and `/reports/` list authorized reports, 25 per page, with patient/sample,
tumour type, status and save time. A fresh report is un-reviewed; saved work is
under-review; signed work is reviewed. The overview distinguishes the latest
signed revision from an active draft. Open a historical snapshot with
`?revision=N`; missing or unauthorized revisions return 404.

## Dependencies and test inputs

Runtime dependencies are in `requirements.txt`, tests in `requirements-test.txt`,
and browser checks additionally use `requirements-browser.txt`. Poppler handles
source PDF plots; generated reports use ReportLab.

Use approved fixture inputs or the [synthetic cohort](synthetic-demo.md) for
testing. Local supplemental workbooks, source figures and generated patient
outputs stay outside Git. A separate loopback fixture demonstration can use
`run_demo --supplementary-demo-dir PATH_TO_APPROVED_INPUTS`; it requires a new
isolated database. `resume_demo` resumes that database without re-importing it.
These commands are separate from the authenticated local launcher.
