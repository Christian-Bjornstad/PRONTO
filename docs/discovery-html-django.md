# Discovery: local HTML work, PRONTO, and Django

Date: 2026-09-22

## Repository and branch state

- The working repository is the `repos/PRONTO` checkout in the local research workspace.
- `origin` is the writable fork, `https://github.com/Christian-Bjornstad/PRONTO.git`.
- `upstream` is the canonical repository, `https://github.com/InPreD/PRONTO.git`.
- Both linked GitHub repositories currently resolve `main` to commit `d20a6ba`.
- GitHub identifies `Christian-Bjornstad/PRONTO` as a fork of `InPreD/PRONTO`, not the reverse.
- The local `main` was at `872a1bd`; this discovery branch was created from current `origin/main` as `feature/html-reporting-foundation`.
- The remotes use the conventional fork layout even while both `main` tips are identical: feature branches push to `origin`, while updates are fetched from `upstream`.

## Existing PRONTO architecture

PRONTO reads TSOPPI/TSO500 files plus clinical metadata and configuration, performs filtering and calculations, and creates PPTX, DOCX, and intermediate text outputs. The implementation is dominated by `Script/PRONTO.py`, with reusable helpers in `pronto/pronto.py` and tests in `pronto/tests/pronto_test.py`.

The key modernization constraint is that input parsing, calculations, state mutation, and PPTX layout are still coupled. Adding a second renderer directly to the procedural script would duplicate clinical behavior and make parity difficult to prove.

## Existing local HTML prototype

The local prototype is substantive and already demonstrates:

- a self-contained HTML report;
- variant filtering and review controls;
- editable case fields and metrics;
- CNV and QC images;
- JSON import/export and browser-local draft state;
- draft/final presentation and an MDT-oriented view.

The builder successfully generated a 2.1 MiB report with 24 variants, 9 CNV images, and a QC image. Its textual smoke test currently reports 19 passing and 3 failing assertions. The three failures appear to be brittle source-text assertions rather than proof of three runtime regressions, so browser-level tests are needed.

## Prototype gaps that block integration

- `build_report.py` parses generated PRONTO files directly instead of consuming a stable contract.
- It contains hard-coded values, including the current-year age calculation, pipeline text, QC metrics, LocalApp TMB, MSI status, and report date.
- Clinical/presentation rules such as TMB level are duplicated outside PRONTO.
- `report_data.json` has no declared schema version or provenance contract.
- Browser `localStorage` is suitable for a demo draft, not an authoritative shared or clinical record.
- Import, identity matching, concurrency, audit, finalization, and access control are not yet specified.

## Local artifact inventory

The workspace root contains several distinct classes of material:

| Area | Role | Initial handling |
|---|---|---|
| `repos/PRONTO` | Public Git repository | Safe place for reviewed code, docs, and approved fixtures |
| `prototype` | HTML template, builder, data, images, smoke test | Candidate source; review and sanitize before copying |
| `PRONTO/test_data_none_sensitive` | Claimed non-sensitive source fixtures | Verify provenance and approval before public commit |
| `PRONTO/output_version_*` | Generated comparison outputs | Keep outside Git unless a minimal golden fixture is approved |
| `inpred` | Office files and screenshots supplied locally | Treat as restricted until explicitly classified |
| `extracted` | Derived images and JSON from local artifacts | Regenerable; do not bulk-copy into Git |
| root Markdown files | Research, meeting notes, and architecture drafts | Consolidate selected durable decisions; do not copy historical contradictions blindly |

Several local source files are byte-identical to already public repository fixtures, but generated reports and extracted derivatives are mostly unique. Uniqueness is not evidence of sensitivity; nevertheless, nothing unique should enter the public repository until its provenance and de-identification are confirmed.

## Django assessment

Django fits the stated need for information both into and out of the report when the scope includes validated forms, uploaded files, persistent review state, authentication/permissions, audit events, and controlled exports. It should wrap a report-neutral Python service rather than own PRONTO's calculations.

A useful first vertical slice is deliberately small:

1. Import one approved non-sensitive PRONTO fixture.
2. Validate it into `ReportData`.
3. Render the existing HTML view server-side.
4. Submit one variant review with a Django form.
5. Persist versioned `ReviewState` with reviewer and timestamps.
6. Export validated JSON and HTML while leaving the PPTX path intact.

For a stability-oriented deployment, Django 5.2 LTS remains a reasonable candidate because it receives security and data-loss fixes through April 2028. The exact framework/Python version should be decided in the `django-application` specification together with the hosting environment.

## Baseline verification

- `python -m pytest -q` did not collect tests in the active local Python because `python-pptx` is not installed.
- The prototype builder completed successfully when pointed at the local v3.0.0 output.
- `node _smoke_test.js` reported 19 passed and 3 failed source-text assertions.

The first implementation task must create a documented, isolated environment and turn these checks into repeatable commands before behavior is changed.

## Immediate recommendation

Do not begin by scaffolding Django or moving all local files into the repository. Approve the capability map first, then specify and implement `repo-baseline` and `report-data-contract`. This gives both PPTX and HTML a shared foundation and keeps Django from becoming a second implementation of PRONTO.
