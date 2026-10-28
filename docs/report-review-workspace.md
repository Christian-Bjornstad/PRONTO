# Report review workspace

For local installation and login, see the [startup guide](oppstart-nb.md).
The workspace keeps imported `ReportData` separate from the reviewer's saved
decisions, comments, corrections and report text in `ReviewState`.

## Changes in 0.7.0

New report defaults exclude `synonymous_variant`, LocalApp `BL` and `GL_BL`,
and `x:noncoding*` except for the gene TERT. The TERT exception applies only
to the noncoding rule. Both `coding_status` and the historical typo
`coding_sastus` are accepted, without regard to column-name case.
Original variant rows remain available for review and explicit overrides.
Existing saved choices are preserved. In an existing draft, enable editing
and choose **Variant review → Apply variant filters** to apply only these
exclusions. Other classifications and comments are kept. Save afterwards.
**Use source defaults** is broader and also replaces choices from the source.

Import now recognizes `report_withQC` and prefers it in automatic file-version
selection when that sample has a primary QC variant table, otherwise retaining
the selected preQC/raw version. A missing table in a selected preQC version still
blocks import instead of silently substituting raw variants. RNA workbooks
in `report_withQC/Fusion_splice/<DNA sample>/` are matched to the exact linked
RNA sample, with raw RNA tables used where no QC workbook exists. Yellow
rows in the `*_withQC.xlsx` workbook seed Include, other rows seed Exclude,
when a review entry has no saved human choice. These are reporting defaults,
not inferred clinical classifications or an automatic overall QC assessment.
Yellow source rows remain visible in RNA review. Gene names, event, exon/intron
fields and read support come first; all other source columns remain available.
**Review note** supplies the RNA Review text in the presentation PDF.

Changed input files do not overwrite an existing report during re-import.
The importer reports a different source basis and preserves the report and
its reviews. Re-import with QC files into a separate empty data root for
comparison if the patient already exists. There is no automatic migration of
existing raw RNA reviews onto new QC rows.

In **CNV review**, enter an absolute manually reviewed value in **Tumor_CN**.
It is saved separately from imported measurements and appears in both the
presentation's Copy number alterations and Key relevant findings tables.
Source Tumor_FC is never converted into an absolute copy number. For older
manually added rows, the legacy tumorFc value is displayed as the manual CN
until a separate tumorCn value is supplied. Include the row, select Gain/Loss
and select **Key relevant findings** when it belongs in the highlights.

In **Tumour board report → Key relevant findings — report fields**, highlighted
included findings have editable names, alteration/effect text, GoF/LoF,
Sensitive/Resistant, EMA context and descriptions. Blank display text uses the
source label. CN/VAF/read-support values come from the underlying finding;
change manual CN in CNV review. TMB/MSI/other available signature statuses can
be edited without adding them to the highlights. Enable Edit mode and Save
before exporting. These fields are human-entered; no therapy/status is inferred.

Fusion labels use `GENE_A::GENE_B` and supplied exon/intron fields, for example
`EWSR1(ex8)::ATF1(ex4)`. Splice labels preserve the supplied boundaries; the app
does not infer an exon-skipping name from two coordinates. Override the display
text explicitly if a different reviewed name is needed. Compact mutation effect
labels omit the `_variant` suffix; original annotations remain in source tables
and the detailed appendix. Presentation template version is 2.1.

## Review tables

Variant review, CNV and RNA display their source data in horizontally scrollable
tables. **Expand table** moves the same live table into a resizable dialog.
Zoom scales the complete table, including controls and column widths. Closing
the dialog returns the table to its tab without losing edits.

**Inc / Exc** controls reporting independently of classification. Excluded rows
are muted and struck through, and do not appear in PDF findings. **Report
highlight** selects included findings for **Key relevant findings**. Changing a
filter does not change any saved selection. Duplicate small-variant occurrences
share their review while retaining separate source occurrence identifiers.

Small variants start from source defaults for reporting and classification
when no saved manual choice exists. **Use source defaults** explicitly replaces
those choices from `Class_judgement` and `CPSR_ClinVar_class`. The Biomarker column
shows gene-list membership; membership alone never includes or highlights a row.
IGV QC offers OK, Artifact and Not reliable independently of the reporting choice.

CNV supports Gain/Loss and editable Cytoband. **Add CNV row** inserts a manual
row above the source rows with editable Gene_Symbol and Tumor_FC. The remaining
source fields stay empty. Reporting/highlight and CNV review controls remain
available. Included manual rows need a gene before finalization.

CNV and RNA each have their own QC comment field. Their comments are included
in PDF output without adding duplicate editors to the Report tab. QC status
controls are linked across the review tabs and Report.

## Save, finalize and start another revision

The local launcher enables `PRONTO_WORKING_DRAFTS`. One active `WorkingDraft`
holds each report's editable review. **Save** replaces this draft and records a
small action event; it does not preserve the full previous draft on every save.
Source facts stay immutable. Existing historical `ReviewRevision` rows remain
available.

**Finalize** requires saved changes, preserves a signed FINAL snapshot and
closes the active draft. A FINAL snapshot is read-only. **Start new revision**
copies the selected saved DRAFT or FINAL into a new working draft without
changing the selected historical snapshot. Replacing an active working draft
requires confirmation. Starting from the current working draft preserves that
selected source once before creating the new revision.

PDF export requires a saved review and records the exact snapshot exported.
An active draft is frozen for export; subsequent edits use the next revision.
Retries of the same export request return the same exported snapshot.
See [PDF formats and figures](integrated-review.md).

All current actions use the authenticated account. Older revisions retain their
original attribution. Historical revisions open through `?revision=N` and are
read-only. The patient overview distinguishes the latest signed report from
an active draft and offers saved history separately.

## Recovery after an unsuccessful save

If saving fails, keep the page open until the working copy is secured:

1. Local edits remain marked unsaved; a failed request does not advance the
   browser's acknowledged revision or draft version.
2. Use the offered local draft JSON download to preserve the working copy.
   This is a backup, not confirmation of a database save.
3. Retry after a network/server failure. If the first request committed but
   its response was lost, the retry can report a version conflict.
4. For a conflict, secure the local copy before loading the latest saved review
   and reconcile the differences explicitly. There is no automatic merge.

Signing and PDF export are blocked while edits are unsaved. Revision/version
checks reject stale browser requests rather than overwriting another save.
The JSON download is not automatically imported back into the database.

## Compatibility

The older immutable-per-save API remains available when working drafts are
disabled. Its legacy command and attribution rules differ from the current
workspace. See the [command contract](review-command-contract.md) for the two
versions. Enabling working drafts on a separate deployment requires migration
and `PRONTO_WORKING_DRAFTS=true`; the loopback launcher enables it automatically.
