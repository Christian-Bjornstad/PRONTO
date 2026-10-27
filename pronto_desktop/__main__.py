"""Start PRONTO's desktop control window or check its local configuration."""
import argparse
from pathlib import Path
import sys

from .runtime import DesktopRuntime, ConfigurationAccessError


def select_existing_database():
    """Only recover the unreadable locator; never make a replacement database."""
    from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox
    app = QApplication.instance() or QApplication(['PRONTO'])
    QMessageBox.information(None, 'Velg eksisterende database',
        'Felles config.json kan ikke leses. Velg den eksisterende PRONTO-databasen '
        '(pronto.sqlite3) i avtalt datamappe. Ingen rapporter kopieres og ingen ny database opprettes. '
        'Du må ha tilgang til databasen og secret.key i datamappen.')
    filename, _ = QFileDialog.getOpenFileName(None, 'Velg eksisterende PRONTO-database', '',
        'SQLite-database (*.sqlite3);;Alle filer (*)')
    # Keep QApplication alive until the main window has taken over its lifetime.
    return (Path(filename) if filename else None), app


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, help="Persistent database, import archive and backup folder.")
    parser.add_argument("--port", type=int, help="Loopback report server port (default 8770).")
    parser.add_argument('--database', type=Path, help='Explicit existing database; selection is remembered per user.')
    parser.add_argument("--gui", action="store_true", help="Open the desktop window (default).")
    parser.add_argument("--check", action="store_true", help="Check configuration and migrate safely, then exit.")
    options = parser.parse_args(argv)
    database = options.database
    root = options.data_root
    if database is not None and root is None:
        root = database.parent.parent if database.parent.name == 'database' else database.parent
    runtime = DesktopRuntime(data_root=root, port=options.port, database_path=database)
    recovery_app = None
    try:
        try:
            runtime.initialize()
        except ConfigurationAccessError:
            if options.check:
                raise
            database, recovery_app = select_existing_database()
            if database is None:
                return 0
            root = database.parent.parent if database.parent.name == 'database' else database.parent
            runtime = DesktopRuntime(data_root=root, port=options.port, database_path=database)
            runtime.initialize()
        if options.check:
            print(f"PRONTO configuration OK. Database: {runtime.database_path}")
            return 0
        from PyQt6.QtWidgets import QApplication
        from .gui import MainWindow
        from .branding import apply_application_branding, prepare_application_identity
        prepare_application_identity()
        app = recovery_app or QApplication.instance() or QApplication(["PRONTO"])
        app.setApplicationName("PRONTO")
        app.setOrganizationName("InPreD")
        apply_application_branding(app)
        window = MainWindow(runtime)
        window.show()
        return app.exec()
    finally:
        if runtime._initialized:
            runtime.server.stop()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
