# Fixture and privacy policy

Date: 2026-09-22

## Purpose

PRONTO is a public repository. A file being non-sensitive is necessary but not sufficient for committing it: fixtures must also be intentional, minimal, reproducible, and useful for automated verification. This policy separates approved public fixtures from local source material and generated report artifacts.

## Approved baseline fixtures

The repository owner approved the fixture data already tracked at baseline commit `50cd812`:

- `test_data/hus/**` and `test_data/ous/**`, including their control/sample input files, QC/CNV assets, and the existing expected PPTX output;
- `test_data/InPreD_PRONTO_metadata.txt`;
- `pronto/tests/data/**`, used by the unit tests.

This approval applies only to the files already tracked at that commit. It does not automatically approve new files copied into those directories. The identifiers and assets in the approved fixture set are treated as public test material, not production clinical records.

## What may be committed

- Source code, templates, schemas, tests, and documentation.
- Small deterministic expected outputs when they materially verify behavior and cannot be asserted more clearly in code.
- New synthetic, public control, or de-identified fixtures after the approval process below.
- Generated assets that are explicitly selected as stable golden fixtures and documented as such.

## What stays local by default

| Artifact | Default handling | Exception |
|---|---|---|
| Self-contained HTML reports | Ignore as generated output | Commit only a deliberately reviewed minimal fixture |
| Review-state JSON and browser exports | Ignore as local working state | Commit only synthetic contract examples under a fixture directory |
| Generated PPTX, DOCX, PDF, and spreadsheets | Keep outside Git | Commit only an approved template or golden fixture |
| Screenshots and browser captures | Keep outside Git | Commit only when required for a durable visual regression test |
| Extracted images or JSON derivatives | Regenerate locally | Commit only an approved minimal derivative with provenance |
| Local databases, uploads, logs, caches, and virtual environments | Never commit | None |
| Credentials, tokens, private keys, or environment files | Never commit | A value-free `.env.example` is allowed |
| Patient or other personal data | Never commit to this public repository | None; use an approved restricted system instead |

The workspace-level `report.html`, prototype outputs, `output_version_*` directories, Office files, screenshots, and extracted derivatives described in `docs/discovery-html-django.md` remain local reference material. Their non-sensitive classification does not make bulk versioning useful or appropriate.

## Approval process for a new fixture

The repository owner or a designated data steward must approve each new fixture set in the pull request. The pull request must record:

1. source and provenance;
2. why the fixture is synthetic, public, or sufficiently de-identified;
3. which test requires it and why a smaller fixture is insufficient;
4. expected generated derivatives;
5. the approving owner or data steward.

Before approval, the contributor must inspect both content and metadata. Removing a visible name is not enough: filenames, document properties, image metadata, free text, sample identifiers, embedded attachments, and archive contents must also be considered.

## Staged-data review

Review the exact staged set before every fixture commit:

```bash
git diff --cached --name-status
git diff --cached
git status --short
```

For binary files, record their purpose, provenance, size, and a reproducible inspection method in the pull request. Review generated output against the approved source fixture and confirm that no local path, username, credential, or unintended record was embedded.

If inappropriate data is discovered before push, unstage it and keep it outside the repository. If it has been pushed, stop further distribution and notify the repository owner immediately so removal and any required credential or privacy response can be coordinated.

## Ownership

- Contributors are responsible for reviewing what they stage.
- The repository owner or designated data steward approves new fixture data.
- Code review verifies that the fixture is necessary, bounded, documented, and covered by a test.
- Approval must be renewed when a fixture's contents or provenance change materially.
