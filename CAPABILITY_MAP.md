# Capability Map: PRONTO HTML and Django evolution

Status: Draft for review. This map defines boundaries and build order; it is not yet an implementation specification.

## Objective

Evolve PRONTO from a PowerPoint-only report generator into a report pipeline with a versioned, report-neutral data model, parallel PPTX and HTML outputs, and an optional Django-based review application for validated input, persistence, access control, and audited output.

## Modules

| Module id | Responsibility | Depends on |
|---|---|---|
| `repo-baseline` | Reproducible environment, current tests, fixture classification, privacy rules, and CI baseline | — |
| `report-data-contract` | Typed and versioned report data, review state, provenance, validation, and serialization | `repo-baseline` |
| `renderer-parity` | Preserve existing PRONTO calculations and PPTX output while making both renderers consume the same report data | `report-data-contract` |
| `html-renderer` | Generate accessible, self-contained or hosted HTML without duplicating clinical rules in JavaScript | `report-data-contract`, `renderer-parity` |
| `review-workflow` | Variant review, comments, draft/final state, optimistic locking, and immutable export semantics | `report-data-contract`, `html-renderer` |
| `django-application` | Server-side forms, file import, authentication/authorization, persistence, audit events, and controlled report download | `report-data-contract`, `review-workflow` |
| `clinical-verification` | Fixture matrix, PPTX/HTML parity checks, browser/accessibility checks, security review, and user acceptance | all preceding modules |

## Dependency flow

```text
repo-baseline
    |
report-data-contract
    |
renderer-parity ----> html-renderer
                           |
                    review-workflow
                           |
                   django-application
                           |
                  clinical-verification
```

## Proposed build order

1. Establish `repo-baseline` and classify every local artifact before copying anything into the public repository.
2. Specify `report-data-contract`; PRONTO should emit validated JSON with schema version and provenance.
3. Introduce `renderer-parity`; keep PPTX as the reference output while separating calculations from layout.
4. Integrate the existing prototype as `html-renderer` and replace its hard-coded and duplicated clinical values.
5. Specify `review-workflow`, including draft/final behavior and conflict handling.
6. Build a narrow `django-application` vertical slice: import one non-sensitive fixture, review one case, save state, and export HTML/JSON.
7. Expand `clinical-verification` before any use with sensitive or clinical data.

## Architectural position on Django

Django is not required merely to generate HTML. It becomes valuable when PRONTO must accept structured user input and files, validate and persist review state, enforce permissions, keep an audit trail, and produce controlled downloads. The initial renderer should therefore remain usable from the command line, while Django calls the same application/service layer rather than reimplementing report logic.

## Boundary contracts to specify next

- `report-data-contract` provides `ReportData` and `ReviewState` schemas to every renderer and application.
- `renderer-parity` defines which calculated fields and included rows must match between PPTX and HTML.
- `review-workflow` defines state transitions and write-conflict behavior; Django only transports and persists them.
- `django-application` owns HTTP, forms, sessions, permissions, storage adapters, and downloads, but not clinical calculations.

## Decisions required before module specifications

1. Is HTML initially a review tool, the final clinical report, an MDT presentation, or a combination with distinct finalization rules?
2. Is the first deployment single-user/local, shared file storage, or a centrally hosted application?
3. Which user roles may view, edit, finalize, reopen, and export a case?
4. What is the authoritative record: PRONTO output files, review JSON, a database record, or a finalized signed artifact?
5. Which local fixtures are confirmed non-sensitive and approved for the public repository?
6. Must PPTX remain a supported output throughout the transition?
