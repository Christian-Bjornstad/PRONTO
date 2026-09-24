# IGV alignment source operations

The optional read-only registry is configured with `PRONTO_ALIGNMENT_SOURCE_ROOT`
and `PRONTO_ALIGNMENT_REGISTRY_JSON`. With both unset, reports offer no registered
alignment pair. Setting only one is an error. The root must contain the data and
index files; do not place it in Git, Django static/media, or a public web tree.

The UTF-8 JSON manifest is versioned and maps exact report, sample, and
reference-build identifiers to explicit file pairs. Example with synthetic
identifiers (paths are relative to the source root):

```json
{
  "version": 1,
  "sources": [
    {
      "id": "tumour-dna-1",
      "reportId": "report-synthetic-1",
      "sampleId": "sample-synthetic-1",
      "referenceBuild": "GRCh37",
      "role": "TUMOUR_DNA",
      "format": "bam",
      "data": "sample-synthetic-1/tumour.bam",
      "index": "sample-synthetic-1/tumour.bam.bai"
    }
  ]
}
```

Permitted roles are `TUMOUR_DNA`, `NORMAL_DNA`, `TUMOUR_RNA`, and `NORMAL_RNA`.
The build must be `GRCh37` or `GRCh38`; formats are `bam` or `cram` with an
explicit `.bai`/`.csi` or `.crai` index. Manifest source IDs must be unique.
All paths are resolved under the configured root; missing, symlinked, escaping,
or malformed entries make the registry unavailable rather than triggering a
filename search. Multiple valid pairs remain separate user choices.

This registry alone does not save an uploaded file. Full-file preservation,
retention/deletion policy, and clinical deployment controls are specified in
`docs/superpowers/specs/2026-09-24-igv-alignment-sources-design.md`.

For embedded IGV, configure both `PRONTO_IGV_GRCh37_FASTA_URL` and
`PRONTO_IGV_GRCh37_FAI_URL` (and/or the corresponding `GRCh38` names) as
same-origin absolute URL paths. The reference FASTA/index must be available
through an institution-approved service that supports HTTP byte ranges and
does not redirect to a public host. If a build has no configured reference,
the panel reports this and does not load alignments. Set `PRONTO_STATIC_ROOT`
to a deployment build directory and run `collectstatic`; serve the collected
`report-igv.js` and vendored `igv/igv.esm.min.js` at `/static/` on the same
origin. The viewer never requests a CDN or IGV default genome list.

## Private preservation gate

Alignment preservation remains disabled until a Linux deployment sets all of:
`PRONTO_ALIGNMENT_STORE_ROOT` and `PRONTO_ALIGNMENT_STAGING_ROOT` to existing,
different private directories outside the project and outside any configured
`STATIC_ROOT`/`MEDIA_ROOT`; `PRONTO_ALIGNMENT_MAX_BYTES`
and `PRONTO_ALIGNMENT_MAX_INDEX_BYTES` to positive per-file byte limits;
`PRONTO_ALIGNMENT_MAX_REPORT_BYTES` to a positive cumulative retained/pending
limit for one report;
`PRONTO_ALIGNMENT_MIN_FREE_BYTES` to a nonnegative reserved-space threshold;
and `PRONTO_ALIGNMENT_POLICY_APPROVED=true` only after the institution approves
retention, deletion, backup, restore, and access policy. At least one supported
build needs `PRONTO_ALIGNMENT_GRCh37_FASTA_PATH` plus
`PRONTO_ALIGNMENT_GRCh37_FAI_PATH`, or the corresponding `GRCh38` paths, to
existing local reference files. A configured reference for one build does not
authorize a different build. These filesystem paths are server-side settings,
never sent to the browser. The separate `ReportWriteGrant` is required for
mutations; without this configuration save routes fail closed.

The pinned `pysam` validator is installed on Linux; native Windows remains
view-only and fails the preservation gate. Development and deployment of the
save service can use Linux/WSL, subject to the same private-root policy.

The storage service validates real BAM/CRAM content against an explicit local
FASTA and its `.fai`, requires a readable index, and compares available contig
names and lengths. It copies the complete pair with bounded streaming into a
private temporary directory, computes SHA-256 for each component, fsyncs the
files, and atomically promotes the directory. Only after that may a READY
database record refer to the pair. A failed copy/promotion removes the partial
directory; neither file belongs in Django static/media or an HTML export.
The storage service itself is not an upload endpoint. The save command passes
the deployment's byte limits and checks write authorization before calling it.

The save-command layer now uses a separate `ReportWriteGrant` for every
preserve, chunk, completion, copy, cancel and delete action. A local session is
bound to its original user and exact report/sample/build/role, and remains
unpublished until both whole files validate. Repeated completion of that same
session returns its existing saved record; a different pair under the same
identity is rejected rather than overwritten. The source registry reserves
`saved-` IDs for READY managed pairs. Deletion first hides a saved pair as `DELETING`, then
removes the managed bytes and writes a minimal audit event. A failed filesystem
deletion leaves a hidden tombstone for an authorized retry or operational
reconciliation; it must never reappear as a READY source automatically.

The authenticated save protocol uses `POST .../alignments/save-sessions/` only
after an explicit confirmation, then contiguous `PUT` chunks to its opaque
session ID (`data` and `index`, each at most 8 MiB), and a separate `POST`
completion with the confirmed build. `DELETE` cancels an incomplete session.
Registered sources have an explicit `POST .../<source-id>/preserve/` copy action;
managed pairs have a separate `DELETE .../<saved-uuid>/` action. Mutations
require the writer grant and CSRF token. Only READY saved pairs appear in the
report and authorized byte-range route; incomplete staging is never an IGV
source. The ordinary review save endpoint remains unrelated to this protocol.

### Operations before clinical use

- Provision the managed and staging directories on private storage with
  permissions restricted to the application account. Do not expose them via
  static files, a general media route, a reverse-proxy alias, or a backup link.
- Confirm an institutional retention/deletion policy, audit access, backup and
  restore procedures, and capacity monitoring before setting
  `PRONTO_ALIGNMENT_POLICY_APPROVED=true`. The environment flag is a deployment
  acknowledgement, not a substitute for policy approval.
- Set per-file byte limits and a free-space reserve appropriate for the local
  storage. A new local upload requires room for both staging and the managed
  copy, plus the reserve; a registered copy requires room for the managed copy.
  These preflight checks do not replace filesystem monitoring during transfer.
  Configure the reverse proxy to admit the 8 MiB chunk body plus
  headers while rejecting larger requests. Use HTTPS, secure session/CSRF
  cookies, and production Django security settings.
- Host IGV JavaScript and each approved reference FASTA/index on the same
  origin. Use a matching local FASTA/FAI for server validation. Never rely on
  a remote CRAM reference fallback or a public CDN.
- Schedule `python manage.py clean_alignment_staging --dry-run` to inspect
  expired sessions and `python manage.py clean_alignment_staging` to remove
  their owned staging bytes. This command does not delete READY saved pairs.
  Investigate any `DELETING` tombstone before retrying authorized deletion.
- After a crash, run `python manage.py reconcile_alignment_store` to count
  managed pairs without a database owner and interrupted temporary copies
  older than 48 hours. During
  a maintenance pause with no active uploads, use
  `python manage.py reconcile_alignment_store --delete` to remove only those
  old orphan pairs. The command refuses symlinks or unexpected contents and
  never removes a pair referenced by a READY or DELETING record. Unexpected
  filenames and directory contents remain untouched for manual investigation.
- Grant `ReportGrant` for reading and `ReportWriteGrant` separately for file
  preservation/deletion. Revoke the write grant when a user should still view
  the report but must not retain or remove genomic files.

Only synthetic fixtures are committed to Git. The code and tests do not make
this a clinically approved deployment; the institution must validate the
storage, backup/restore, retention, access and security configuration first.
