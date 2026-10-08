# Review workspace refinement

Use the existing review controls and visual style. Retain signature highlighting,
moving one compact checkbox and range into each TMB/MSI/HRD card. Style CNV's Table
and Plots choices as a segmented control. Remove source legends and mixed-sample
notices from rendered reports, retaining the original source tables and Sample_ID.

Modern Variant review uses one table: fixed review columns followed by genomic
fields, IGV assessment, comments, annotations and complete source columns. Join
source values by occurrenceId, never just gene or variantId. Preserve transcript
occurrences, duplicates, search, sorting, include/exclude and historical read-only
behavior. Keep legacy standalone rendering compatible.

Authenticated web actions use the server's session user as attribution. Save,
reset, finalization and PDF export require no self-declared initials. Extend the
review attribution contract to record actorId/actorLabel with method AUTHENTICATED,
while retaining historical SELF_REPORTED data. PDF audit migration preserves old
rows. Client data must not override authenticated attribution.

Remove the HTML download button; existing historical export endpoints remain
compatible. Provide hypothetical English example text per existing report field,
based on the supplied PDFs, without fabricated trial IDs or references.

Verify occurrence-specific source values, authenticated action attribution and
rollback/idempotency, immutable imported notes, UI controls, PDF text and layout.
Run project checks, inspect the browser, merge after CI and restart the local app.

## Verification

- Django request suite: 89 passed. Non-browser pytest suite: 300 passed,
  17 skipped for optional integrations. Browser regression checks cover modern
  review controls, figure captions, authenticated PDF commands, reset/save and
  finalization. The old HTML download flows now exercise the saved PDF export.
- The browser opened the real saved revision 6: one variant table, 30 source
  occurrences and 79 columns; no details accordion, HTML button or initials
  dialog. CNV still opens B3 above C1. RNA retains 428 rows and Sample_ID.
- Both actual PDF buttons exported revision 6 without an initials prompt. Every
  page identifies the authenticated account. The mixed-sample notice is absent.
  ESMO is portrait (3 pages); presentation is landscape (6 pages including figures).
- The SQLite backup and migrated database retain identical source snapshots,
  reviews, report assets, review audit, user permissions and credentials. Login
  timestamps and the two requested PDF audit events are the expected changes.
- Self-review checked occurrence joins, escaping, session-derived attribution,
  revision conflicts, PDF retry identity and historical schema compatibility.
  The clean display uses the untouched saved command payload so generated copy
  cannot prevent saving or finalizing a synthetic case.
- Private inputs, PDFs, screenshots, credentials and SQLite data remain local;
  only code, migration, regression tests and documentation are committed.
