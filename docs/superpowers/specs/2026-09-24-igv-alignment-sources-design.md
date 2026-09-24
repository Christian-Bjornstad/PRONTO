# IGV alignment sources in the interactive report

Date: 2026-09-24

Status: design approved in conversation on 2026-09-24; written spec awaiting owner review

Depends on: `2026-09-23-report-html-fidelity-and-review-persistence-design.md`

## Intent and success

Molecular biologists should inspect the reads supporting a variant without
leaving the familiar report workflow. A sample may already have a registered
BAM/CRAM plus index in a configured location. If not, the biologist may select
the pair on their own computer and inspect it temporarily. **Nothing is sent
to or retained by the report server merely because a local file was selected.**
The distinct **Lagre filer for senere bruk** action saves the *complete*
alignment file and its index for later authorized review. The ordinary report
**Lagre** action never saves alignment files.

Success means that a reviewer can open IGV at a variant locus, distinguish a
registered source from an unsaved local source, and later reopen a deliberately
saved source. A missing, ambiguous, invalid, or incompatible source must never
appear as successfully loaded or saved.

## Decision and alternatives

Use igv.js embedded in the authenticated report, with local-first fallback.
The alternatives considered were (1) uploading every selected file to a
temporary server area before viewing, which transfers potentially huge and
sensitive files without an explicit save choice, and (2) launching a separate
IGV application, which loses the direct variant/review context. Neither is
selected. IGV's own web application demonstrates local BAM plus index
selection; indexed server-hosted data requires HTTP byte ranges.

The original `C:/Users/molpa/Documents/Inpred/report.html` remains the visual
and interaction reference. Its IGV QC text field is not itself a genome viewer.
The existing `igvAssessment` in `ReviewState` remains a human judgement, not a
flag that an alignment file was uploaded or validated.

## Scope

Included:

- A **Vis i IGV** action for a variant with an explicit genomic coordinate and
  known, supported reference build; the viewer is a panel in the report rather
  than a replacement for the variant table.
- A configured registry of read-only, server-accessible alignment pairs keyed
  to exact report/sample/build identity, plus an explicit local-file fallback.
- Explicit, authenticated preservation of an entire BAM or CRAM and its
  matching index. A registered pair is copied into managed storage only when
  marked important; its original location is otherwise left untouched.
- Reopening a saved pair through authorized, same-origin, range-capable URLs.
- Source, format, build declaration, size, checksum, and save actor/time
  metadata, without putting file bytes in `ReportData`, `ReviewState`,
  `ReportAsset.content`, Git, or a self-contained HTML export.

Not included: automatic variant interpretation, automatic clinical
classification, editing alignments, arbitrary remote-URL import, sharing with
users who lack report access, or displaying raw alignments inside an offline
export. Saved IGV files are independent of review finalization; finalizing a
report neither saves nor deletes them.

## Components and contracts

| Unit | Responsibility | Boundary |
| --- | --- | --- |
| Alignment registry | Resolve exact report/sample/build to zero, one, or multiple registered BAM/CRAM/index pairs under configured allowlisted roots | Never searches arbitrary paths supplied by the browser; never chooses an ambiguous match |
| IGV projection | Provide variant locus and source availability/status to the UI | Reads validated `ReportData` and source metadata; never exposes filesystem paths |
| Report IGV panel | Lazily create igv.js, load a registered/saved track or browser-selected local file pair, display source and unsaved state | File selection alone makes no upload request |
| Save service | Authorize, receive a deliberate save, validate pair, compute checksums, and publish both files atomically | Streams into bounded staging outside the public web root, then records metadata only after successful validation |
| Data endpoint | Serve registered/saved data and index with byte ranges | Reauthorizes the requesting user for this report on every request; same-origin; no public/static URL |

The registry is configuration/metadata, not a filename heuristic. Its entries
identify the pair, declared build, sample, optional track role (for example
tumour DNA or normal DNA), and storage locator. Multiple valid pairs may be
shown as explicitly labeled choices; no pair is silently selected when the
role or sample is ambiguous. The managed save store has a separate configured
root outside the repository, database, and publicly served static/media tree.
Original filenames are display metadata only, never destination paths.

The browser may use local `File` objects only after an explicit picker action.
It must not enable IGV query-parameter file loading, arbitrary remote track
URLs, or default hosted genome discovery. The igv.js script and the declared
reference resources are served from an approved same-origin installation;
clinical alignment data is never intentionally sent to igv.org or a CDN.

## User flow and states

1. An authorized reviewer chooses **Vis i IGV** for a variant. The report
   checks its declared build and coordinate, then asks the registry for that
   sample. Unknown build or unusable coordinate disables opening with a reason.
2. One unambiguous registered or previously saved pair is offered with source
   and track label. Multiple pairs require an explicit choice. No pair shows
   **Velg BAM/CRAM og indeks**. BAM and CRAM both require an index; the picker
   never assumes browser access to an adjacent index file.
3. A local pair opens in the current browser page only, labeled **Ikke
   lagret**. Closing/reloading the page loses the selected file handles and
   shows the normal source lookup again. Review comments and `igvAssessment`
   follow the existing explicit review-save workflow; they do not keep the
   alignment file alive.
4. **Lagre filer for senere bruk** has a separate confirmation showing sample,
   build, filenames, total bytes, and destination purpose. Only after
   confirmation does transfer begin. Progress/cancel and clear success/failure
   states are required. The label changes to saved only after the entire pair
   and metadata are committed. A failed or cancelled transfer leaves no
   visible saved record and any staging bytes are cleaned up.
5. Reopening a saved pair uses the same IGV panel. An offline/read-only HTML
   snapshot may show that a source was saved and its provenance, but never
   contains data URLs, private paths, credentials, or raw file bytes. If it is
   disconnected from the server, IGV data access is unavailable rather than
   silently falling back to a public service.

The save action is idempotent for an already saved identical pair under the
same report/sample/build/role. A different pair for that identity is a
conflict requiring an explicit choice, never an overwrite. The record should
support more than one role per sample without conflating tumour, normal, or
RNA tracks. A registered source is viewable without copying it; selecting
save for later use preserves its complete pair in the managed store.

## Validation, security, and operations

Alignment files are potentially sensitive human genomic data. The server
checks active authentication and report-specific authorization for registry
lookup, save initiation, every upload part, save completion, and every data or
index range request. Read permission alone does not imply permission to save;
the write policy must be the same explicit policy used for report review
commands. Upload mutations use CSRF protection. No browser-supplied path or
URL is accepted as a storage locator. Do not log read data, patient-identifying
filenames, or authorization tokens.

Before publishing a saved pair, enforce configured per-file and per-report
limits; validate actual format and index readability rather than extensions
or MIME types alone; compare the declared reference build and available
contig/header information with the report, blocking a known mismatch; and
require the reviewer to confirm the build because alignment data may not
identify it conclusively. The pair is staged under generated opaque names,
checksummed while streaming, and made visible together only after both
validate. Long transfers must not be held wholly in application memory.
Interrupted transfers have bounded staging lifetime and a safe cleanup path.
No automatic retry may turn a single confirmation into duplicate records.

Range delivery supports indexed reads (`206`, `Content-Range`, `Accept-Ranges`
and correct `416` behavior) for both the alignment and index, with
`Cache-Control: no-store` and content-type hardening. Same-origin delivery
avoids a credentialed wildcard CORS policy. Saved files and references remain
outside ordinary Django static serving; any reverse-proxy acceleration must
preserve the per-request authorization boundary. Reference build selection
must never silently substitute GRCh37 for GRCh38 or vice versa.

Clinical deployment is fail-closed until an administrator configures the
registry root(s), managed storage root, quotas, reference resources, backups,
and an institution-approved retention/deletion policy. No default clinical
upload destination or indefinite implicit retention is provided. An authorized
deletion workflow must remove managed bytes and metadata together, respecting
the deployment's approved audit and backup rules. Synthetic fixtures may be
used for development before those operational settings exist.

## Failures and acceptance tests

- No registry match, ambiguous match, missing index, unsupported build,
  coordinate mismatch, known build mismatch, invalid format, corrupt index,
  full quota, interrupted transfer, and inaccessible source each have an
  actionable state without a false success indication.
- Selecting a local pair, navigating loci, saving the report review, and
  finalizing the report produce no alignment upload. Only the separate,
  confirmed save action transfers the entire pair.
- Direct URL access, guessed IDs, and byte-range requests from a user without
  the report grant fail. A user with read access but without save permission
  may view an available pair but cannot preserve one. An authorized range
  request returns only the requested bytes, including after reopening the
  report.
- The same saved pair is not duplicated; a different pair for the same
  identity cannot overwrite it silently; a partially transferred pair is
  never offered to IGV.
- Browser tests use synthetic indexed BAM/CRAM fixtures to verify locus,
  local unsaved state, explicit upload, source switching, failed/cancelled
  upload, and offline snapshot behavior. Server tests cover authorization,
  CSRF, quota, format/index checks, path containment, atomic publication,
  staging cleanup, and range semantics.

## Sources

- [igv.js local BAM example](https://igv.org/web/test/examples/localBam.html)
- [igv.js data-server requirements](https://igv.org/doc/igvjs/Data-Server-Requirements/)
- [IGV-Web user guide: local files, indexes, and reference limitations](https://igv.org/doc/webapp/UserGuide/)
- [Django 5.2 file uploads and streaming](https://docs.djangoproject.com/en/5.2/topics/http/file-uploads/)
