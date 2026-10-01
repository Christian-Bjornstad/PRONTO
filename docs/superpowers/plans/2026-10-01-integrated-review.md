# Integrated review implementation plan

> For agentic workers: use superpowers:executing-plans task by task, with a fresh whole-branch review before merge.

**Goal:** Deliver variant/CNV/RNA review, linked QC, two PDF formats and authorized patient/revision navigation.
**Architecture:** Versioned immutable source/review contracts, shared export projection, focused UI extension and Django adapters.
**Tech Stack:** Python 3.14, Django 5.2, JSON Schema, vanilla JS/CSS, openpyxl, ReportLab, pytest/Playwright.
**Spec:** [Integrated review design](../specs/2026-10-01-integrated-review-design.md)

## Global constraints

Keep source facts, review history, explicit Save and FINAL locks. English
product copy. Local patient inputs/assets stay outside Git. Test with synthetic
data and existing approved fixtures. Use the existing isolated worktree on a
new feature branch. Owner has authorized push/PR/merge after checks and review.

## Review focus

Duplicate variants; source/human QC distinction; mixed-sample demo provenance;
long PDF text/tables; stale/unauthorized history and export requests.

## Tasks

1. [x] Contracts/migration: add ReportData v2 sourceTables and measurement
   metadata; ReviewState v3 classifications/highlights/findingReviews/sectionQc
   and notes. RED/GREEN migration/round-trip/invalid ID/save/reset tests.
2. [x] Source adapters: complete variant TSV columns; CNV semicolon/preamble
   and RNA XLSX/header/empty/formula/highlight preservation. Test synthetic
   columns, duplicate headers, limits and source values. Add explicit local
   supplementary demo loading with no data files in Git.
3. [x] UI: variant Review/VUS/Exclude/highlight, CNV Table/Plots B3+C1 and RNA
   full table/gallery. Link all section QC and notes in working copy; verify
   Save/reload, duplicate IDs, FINAL and responsive/browser behavior.
4. [x] PDF: shared saved-revision projection and ReportLab landscape/portrait
   renderers, pagination, source ranges/corrections, Key relevant findings and
   all report free text. Verify actual PDF content/sizes/long rows and images.
5. [x] Export adapter: versioned request, PDF audit migration, revision/CSRF/
   access checks, idempotent retry and two download buttons. RED/GREEN HTTP
   and browser save-first/error/download tests; keep historical HTML route.
6. [x] Index/history: authorized paginated report list, status from saved
   audits/FINAL, summary and revision dropdown; historical read-only view and
   export tied to requested saved revision. Test grants/status/stale IDs.
7. [ ] Integration: run full suites on project Python 3.14, address existing
   obsolete translation assertions explicitly, inspect demo/PDF in real browser,
   independent review, fix findings, commit/push/PR/merge into maintained base.

Upload follow-up is part of tasks 1/3/4/5: immutable private raster assets, revisioned captions/order, presentation-only appendix and bounded upload authorization.

## Files and interfaces

`models.py`/schemas/serialization/validation/migration own contracts;
`review/service.py` validates CNV/RNA/metric references and persists v3.
`adapters/source_tables.py` reads complete local tables. `renderers/review_v3.py`
owns new UI markup; core HTML/JS retains save/IGV. `renderers/report_pdf.py`
projects saved snapshots and renders PDF bytes. `reports/pdf_exports.py`
owns the authorized export. `reports/index.py` owns list/history queries.

These tasks consume the same ReportData/ReviewState objects; no second storage
system, client-generated report, external annotation lookup or fabricated
clinical evidence. Completion evidence is kept in this plan's ignored ledger.
