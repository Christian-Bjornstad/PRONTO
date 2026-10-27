"""Start PRONTO inside the active Python interpreter without a child interpreter."""
from pathlib import Path
import importlib
import runpy
import site
import sys
import sqlite3

PROJECT_DIR = Path(__file__).resolve().parent
_helpers = runpy.run_path(str(PROJECT_DIR / "install_python_felles.py"), run_name="pronto_bootstrap_helpers")


def start(*, project_dir=PROJECT_DIR, user_site=None, app_main=None, argv=None):
    project = Path(project_dir).resolve()
    if not (project / "pronto_desktop").is_dir() or not (project / "pronto_web").is_dir():
        raise RuntimeError("Cannot find the complete PRONTO project next to this script.")
    package_site = Path(user_site or site.getusersitepackages())
    # A virtualenv should keep its isolated pinned packages; FELLES uses user site.
    if sys.prefix == sys.base_prefix or user_site is not None:
        site.addsitedir(str(package_site))
        _helpers["add_path"](package_site)
    _helpers["add_path"](project)
    importlib.invalidate_caches()
    if app_main is None:
        import pronto_desktop
        if Path(pronto_desktop.__file__).resolve().parent != project / "pronto_desktop":
            raise RuntimeError("PRONTO was already imported from another program folder. Restart Python FELLES.")
        from pronto_desktop.__main__ import main as app_main
    # Never forward host-launcher arguments from a pasted FELLES command.
    result = app_main(list(argv or [])) or 0
    if result:
        raise RuntimeError(f"PRONTO exited with code {result}.")
    return 0


def main(*, project_dir=PROJECT_DIR, argv=None):
    try:
        if sys.prefix == sys.base_prefix:
            _helpers["activate_user_site"]()
        elif sys.version_info[:2] != (3, 14):
            raise RuntimeError("PRONTO requires Python 3.14.")
        return start(project_dir=project_dir, argv=argv)
    except Exception as error:
        _helpers["record_failure"]("start", error)
        if isinstance(error, ImportError):
            print('Kjør PRONTO_INSTALL.cmd for å installere eller reparere Python-avhengighetene.')
        elif isinstance(error, sqlite3.Error):
            print('Feil ved database eller sikkerhetskopi. Behold datamappen; reinstallering av Python-avhengigheter løser ikke denne feilen.')
        else:
            print('Se feilloggen ovenfor. Behold eksisterende datamappe og database.')
        return 1


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
