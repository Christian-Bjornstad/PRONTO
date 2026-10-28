"""Start PRONTO's desktop control window or check its local configuration."""
import argparse
from pathlib import Path
import sys

from .runtime import DesktopRuntime, ConfigurationAccessError, DatabaseLocationError, ROOT


def select_existing_database(error):
    """Recover missing/stale locations before Django setup; never replace a DB."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox
    from .shared_installation import read_locator
    app = QApplication.instance() or QApplication(['PRONTO'])
    details = str(error)
    try:
        shared = read_locator(ROOT)
    except (OSError, ValueError) as locator_error:
        shared = None
        details += f'\nFelles databasevalg: {locator_error}'
    message = QMessageBox()
    message.setTextFormat(Qt.TextFormat.PlainText)
    message.setWindowTitle('Finn eksisterende PRONTO-database')
    message.setIcon(QMessageBox.Icon.Warning)
    message.setText('Databaseplasseringen må kontrolleres.')
    message.setInformativeText(details + '\n\nIngen database eller nøkkel erstattes.')
    shared_button = None
    if shared:
        message.setInformativeText(message.informativeText() +
            f'\n\nFelles database: {shared["database"]}\nDatamappe: {shared["data_root"]}')
        shared_button = message.addButton('Bruk felles database', QMessageBox.ButtonRole.AcceptRole)
    choose_button = message.addButton('Velg eksisterende database…', QMessageBox.ButtonRole.ActionRole)
    message.addButton(QMessageBox.StandardButton.Cancel).setText('Avbryt')
    message.exec()
    if shared_button is not None and message.clickedButton() is shared_button:
        return shared['database'], shared['data_root'], app
    if message.clickedButton() is not choose_button:
        return None, None, app
    filename, _ = QFileDialog.getOpenFileName(None, 'Velg eksisterende PRONTO-database', str(ROOT / '.local-web'),
        'SQLite-database (*.sqlite3);;Alle filer (*)')
    # Keep QApplication alive until the main window has taken over its lifetime.
    database = Path(filename) if filename else None
    root = (database.parent.parent if database.parent.name == 'database' else database.parent) if database else None
    return database, root, app


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
    runtime = None
    recovery_app = None
    try:
        while True:
            try:
                runtime = DesktopRuntime(data_root=root, port=options.port, database_path=database)
                runtime.initialize()
                break
            except (ConfigurationAccessError, DatabaseLocationError) as error:
                from django.conf import settings
                if options.check or settings.configured:
                    raise
                database, root, recovery_app = select_existing_database(error)
                if database is None:
                    return 0
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
        if runtime is not None and runtime._initialized:
            runtime.server.stop()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
