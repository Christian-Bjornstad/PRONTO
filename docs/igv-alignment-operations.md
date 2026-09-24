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
