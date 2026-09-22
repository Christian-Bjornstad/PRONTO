# Contributing to PRONTO

## Development baseline

PRONTO currently targets Python 3.14, matching the Docker image and CI workflow. Use an isolated virtual environment; do not install project dependencies into a shared system Python.

## Windows setup

List installed Python runtimes and select a 3.14 interpreter:

```powershell
py -0p
py -3.14 -m venv .venv
```

Some `uv`-managed Python installations are exposed through a named launcher tag instead of `-3.14`. In that case, use the exact 3.14 tag shown by `py -0p`, for example:

```powershell
py -V:Astral/CPython3.14.0 -m venv .venv
```

Install the runtime and test dependencies, then run the unit suite:

```powershell
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-test.txt
.\.venv\Scripts\python -m pytest -q
```

## Linux and macOS setup

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt -r requirements-test.txt
.venv/bin/python -m pytest -q
```

## Docker fixture verification

Build the same runtime used for the full OUS/HUS fixture flow:

```bash
docker build -t pronto:baseline .
```

The authoritative full-flow commands are maintained in `.github/workflows/test.yml`. Run them before changing parsing, calculations, report generation, configuration, or fixture data.

## Test conventions

- Run a focused test during the RED/GREEN loop, then the full unit suite before committing.
- Compare filesystem paths semantically with `pathlib.Path`; do not assert operating-system-specific separators.
- Do not skip, delete, or weaken a failing test to make a change pass.
- Add tests for every behavior change and regression fix.

## Data and generated files

The committed `test_data/` files are approved public fixtures. New fixtures require explicit owner approval before they are staged.

Do not commit:

- patient or otherwise sensitive data;
- locally generated reports or review-state exports;
- virtual environments, caches, build output, or secrets;
- local Office files, screenshots, or extracted derivatives unless they have been explicitly approved as a fixture.

Before every commit, inspect the staged file list and diff:

```bash
git diff --cached --name-status
git diff --cached
```

## Branch and commit workflow

Create short-lived branches from current upstream `main`. Keep commits focused and use descriptive messages such as `test: normalize cross-platform path assertions` or `feat: add report data validation`.

The fork remotes are expected to be:

```text
origin    https://github.com/Christian-Bjornstad/PRONTO.git
upstream  https://github.com/InPreD/PRONTO.git
```
