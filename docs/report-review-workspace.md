# Report review workspace

For local installation and login, see the [startup guide](oppstart-nb.md).
The workspace keeps imported `ReportData` separate from the reviewer's saved
decisions, comments, corrections and report text in `ReviewState`.

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
