# Spec: Report data contract

Status: Approved for implementation

Module: `report-data-contract`

Depends on: `repo-baseline`

## Objective

Define one versioned, validated, report-neutral contract between PRONTO calculations and every output surface. PPTX, self-contained HTML, Django, JSON export, and tests must consume the same `ReportData`; review activity must be stored separately as `ReviewState`.

The contract must preserve source facts, record provenance, and make user corrections explicit rather than silently overwriting calculated values.

## Tech Stack

- Python dataclasses or typed model classes for the in-process domain model.
- JSON Schema 2020-12 files as the language-neutral serialized contract.
- Standard JSON serialization with deterministic key ordering for fixtures and hashes.
- `jsonschema==4.26.0` validates Draft 2020-12 contracts; `rfc3339-validator==0.1.4` enables timestamp format assertions.

The schemas validate `reportId` independently. Equality between `ReportData.reportId` and `ReviewState.reportId` is a cross-document invariant enforced by the Task 6 boundary validator, because JSON Schema 2020-12 does not compare arbitrary values across separate instances.

## Contract Limits

| Area | v1 limit |
|---|---:|
| Variants and variant reviews | 10,000 |
| Attachments and source files | 100 each |
| Diagnostics and value corrections | 1,000 each |
| QC metrics | 500 |
| Biomarkers | 100 |
| Report notes | 50,000 characters |
| General comments/reasons | 10,000 characters |

Nested contract objects are closed with `additionalProperties: false`. Correction values and source raw values are scalar-only, so imported documents cannot create unbounded recursive object trees.

## Commands

Target commands after implementation:

```powershell
.\.venv\Scripts\python -m pytest -q pronto\tests\reporting
.\.venv\Scripts\python -m pronto_report.cli validate test_data\report-data.json
.\.venv\Scripts\python -m pronto_report.cli export --fixture ous --output Out\report-data.json
```

## Project Structure

```text
pronto_report/
  __init__.py
  models.py               typed ReportData and ReviewState models
  validation.py           boundary validation and structured errors
  serialization.py        deterministic JSON input/output
  identity.py             stable report and variant identifiers
  schemas/
    report-data-v1.schema.json
    review-state-v1.schema.json
pronto/tests/reporting/
  test_models.py
  test_validation.py
  test_serialization.py
  fixtures/
```

## Contract Outline

`ReportData` contains immutable or source-derived facts:

```text
schemaVersion
reportId
sample + patient pseudonym
run + generator provenance
source file hashes
biomarkers and QC values with units, thresholds, status, and source
variants with stable variantId and source annotations
plots/attachments as named assets with hashes and media types
warnings and missing-data diagnostics
```

`ReviewState` contains human activity and overrides:

```text
schemaVersion
reportId
revision
status: DRAFT | FINAL
reviewer and timestamps
per-variant reportingDecision: UNREVIEWED | INCLUDE | EXCLUDE
per-variant clinicalClassification: UNCLASSIFIED | PATHOGENIC | UNCERTAIN | OTHER
IGV/run-QC assessments and comments
report notes
explicit valueCorrections with original value, corrected value, reason, author, and time
```

Reporting decision and clinical classification are separate dimensions. The current prototype's `INC`, `EXC`, `PATH`, and `UNS` values must not remain one mutually exclusive field.

## Identity Rules

- `reportId` is stable for one logical sample/run/report generation context.
- `variantId` is derived from normalized sample ID, reference build, chromosome, position, reference allele, and alternate allele when available.
- A fallback identity may use the current sample/gene/location/change tuple but must emit a warning and cannot be treated as collision-proof.
- Duplicate source rows remain representable and receive distinct occurrence identifiers; validation reports duplicates rather than silently dropping them.

## Error Contract

Every validation failure uses one predictable shape:

```json
{
  "code": "INVALID_REPORT_DATA",
  "message": "Report data did not pass validation",
  "issues": [
    {"path": "variants[2].variantId", "code": "DUPLICATE_ID", "message": "Variant ID must be unique"}
  ]
}
```

Internal stack traces and file contents are never included in user-facing errors.

## Testing Strategy

- RED/GREEN unit tests for every validation rule and migration rule.
- Round-trip tests prove serialized JSON loads without semantic change.
- Golden fixtures cover OUS and HUS layouts, tumour-only and matched-normal cases, missing metadata, empty variant sets, duplicate variants, and missing plots.
- Contract tests compare the key values consumed by PPTX and HTML.
- Malicious strings are rendered as text and never executed as HTML or script.

## Security and Privacy

- Validate imported JSON before use; reject unknown major schema versions.
- Set explicit size, nesting, string-length, variant-count, and attachment-count limits.
- Hash provenance files without embedding their unrestricted contents.
- Minimize direct identifiers; use a pseudonymous patient/case key in the contract.
- Never use imported strings with `innerHTML`, `eval`, shell commands, SQL, or filesystem paths.
- FINAL review state is immutable; reopening creates a new audited revision rather than modifying history in place.

## Boundaries

- Always: validate at import/export boundaries; preserve raw source values and provenance; escape display strings; use stable IDs; keep review state separate.
- Ask first: add direct personal identifiers; change a field's meaning or type; accept a new upload type; introduce a new external data source.
- Never: silently coerce ambiguous clinical values; overwrite calculated source facts with browser edits; load mismatched sample/run state after a warning-only prompt; remove fields from v1 without a migration.

## Success Criteria

- Both schemas reject malformed, mismatched, oversized, and unsupported input with structured issues.
- One approved fixture serializes deterministically and round-trips without loss.
- Duplicate TERT-like source rows are detected and remain traceable.
- Reporting decisions and clinical classifications can vary independently.
- The contract contains no hard-coded report year, pipeline version, QC value, TMB, MSI status, or hospital.

## Open Questions

- Which genome builds must v1 support and how should build be obtained when absent?
- Which identifiers are permitted in the public fixture versus restricted deployments?
- Should FINAL state require one reviewer or independent reviewer/finalizer roles?
