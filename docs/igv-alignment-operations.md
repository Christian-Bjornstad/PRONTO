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
`docs/superpowers/specs/2026-09-24-igv-alignment-sources-design.md` and will
be implemented in the separate preservation slice.

For embedded IGV, configure both `PRONTO_IGV_GRCh37_FASTA_URL` and
`PRONTO_IGV_GRCh37_FAI_URL` (and/or the corresponding `GRCh38` names) as
same-origin absolute URL paths. The reference FASTA/index must be available
through an institution-approved service that supports HTTP byte ranges and
does not redirect to a public host. If a build has no configured reference,
the panel reports this and does not load alignments. Set `PRONTO_STATIC_ROOT`
to a deployment build directory and run `collectstatic`; serve the collected
`report-igv.js` and vendored `igv/igv.esm.min.js` at `/static/` on the same
origin. The viewer never requests a CDN or IGV default genome list.

## Private preservation gate (no upload protocol yet)

Alignment preservation remains disabled until a Linux deployment sets all of:
`PRONTO_ALIGNMENT_STORE_ROOT` and `PRONTO_ALIGNMENT_STAGING_ROOT` to existing,
different private directories outside the project; `PRONTO_ALIGNMENT_MAX_BYTES`
and `PRONTO_ALIGNMENT_MAX_INDEX_BYTES` to positive per-file byte limits;
`PRONTO_ALIGNMENT_MIN_FREE_BYTES` to a nonnegative reserved-space threshold;
and `PRONTO_ALIGNMENT_POLICY_APPROVED=true` only after the institution approves
retention, deletion, backup, restore, and access policy. At least one supported
build needs `PRONTO_ALIGNMENT_GRCh37_FASTA_PATH` plus
`PRONTO_ALIGNMENT_GRCh37_FAI_PATH`, or the corresponding `GRCh38` paths, to
existing local reference files. A configured reference for one build does not
authorize a different build. These filesystem paths are server-side settings,
never sent to the browser. This step creates metadata tables and a separate
`ReportWriteGrant`, but does not yet enable an upload route or store bytes.

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
This service is not an upload endpoint by itself. The future save command must
pass the deployment's byte limits and verify explicit user confirmation and
write authorization before calling it.

The save-command layer now uses a separate `ReportWriteGrant` for every
preserve, chunk, completion, copy, cancel and delete action. A local session is
bound to its original user and exact report/sample/build/role, and remains
unpublished until both whole files validate. Repeated completion of that same
session returns its existing saved record; a different pair under the same
identity is rejected rather than overwritten. The source registry reserves
`saved-` IDs for READY managed pairs. No browser/API upload route is exposed by
this command layer alone. Deletion first hides a saved pair as `DELETING`, then
removes the managed bytes and writes a minimal audit event. A failed filesystem
deletion leaves a hidden tombstone for an authorized retry or operational
reconciliation; it must never reappear as a READY source automatically.
