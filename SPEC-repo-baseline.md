# Spec: Repository baseline

Status: Draft for review

Module: `repo-baseline`

## Objective

Create a reproducible, privacy-safe development baseline before changing PRONTO behavior. A new contributor must be able to set up one isolated environment, run focused unit tests and the existing full fixture flow, and understand which data may be committed.

The existing PPTX/DOCX behavior remains unchanged in this module.

## Tech Stack

- Python 3.14, matching the current Dockerfile and CI baseline.
- `venv` plus pinned requirement files initially; packaging consolidation may follow in a separate reviewed change.
- `pytest` for unit and contract tests.
- Docker for the existing OUS/HUS full-flow checks.
- No Node dependency is required for the baseline.

## Commands

Target commands after this module is implemented:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-test.txt
.\.venv\Scripts\python -m pytest -q
docker build -t pronto:baseline .
```

CI must run the equivalent pytest and Docker fixture commands on pull requests and pushes to `main`.

## Project Structure

```text
pronto/                 existing reusable Python code
pronto/tests/           existing and new focused tests
test_data/              approved public fixtures only
docs/                   discovery, privacy, and contributor documentation
tasks/                  approved plans and task state
```

## Code Style

New Python code uses four spaces, type hints at public boundaries, `pathlib.Path` for paths, descriptive names, and narrow exception handling.

```python
def load_fixture(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Fixture does not exist: {path.name}")
    return path.read_text(encoding="utf-8")
```

## Testing Strategy

- Existing unit tests must run in a clean environment.
- Windows and Linux path assertions compare normalized paths, not raw separators.
- The existing OUS and HUS fixture flows remain the integration baseline.
- New checks must fail clearly when a required dependency or fixture is absent.

## Privacy and Trust Boundaries

- Only fixtures already public or explicitly approved as non-sensitive may enter Git.
- Generated HTML, Office documents, screenshots, extracted images, and unique local data remain outside Git until classified.
- Test and application logs must not contain full clinical records.
- Local file paths and uploaded/imported content are untrusted input.

## Boundaries

- Always: use isolated environments; run tests before commits; keep public fixtures de-identified; preserve existing report behavior.
- Ask first: add dependencies; change Python/Docker versions; add or replace fixture datasets; modify CI secrets or publication behavior.
- Never: commit patient data, secrets, local generated reports, or environment directories; delete or weaken existing tests to obtain a green run.

## Success Criteria

- A documented clean setup runs the unit suite without manual `PYTHONPATH` changes.
- Pull requests run unit tests and build/run the approved fixture path without publishing an image.
- The fixture/privacy policy identifies the authoritative approved dataset and exclusions.
- `main` behavior and generated PPTX/DOCX output are unchanged.

## Open Questions

- Should Python 3.14 remain the only supported version, or should CI include the latest supported Python used at each InPreD node?
- Who has authority to approve a local artifact as non-sensitive and suitable for the public repository?
