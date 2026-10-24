"""Native GUI interaction checks using synthetic sources and an isolated runtime."""
from __future__ import annotations

import os
from pathlib import Path
from threading import Event, get_ident
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QDialog, QLineEdit, QPushButton

from pronto_desktop.gui import CredentialsDialog, MainWindow, MappingDialog
from pronto_ingest.contracts import DiscoveryPlan, ReportPlan, SourceCandidate


class FakeServer:
    url = "http://127.0.0.1:8770/reports/"
    running = False
    owned = False

    def start(self):
        self.running = self.owned = True
        return self.url

    def stop(self):
        self.running = self.owned = False


class FakeRuntime:
    def __init__(self, root: Path):
        self.data_root = root
        self.database_path = root / "database" / "pronto.sqlite3"
        self.raw_root = root / "raw_imports"
        self.port = 8770
        self.server = FakeServer()
        self.count_thread = None
        self.saved = None

    def report_counts(self):
        self.count_thread = get_ident()
        return {"reports": 12, "drafts": 4}

    def capabilities(self):
        return {"pdfinfo": True, "pdftoppm": True, "pdf": True}

    def backup(self):
        return self.data_root / "backups" / "synthetic.sqlite3"

    def save_next_launch(self, root, port):
        self.saved = (root, port)

    def has_users(self):
        return True


@pytest.fixture
def window(qtbot, tmp_path):
    # Qt's Windows offscreen plugin does not enumerate the system font directory.
    # The normal Windows platform plugin does. Register local fonts for visual QA.
    if not QFontDatabase.families() and os.name == "nt":
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in ("segoeui.ttf", "segoeuib.ttf", "segoeuisl.ttf"):
            if (fonts / filename).exists():
                QFontDatabase.addApplicationFont(str(fonts / filename))
    instance = MainWindow(FakeRuntime(tmp_path))
    qtbot.addWidget(instance)
    instance.show()
    qtbot.waitUntil(lambda: instance.runtime.count_thread is not None and instance._worker is None)
    yield instance
    qtbot.waitUntil(lambda: instance._worker is None)
    instance.close()


@pytest.fixture
def plan(tmp_path):
    folders = tuple(tmp_path / f"folder-{i}" for i in range(1, 6))
    sources = {role: (folders[0] / f"synthetic-{role}.tsv",) for role in ("metadata", "summary", "variants", "sample_list")}
    return DiscoveryPlan(folders, (ReportPlan("SYNTHETIC_001", "RUN_TEST_01", sources),),
                         (SourceCandidate(folders[2] / "CNV_summary_table.csv", "cnv_table"),), ())


def test_initial_state_navigation_and_keyboard(window, qtbot):
    assert len(window.folder_fields) == 5
    assert window.metrics["reports"].text() == "12"
    assert window.runtime.count_thread != get_ident()
    window.activateWindow()
    qtbot.keyClick(window, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)
    assert window.stack.currentIndex() == 1
    assert window.nav_buttons[1].isChecked()
    qtbot.keyClick(window, Qt.Key.Key_5, Qt.KeyboardModifier.ControlModifier)
    assert window.stack.currentIndex() == 4


def test_missing_pdf_tools_are_reported_without_blocking_gui(window, qtbot):
    threads = []
    def capabilities():
        threads.append(get_ident())
        return {"pdfinfo": False, "pdftoppm": True, "pdf": False}
    window.runtime.capabilities = capabilities
    window.refresh_counts()
    qtbot.waitUntil(lambda: window._worker is None)
    assert threads and threads[0] != get_ident()
    assert "Poppler" in window.pdf_tools_status.text()
    assert "pdfinfo: mangler" in window.pdf_tools_status.text()
    window.navigate(4)
    assert window.scan_button.isEnabled()


def test_scan_requires_five_folders_and_rejects_stale_plan(window, plan):
    window.show_plan(plan)
    assert window.import_button.isEnabled()
    window.folder_fields[0].setText(str(plan.folders[0]))
    assert window.plan is None
    assert not window.import_button.isEnabled()
    window.start_scan()
    assert "alle fem" in window.statusBar().currentMessage()


def test_scan_and_failure_preserve_review_plan(window, plan, qtbot, monkeypatch):
    import pronto_ingest.discovery as discovery
    for field, folder in zip(window.folder_fields, plan.folders):
        field.setText(str(folder))
    def discover(folders, progress, cancel):
        assert len(folders) == 5
        assert get_ident() != gui_thread
        progress("Syntetisk filkontroll")
        return plan
    gui_thread = get_ident()
    monkeypatch.setattr(discovery, "discover_folders", discover)
    window.start_scan()
    qtbot.waitUntil(lambda: window._worker is None)
    assert window.plan == plan
    assert window.plan_tree.topLevelItemCount() == 2
    assert "1 klare" in window.plan_summary.text()
    def fail(*args, **kwargs):
        raise ValueError("Syntetisk lesefeil")
    monkeypatch.setattr(discovery, "discover_folders", fail)
    window.start_scan()
    qtbot.waitUntil(lambda: window._worker is None)
    assert window.plan == plan
    assert "Syntetisk lesefeil" in window.plan_summary.text()


def test_mapping_shows_only_discovered_sources_for_role(window, plan):
    dialog = MappingDialog(plan, window)
    assert dialog.source.currentData() == plan.reports[0].files["metadata"][0]
    dialog.role.setCurrentIndex(dialog.role.findData("cnv_table"))
    assert dialog.source.count() == 2
    assert dialog.source.itemData(1) == plan.unassigned[0].path
    assert dialog.source.currentData() is None
    dialog.reject()


def test_credentials_password_fields_and_confirmation(window, qtbot):
    dialog = CredentialsDialog(first_user=True, parent=window)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.password.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.confirm.echoMode() == QLineEdit.EchoMode.Password
    dialog.username.setText("synthetic-user")
    dialog.password.setText("one")
    dialog.confirm.setText("two")
    dialog._validate()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "ulike" in dialog.error.text()
    dialog.reject()


def test_cancel_runs_on_worker_and_preserves_plan(window, plan, qtbot):
    started = Event()
    window.show_plan(plan)
    def operation(progress, cancel):
        started.set()
        pause = Event()
        while not cancel():
            pause.wait(0.01)
        return "cancelled"
    results = []
    window._job("Syntetisk jobb", operation, results.append)
    qtbot.waitUntil(started.is_set)
    assert not window.import_button.isEnabled()
    window.cancel_job()
    qtbot.waitUntil(lambda: window._worker is None)
    assert results == ["cancelled"]
    assert window.plan == plan


def test_server_controls_and_backup(window, qtbot):
    window.start_server()
    qtbot.waitUntil(lambda: window._worker is None)
    assert window.runtime.server.running
    assert not window.start_button.isEnabled()
    assert window.stop_button.isEnabled()
    window.stop_server()
    qtbot.waitUntil(lambda: window._worker is None)
    assert not window.runtime.server.running
    window.backup()
    qtbot.waitUntil(lambda: window._worker is None)
    assert "synthetic.sqlite3" in window.backup_result.text()


def test_import_result_and_next_launch_settings(window, qtbot):
    result = SimpleNamespace(items=(SimpleNamespace(sample_id="SYNTHETIC_001", status="imported", message="Kontrollert syntetisk prøve"),))
    window._import_finished(result)
    qtbot.waitUntil(lambda: window._worker is None)
    assert window.stack.currentIndex() == 2
    assert window.history_table.item(0, 2).text() == "Importert"
    original_db = window.runtime.database_path
    window.next_root.setText(str(window.runtime.data_root / "next-launch"))
    window.next_port.setValue(8779)
    window._save_next_launch()
    qtbot.waitUntil(lambda: window._worker is None)
    assert window.runtime.saved == (window.runtime.data_root / "next-launch", 8779)
    assert window.runtime.database_path == original_db


def test_first_account_authenticates_import_actor_on_worker(window, plan, qtbot, monkeypatch):
    from pronto_desktop import gui
    import pronto_ingest.importer as importer
    window.show_plan(plan)
    actor = SimpleNamespace(username="synthetic-user", pk=17)
    calls = []
    monkeypatch.setattr(window.runtime, "has_users", lambda: False)
    monkeypatch.setattr(window.runtime, "create_user", lambda username, password: calls.append(("create", username, get_ident())), raising=False)
    monkeypatch.setattr(window.runtime, "authenticate", lambda username, password: actor, raising=False)
    def credentials(dialog):
        dialog.username.setText("synthetic-user")
        dialog.password.setText("Synthetic-test-passphrase-248")
        dialog.confirm.setText("Synthetic-test-passphrase-248")
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(gui.CredentialsDialog, "exec", credentials)
    def import_plan(selected, *, actor, raw_root, progress, cancel):
        calls.append(("import", actor.pk, get_ident()))
        return SimpleNamespace(items=())
    monkeypatch.setattr(importer, "import_plan", import_plan)
    window.prepare_import()
    qtbot.waitUntil(lambda: any(c[0] == "import" for c in calls) and window._worker is None)
    assert calls[0][:2] == ("create", "synthetic-user")
    assert calls[1][:2] == ("import", 17)
    assert all(call[2] != get_ident() for call in calls)
    assert window.actor is actor
    assert window.logout_button.isEnabled()


def test_saved_history_loaded_only_for_authenticated_actor(window, qtbot, monkeypatch):
    seen = []
    actor = SimpleNamespace(username="synthetic-user", pk=17)
    def history(user):
        seen.append(user.pk)
        return [{"time": "2026-10-24T10:30:00+02:00", "sample_id": "SYNTHETIC_PERSISTED", "status": "imported", "message": "Kontrollert"}]
    monkeypatch.setattr(window.runtime, "import_history", history, raising=False)
    window.refresh_counts()
    qtbot.waitUntil(lambda: window._worker is None)
    assert seen == []
    window._authenticated(actor, False)
    qtbot.waitUntil(lambda: window._worker is None)
    assert seen == [17]
    assert window.history_table.item(0, 1).text() == "SYNTHETIC_PERSISTED"
    window._logout()
    assert window.actor is None
    assert window.history_table.rowCount() == 0


def test_native_layout_and_synthetic_screenshots(window, plan, qtbot, tmp_path):
    for field, folder in zip(window.folder_fields, plan.folders):
        field.setText(str(folder))
    window.show_plan(plan)
    window.resize(1280, 850)
    output = Path(os.environ.get("PRONTO_UI_CAPTURE", tmp_path))
    output.mkdir(parents=True, exist_ok=True)
    for page, name in ((0, "overview"), (1, "import"), (2, "reports"), (3, "settings"), (4, "diagnostics")):
        window.navigate(page)
        qtbot.wait(30)
        assert window.size().width() == 1280
        assert window.size().height() == 850
        for widget in window.findChildren(QPushButton):
            if widget.isVisible():
                assert widget.minimumHeight() >= 40
                assert widget.accessibleName()
                top_left = widget.mapTo(window, QPoint(0, 0))
                bottom_right = widget.mapTo(window, widget.rect().bottomRight())
                assert window.rect().contains(top_left), widget.objectName()
                assert window.rect().contains(bottom_right), widget.objectName()
        assert window.grab().save(str(output / f"pronto-{name}.png"))
    window.resize(1100, 760)
    window.navigate(1)
    qtbot.wait(30)
    for widget in (window.scan_button, window.mapping_button, window.import_button, window.start_button, window.open_button):
        assert window.rect().contains(widget.mapTo(window, widget.rect().bottomRight()))
