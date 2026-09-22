# Approved OUS ReportData fixture mapping

Date: 2026-09-22

## Source fixture

Task 9 uses the already approved public OUS fixture at:

```text
test_data/ous/251114_A02134_0115_BHCJCKDRX7_TSO_500_LocalApp_postprocessing_results
```

The selected DNA sample is `IPD2225-D01-P01-A08` from run `251114_A02134_0115_BHCJCKDRX7`. The adapter reads four declared TSV sources and exposes three hashed plot assets. Only repository-relative names, media types, byte sizes, and SHA-256 hashes enter provenance; local absolute paths and unrestricted source contents do not.

## Verified mapping

| Contract value | Source value |
|---|---|
| Reference build | `hg19` source declaration, normalized to `GRCh37` |
| TMB | `14.9 (19)`; numeric value `14.9 mut/Mb` plus raw provenance |
| MSI | `4.13 (5/121)`; numeric value `4.13 %` plus raw provenance |
| Variant occurrences | 30 source rows |
| Duplicate example | Two TERT `5:1295228 G>A` occurrences share one `variantId` and retain different `occurrenceId` values |
| Assets | One CNV PDF and two sample-QC PNG files |

No TMB/MSI category, clinical diagnosis, tumour type, structured QC metric, report year, hospital, or pipeline version is invented when absent from the selected source fields. Missing clinical diagnosis and structured QC are emitted as `MISSING_CLINICAL_DIAGNOSIS` and `MISSING_STRUCTURED_QC` diagnostics.

## Comparison with the local HTML prototype

The local prototype's `report_data.json` displays 24 variants, while the source table contains 30. The v1 contract intentionally preserves all 30 source occurrences: filtering and review visibility are downstream presentation/review concerns, and silently dropping six rows would break provenance. The prototype's TMB `14.9 (19)` and MSI `4.13 (5/121)` agree with the contract mapping.

Values present only in the prototype—including a LocalApp TMB of `21`, derived TMB/MSI labels, detailed QC cards, report date, tumour type, and sample type/material—are not copied into the contract because discovery identified them as hard-coded or not traceable to the four selected source files.

## Reproduction

```powershell
.\.venv\Scripts\python -m pronto_report.cli export `
  --fixture ous `
  --generated-at 2026-09-22T12:00:00Z `
  --output Out\report-data.json
```

For the same committed inputs, generator version, and declared timestamp, repeated exports are byte-identical and validate through the ReportData v1 boundary.
