"""Install PRONTO in the active Python FELLES 3.14 interpreter, without python.exe."""
from pathlib import Path
import importlib
import os
import site
import sys
import traceback
import tempfile

PROJECT_DIR = Path(__file__).resolve().parent


def add_path(path):
    value = str(path)
    while value in sys.path:
        sys.path.remove(value)
    sys.path.insert(0, value)


def activate_user_site():
    if sys.version_info[:2] != (3, 14):
        raise RuntimeError(f"PRONTO requires Python 3.14; the active version is {sys.version.split()[0]}.")
    user_site = Path(site.getusersitepackages())
    user_site.mkdir(parents=True, exist_ok=True)
    site.addsitedir(str(user_site))
    add_path(user_site)
    return user_site


def record_failure(stage, error):
    print(f"PRONTO could not {stage}: {error}")
    candidates = [Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'share') / 'PRONTO' / 'logs',
                  Path(tempfile.gettempdir()) / 'PRONTO' / 'logs']
    for logs in candidates:
        try:
            logs.mkdir(parents=True, exist_ok=True)
            path = logs / 'bootstrap.log'
            with path.open('a', encoding='utf-8') as output:
                output.write(f'\n{stage}: {type(error).__name__}: {error}\n')
                traceback.print_exception(type(error), error, error.__traceback__, file=output)
            print(f'Feillogg: {path}\nLim denne mappen inn i adressefeltet i Filutforsker:\n{logs}')
            return path
        except OSError:
            continue
    print('Feilloggen kunne ikke lagres. Kopier feildetaljene nedenfor:')
    traceback.print_exception(type(error), error, error.__traceback__, file=sys.stdout)
    return None


def install(*, project_dir=PROJECT_DIR, user_site=None, pip_main=None, importer=importlib.import_module):
    project = Path(project_dir).resolve()
    requirements = project / "requirements-desktop.txt"
    if not requirements.is_file() or not (project / "pronto_desktop").is_dir():
        raise RuntimeError("Cannot find the complete PRONTO project next to this script.")
    package_site = Path(user_site or site.getusersitepackages())
    package_site.mkdir(parents=True, exist_ok=True)
    add_path(package_site)
    if pip_main is None:
        try:
            import pip  # noqa: F401
        except ImportError:
            import ensurepip
            ensurepip.bootstrap(user=True)
        from pip._internal.cli.main import main as pip_main
    # No broad --upgrade: satisfy the application's existing pinned requirements.
    args = ["install", "--user", "--disable-pip-version-check", "-r", str(requirements)]
    if sys.prefix != sys.base_prefix:
        args.remove("--user")  # Local venvs already isolate their dependencies.
    result = pip_main(args) or 0
    if result:
        raise RuntimeError(f"Dependency installation exited with code {result}.")
    add_path(project)
    importlib.invalidate_caches()
    for name in ("PyQt6.QtWidgets", "django", "pandas", "openpyxl", "pypdfium2", "pronto_desktop.runtime"):
        importer(name)
    from pronto_desktop.capabilities import PDF_TOOL_HELP, capabilities
    if not capabilities()["pdf"]:
        raise RuntimeError("Python-avhengighetene er installert. " + PDF_TOOL_HELP)
    print("PRONTO installed. Close Python FELLES and open PRONTO_START.cmd.")
    return 0


def main(*, project_dir=PROJECT_DIR):
    try:
        if sys.prefix == sys.base_prefix:
            activate_user_site()
        elif sys.version_info[:2] != (3, 14):
            raise RuntimeError("PRONTO requires Python 3.14.")
        return install(project_dir=project_dir)
    except Exception as error:
        record_failure("install", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
