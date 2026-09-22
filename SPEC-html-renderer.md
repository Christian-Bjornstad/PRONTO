# Spec: HTML renderer and review surface

Status: Draft for review

Module: `html-renderer`

Depends on: `report-data-contract`, `renderer-parity`

## Objective

Rebuild the HTML report from clean source files while preserving the successful visual language and workflow of the local `report.html`. The existing report is the reference for information hierarchy and user flow, not a source file to copy wholesale.

The first renderer remains usable without Django. It accepts validated `ReportData` plus optional validated `ReviewState` and can produce a self-contained HTML artifact. Django will later reuse the same templates, presentation models, and domain services.

## Reference Experience to Preserve

- InPreD blue header with clear sample and draft/final status.
- Five primary surfaces: Key findings, Variant review, CNV plots, Sequencing QC, and Tumour board report.
- Dense, searchable variant workflow with visible progress.
- Fast CNV plot switching and enlargement.
- QC status tiles plus the source plot.
- Separate MDT notes/sign-off and print-oriented output.
- Offline-capable self-contained export when required.

## Problems to Correct

- Separate HTML, CSS, JavaScript, templates, and data during development; bundle only at export time.
- No hard-coded clinical or pipeline values.
- No clinical calculations duplicated in browser JavaScript.
- No silent localStorage fallback for authoritative state.
- Remove whole-page horizontal overflow at narrow widths.
- Format numeric values intentionally instead of exposing floating-point artifacts.
- Use stable variant IDs rather than a delimiter-joined key.
- Separate reporting decision from clinical classification.
- Validate imported state strictly; a mismatched report ID is an error, not a bypassable confirmation.
- FINAL must lock editing and display provenance/finalization status unmistakably.

## Tech Stack

- Server-renderable HTML templates compatible with Django's template engine.
- Plain, modular JavaScript for focused interactions; no frontend framework until the workflow proves it is necessary.
- CSS custom properties for the design system; no external font or CDN requirement.
- Python bundler/renderer for self-contained export.
- Browser tests against managed Chromium/Edge behavior.

## Commands

Target commands after implementation:

```powershell
.\.venv\Scripts\python -m pytest -q pronto\tests\reporting\test_html_renderer.py
.\.venv\Scripts\python -m pronto_report.cli render-html test_data\report-data.json --output Out\report.html
.\.venv\Scripts\python -m http.server 8765 --directory Out
```

## Project Structure

```text
pronto_report/
  renderers/
    html.py
  templates/
    report/
      base.html
      key-findings.html
      variant-review.html
      cnv-plots.html
      sequencing-qc.html
      tumour-board.html
  static/
    report.css
    report.js
pronto/tests/reporting/
  test_html_renderer.py
  browser/
```

## Design System

- Preserve the current blue, pale-blue, white, green, amber, and red semantic family.
- Use blue for navigation/identity; green for successful QC and inclusion; amber for draft/warning; red for destructive/error/exclusion.
- Status must always include text or an icon in addition to color.
- Use a system sans-serif for UI and a system monospace for identifiers/numeric data; no external font request.
- Dense desktop table remains the primary review experience.
- At narrow widths, keep the page itself fixed to the viewport and allow only the variant table to scroll horizontally, with frozen identifying columns where practical.
- Minimum interactive target is 44×44 CSS pixels on touch-oriented widths; desktop table controls may be compact when keyboard focus remains clear.
- Motion is limited to 150–200 ms state transitions and respects `prefers-reduced-motion`.

The generated design-system search suggested blue/neutral operations colors and dense analytics typography. Its landing-page, oversized-type, external-font, and decorative-animation suggestions are explicitly rejected as unsuitable for a clinical review tool.

## Accessibility and Interaction

- WCAG 2.1 AA contrast and visible focus states.
- Tabs support arrow-key navigation and correct `aria-controls`/`aria-labelledby` relationships.
- Search and filters have visible labels or accessible names.
- Sorting uses buttons with announced direction, not click-only table headers.
- Review progress and save/finalization feedback use appropriate live regions.
- Dialog/lightbox focus is trapped and returned to its trigger on close.
- Every plot has a meaningful caption and a text alternative describing its role.
- Loading, missing-data, empty-variant, and validation-error states are explicit.

## Testing Strategy

- Unit tests assert escaped output, required landmarks, headings, field formatting, and empty/error states.
- Contract tests render the approved fixture and compare key displayed values to `ReportData`.
- Browser tests cover tab keyboard behavior, filtering, sorting, review edits, CNV switching, focus return, print mode, and FINAL locking.
- Responsive checks cover 375, 768, 1024, and 1440 CSS-pixel widths with no whole-page horizontal overflow.
- Browser console must have zero errors and warnings.
- Self-contained export must make no external network request.

## Boundaries

- Always: render only validated contract data; escape content by default; preserve the five-surface workflow; verify in a real browser; keep the source modular.
- Ask first: remove an existing workflow surface; introduce a frontend framework; load an external font/script; make HTML the authoritative clinical artifact.
- Never: parse PPTX as the HTML data source; implement clinical thresholds only in JavaScript; embed unclassified local artifacts; treat localStorage as the clinical record.

## Success Criteria

- An approved fixture renders all five surfaces from `ReportData` without hard-coded values.
- The visual hierarchy is recognizably based on the current local report.
- Browser interaction and accessibility checks pass at the four target widths.
- Review status and classification are independently editable and persist through `ReviewState`.
- HTML export is self-contained, deterministic apart from declared timestamps, and contains provenance.
- Existing PPTX generation remains available throughout validation.

## Open Questions

- Is the minimum supported narrow width 768 px for a managed desktop environment, or must phone-sized review be fully supported?
- Should the self-contained artifact include editable review controls, or should finalized exports be read-only?
- Which plot descriptions can be generated automatically and which require domain-authored text?
