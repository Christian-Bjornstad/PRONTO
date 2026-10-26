"""Application identity for native windows and the Windows taskbar."""
import sys

from pronto_report.branding import ASSET_ROOT

APP_ID = 'InPreD.PRONTO.Desktop'


def application_icon():
    from PyQt6.QtGui import QIcon
    return QIcon(str(ASSET_ROOT / 'pronto.ico'))


def icon_pixmap(size):
    return application_icon().pixmap(size, size)


def prepare_application_identity():
    """Set Windows identity before Qt creates any native windows."""
    if sys.platform == 'win32':
        import ctypes
        # Per-process identity; no registry, installer or system setting is changed.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)


def apply_application_branding(app):
    prepare_application_identity()
    app.setWindowIcon(application_icon())
