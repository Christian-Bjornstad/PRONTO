# Integrated review and PDF exports

The report workspace uses a single explicitly saved working copy for small
variants, CNV, RNA, QC, free text and presentation figures. Old revisions stay
immutable. Opening a legacy DRAFT offers a v3 working copy; Save persists that
upgrade before signing or exporting.

- Small variants: full source columns in Details and the complete table;
  Review = Benign / VUS / Oncogenic, Exclude, and Report highlight. VUS in Key
  findings mirrors Review. Legacy Pathogenic/Other labels remain read-only.
- CNV review: complete source table with independent inclusion and highlights;
  Table / Plots views, B3 above C1 initially, then individual panels and Cancan.
- RNA review: complete fusion/splice source table and domain plots. Spreadsheet
  QC highlights remain separate from manual report selection.
- Highlights are **Key relevant findings**. Exclude always overrides highlight;
  classifying a variant does not automatically include or exclude it.
- Five manual, linked QC assessments: small variants, CNV, RNA, signatures and
  overall. Green/Pass, Orange/Conditional, Red/Fail and neutral/Not reviewed.
- TMB, MSI and HRD display their score and ranges. Ranges describe the display,
  not clinical thresholds. Missing HRD is unavailable. Only the explicitly
  enriched demonstration supplies the example HRD score 42.
- Report page: manual history, summary, therapeutic context, variant description,
  clinical actionability, trials, follow-up, methods, references, patient details
  and additional comments. This does not infer clinical evidence or treatment.

## Saved outputs

**Presentation PDF** is landscape A4 with a patient sidebar, Key relevant
findings and a compact variant table. Additional selected CNV/RNA and free text
continue on subsequent landscape pages when needed. **ESMO PDF** is portrait A4
with Summary, Results and Key relevant findings / clinical evidence sections.
Both approximate the supplied screenshots; there is no editable source template.
Long text/tables continue rather than being clipped. Both contain the saved
selection, saved corrections, QC, ranges, DRAFT/FINAL status, revision and export
initials. Existing offline HTML downloads also accept v3 snapshots.

Export requires Save first and self-reported initials. The backend validates
access, CSRF and the saved revision and records a transactional PDF audit. Retry
of the same request ID uses the same snapshot; changing its identity conflicts.

**Presentation figures** accepts PNG, JPEG and WebP, previews each figure and
supports captions, ordering and removal from the selected list. Save records
the selection, captions and order. Figures appear only at the very end of the
landscape PDF, never in ESMO. Images are decoded and re-encoded to PNG, stripped
of original metadata, bounded to 8 MB, and stored privately
with report authorization. Up to 30 figures can be selected; immutable assets
remain available to earlier revisions after removal from a later selection.
Uploads have a per-report 64 MB / 100-asset quota. Source images up to 64 million
pixels are accepted to accommodate high-resolution scientific plots such as the
provided Cancan image (7500 × 6600). They are scaled proportionally to at most
16 million stored pixels and flattened onto the PDF's white background.

## Patient overview and history

`/` and `/reports/` list authorized reports, 25 per page, with patient/sample,
tumour type, status and save time. Seeding alone is `un-reviewed`; a SAVE_DRAFT
audit produces `under-review`; FINAL produces `reviewed`. Open report selects
the latest snapshot. Saved version opens `?revision=N`, a read-only view without
save/finalization/upload endpoints. Missing or unauthorized revisions return 404.

## Explicit local mixed-sample demonstration

Do not commit `info/` inputs or generated patient PDFs. To start a separate new
loopback demonstration database:

```powershell
$env:PRONTO_DJANGO_SECRET_KEY = '<local secret>'
python manage.py run_demo --database new-integrated.demo.sqlite3 --report demo-integrated-review --port 8770 --supplementary-demo-dir 'C:/Users/molpa/Documents/Inpred/info'
```

This imports the existing approved variant fixture plus the provided CNV CSV,
RNA XLSX, Cancan image and domain PDFs, explicitly marked as mixed-sample demo.
The RNA sample mismatch and plot/Event_ID mismatch are retained; approximate
filenames never establish patient or variant matching. Existing databases are
refused by run_demo. Restart with `resume_demo` to preserve saved revisions.

Install `requirements.txt` and `requirements-test.txt`; browser checks additionally
use `requirements-browser.txt`. PDF plot display uses the existing Poppler
dependency. The generated report PDFs themselves use ReportLab.
