# PPTX and HTML report parity

The approved OUS fixture contains a 12-slide legacy PPTX and the source files
used by the new `ReportData` adapter. The HTML report is a new presentation of
the validated contract, not a pixel-by-pixel copy of the presentation.

| Fact or surface | Legacy PPTX | Standalone HTML |
| --- | --- | --- |
| Patient pseudonym | `MRARE-X-xxxx` | Same contract value |
| TMB | `TMB = 14.9 (19)` | `14,9 mut/Mb`; raw source value retained in `ReportData` |
| MSI | `MSI = 4.13 (5/121)` | `4,13 %`; raw source value retained in `ReportData` |
| Variants | Selected slide presentation | All 30 source occurrences, including both TERT occurrences, with searchable table |
| CNV and QC plots | Embedded or linked slide visuals | Hash-verified attachments rasterized and embedded as data URIs |
| Review decisions | Legacy presentation workflow | Separate `ReviewState` contract; no decision inferred from a PPTX slide |

The adapter deliberately does not infer clinical diagnosis, tumour type, QC
thresholds, or final clinical decisions from slide layout or metadata. Missing
structured fields are shown explicitly. HTML `FINAL` is read-only and displays
review finalization details. The live Django report saves drafts explicitly to
the database; standalone working copies require downloading the updated
`ReviewState`. The HTML export contains no remote fonts, scripts, stylesheets,
or image requests.

Export from validated JSON with `python -m pronto_report.cli render-html
report-data.json --asset-root PATH_TO_SOURCE_ROOT --output report.html`. The
asset root is the directory against which declared relative attachment paths
are resolved; if omitted, it defaults to the JSON file's directory. Every
declared plot attachment must exist and match its recorded SHA-256 digest.
PDF plots require Poppler (`pdftoppm`/`pdfinfo`) on `PATH`, as in the existing
PRONTO PDF workflow. A separate `--review review-state.json` can be supplied;
the report and review IDs must match.

Run `python -m pytest -q pronto/tests/reporting` for contract, parity, and
browser checks. The browser checks require `requirements-browser.txt` and a
local Chrome/Edge/Chromium executable; set `PRONTO_BROWSER_EXECUTABLE` if it is
not in a standard location. Print CSS is verified by Chromium's print-media
emulation and PDF generation.

## Tumour-board export parity

Included findings carry their review comment and the same readable clinical
classification label in the live page, server rendering and read-only HTML
snapshot. Duplicate occurrences are listed once; excluded variant comments are
not included in the tumour-board section. Comments are HTML-escaped. A browser
PDF regression test verifies that the comment survives read-only export/print.

## Demo variant population

The original local prototype builder takes its variant rows from
`extra_files/*_preMTB_workingTable.txt`, enriching them with judgment fields from
`*_small_variant_table_forQC.tsv`. The current pipeline adapter instead prefers
the full `*_small_variant_table_forQC.tsv` (falling back to the small-variant
table). For the approved IPD2225-D01-P01-A08 demo, this gives 24 occurrences
(23 unique variants) in the prototype versus 30 (29 unique) in the adapter.
Both contain a duplicate TERT occurrence. The six additional rows are CHEK2,
PREX2, DNMT3A, CDKN2A, KMT2B and PRKDC. This is a source-population difference,
not evidence that those rows should automatically be excluded. Review selection
remains explicit; no clinical filter rule has been inferred from the prototype.
