"""Start PRONTO's desktop control window or check its local configuration."""
import argparse
from pathlib import Path
import sys

from .runtime import DesktopRuntime


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, help="Persistent database, import archive and backup folder.")
    parser.add_argument("--port", type=int, help="Loopback report server port (default 8770).")
    parser.add_argument("--gui", action="store_true", help="Open the desktop window (default).")
    parser.add_argument("--check", action="store_true", help="Check configuration and migrate safely, then exit.")
    options = parser.parse_args(argv)
    runtime = DesktopRuntime(data_root=options.data_root, port=options.port)
    try:
        runtime.initialize()
        if options.check:
            print(f"PRONTO configuration OK. Database: {runtime.database_path}")
            return 0
        from PyQt6.QtWidgets import QApplication
        from .gui import MainWindow
        app = QApplication.instance() or QApplication(["PRONTO"])
        app.setApplicationName("PRONTO")
        app.setOrganizationName("InPreD")
        window = MainWindow(runtime)
        window.show()
        return app.exec()
    finally:
        if runtime._initialized:
            runtime.server.stop()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
