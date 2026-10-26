"""Native GUI interaction checks using synthetic sources and an isolated runtime."""
from __future__ import annotations

from dataclasses import replace
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
from PyQt6.QtWidgets import QDialog, QLineEdit, QPushButton, QScrollArea

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
    assert not window.windowIcon().isNull()
    assert len(window.folder_fields) == 5
    assert window.nav_buttons[4].text() == 'Log'
    assert window.metrics["reports"].text() == "12"
    assert window.runtime.count_thread != get_ident()
    window.activateWindow()
    qtbot.keyClick(window, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)
    assert window.stack.currentIndex() == 1
    assert window.nav_buttons[1].isChecked()
    assert not window.advanced_import.isVisible()
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


def test_changed_sources_invalidate_plan_and_empty_scan_focuses_folder(window, plan):
    window.show_plan(plan)
    assert window.import_button.isEnabled()
    window.folder_fields[0].setText(str(plan.folders[0]))
    assert window.plan is None
    assert not window.import_button.isEnabled()
    window.folder_fields[0].clear()
    window.start_scan()
    assert "minst én" in window.statusBar().currentMessage()
    assert "minst én" in window.plan_summary.text()
    assert window._worker is None


def test_scan_and_failure_preserve_review_plan(window, plan, qtbot, monkeypatch):
    import pronto_ingest.discovery as discovery
    for field, folder in zip(window.folder_fields, plan.folders):
        field.setText(str(folder))
    def discover(folders, progress, cancel, **options):
        assert len(folders) == 5
        assert options == {"report_version": "auto", "cnv_source": "merged", "cnv_solution": "main"}
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


def test_parent_folder_and_explicit_source_options_run_in_worker(window, plan, qtbot, monkeypatch):
    import pronto_ingest.discovery as discovery
    window.navigate(1)
    assert window.folder_fields[0].isVisible()
    assert not window.folder_fields[1].isVisible()
    window.more_folders_button.click()
    assert window.folder_fields[4].isVisible()
    window.more_folders_button.click()
    assert not window.folder_fields[4].isVisible()
    window.folder_fields[0].setText(str(plan.folders[0].parent))
    window.report_version.setCurrentIndex(window.report_version.findData("new"))
    window.cnv_source.setCurrentIndex(window.cnv_source.findData("cancan"))
    assert window.cnv_solution.isEnabled()
    window.cnv_solution.setCurrentIndex(window.cnv_solution.findData("alt01"))
    calls = []
    def discover(folders, progress, cancel, **options):
        calls.append((folders, options, get_ident()))
        return plan
    monkeypatch.setattr(discovery, "discover_folders", discover)
    window.start_scan()
    qtbot.waitUntil(lambda: window._worker is None)
    assert len(calls) == 1
    assert calls[0][:2] == ((plan.folders[0].parent,), {"report_version": "new", "cnv_source": "cancan", "cnv_solution": "alt01"})
    assert calls[0][2] != get_ident()
    window.cnv_source.setCurrentIndex(window.cnv_source.findData("merged"))
    assert not window.cnv_solution.isEnabled()
    assert window.plan is None


def test_unset_metadata_requires_explicit_sample_selection(window, plan, qtbot):
    report = replace(plan.reports[0], metadata_flag="-", selected=False, selection_confirmed=False)
    selected_plan = replace(plan, reports=(report,))
    window.show_plan(selected_plan)
    item = window.plan_tree.topLevelItem(0)
    assert item.checkState(0) == Qt.CheckState.Unchecked
    assert item.text(2) == "-"
    assert item.text(3) == "Ikke valgt"
    assert window.metrics["ready"].text() == "0"
    assert not window.import_button.isEnabled()
    item.setCheckState(0, Qt.CheckState.Checked)
    assert window.plan.reports[0].selected
    assert window.plan.reports[0].selection_confirmed
    assert window.metrics["ready"].text() == "1"
    assert window.import_button.isEnabled()
    item.setCheckState(0, Qt.CheckState.Unchecked)
    assert not window.plan.reports[0].selected
    assert not window.import_button.isEnabled()


def test_negative_metadata_has_no_selectable_checkbox(window, plan):
    report = replace(plan.reports[0], metadata_flag="N", selected=False,
                     issues=("Metadata angir at rapport ikke skal opprettes.",))
    window.show_plan(replace(plan, reports=(report,)))
    item = window.plan_tree.topLevelItem(0)
    assert not item.flags() & Qt.ItemFlag.ItemIsUserCheckable
    assert not window.import_button.isEnabled()


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
    for width, height in ((1100, 760), (1400, 900)):
        window.resize(width, height)
        for page, name in ((0, "overview"), (1, "import"), (2, "reports"), (3, "settings"), (4, "diagnostics")):
            window.navigate(page)
            qtbot.wait(30)
            assert window.width() == width
            for widget in window.findChildren(QPushButton):
                if widget.isVisible():
                    assert window.rect().contains(widget.mapTo(window, widget.rect().bottomRight())), widget.objectName()
            assert window.grab().save(str(output / f"pronto-{name}-{width}.png"))


def test_actual_profile_sample_list_preview(window, plan, qtbot, tmp_path):
    sources = plan.reports[0].files
    reports = tuple(ReportPlan(f"SYNTHETIC_DNA_{i:02d}", "SYNTHETIC_RUN_01", sources,
                              profile="tsoppi-run-v1", metadata_flag="-", selected=False,
                              report_version="new") for i in range(1, 14))
    window.show_plan(replace(plan, folders=(tmp_path / "Pronto",), reports=reports,
                             unassigned=(), profile="tsoppi-run-v1", report_version="auto"))
    window.folder_fields[0].setText(str(tmp_path / "Pronto"))
    window.show_plan(replace(plan, reports=reports, unassigned=(), profile="tsoppi-run-v1"))
    window.navigate(1)
    assert window.plan_tree.topLevelItemCount() == 13
    assert "0 valgt" in window.plan_summary.text()
    window.plan_tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Checked)
    window.plan_tree.topLevelItem(1).setCheckState(0, Qt.CheckState.Checked)
    assert "2 valgt" in window.plan_summary.text()
    assert "Kontroller prøvevalget" in window.plan_hint.text()
    assert not window.plan.reports[2].selection_confirmed
    output = Path(os.environ.get("PRONTO_UI_CAPTURE", tmp_path))
    for width, height in ((1100, 760), (1400, 900)):
        window.resize(width, height)
        qtbot.wait(30)
        assert window.stack.widget(1).findChild(QScrollArea).verticalScrollBar().maximum() == 0
        assert window.grab().save(str(output / f"pronto-run-import-{width}.png"))


def test_folder_picker_scans_automatically_in_worker(window, plan, qtbot, monkeypatch, tmp_path):
    from pronto_desktop import gui
    import pronto_ingest.discovery as discovery
    calls = []
    monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *args: str(tmp_path))
    def discover(folders, **kwargs):
        calls.append((folders, get_ident()))
        return plan
    monkeypatch.setattr(discovery, "discover_folders", discover)
    window._choose_folder(0)
    qtbot.waitUntil(lambda: window.plan is not None and window._worker is None)
    assert calls == [((tmp_path,), calls[0][1])]
    assert calls[0][1] != get_ident()


def test_pasted_folder_is_debounced_and_options_rescan(window, plan, qtbot, monkeypatch, tmp_path):
    import pronto_ingest.discovery as discovery
    calls = []
    def discover(folders, **kwargs):
        calls.append((folders, kwargs["report_version"]))
        return plan
    monkeypatch.setattr(discovery, "discover_folders", discover)
    window.folder_fields[0].setText(str(tmp_path / "not-yet-complete"))
    qtbot.wait(70)
    window.folder_fields[0].setText(str(tmp_path))
    qtbot.waitUntil(lambda: len(calls) == 1 and window._worker is None)
    assert calls == [((tmp_path,), "auto")]
    window.report_version.setCurrentIndex(window.report_version.findData("new"))
    assert window.plan is None and not window.import_button.isEnabled()
    qtbot.waitUntil(lambda: len(calls) == 2 and window._worker is None)
    assert calls[-1] == ((tmp_path,), "new")


def test_changed_folder_discards_inflight_plan_and_scans_latest(window, plan, qtbot, monkeypatch, tmp_path):
    import pronto_ingest.discovery as discovery
    second_root = tmp_path / "second"
    second_root.mkdir()
    latest = replace(plan, reports=(replace(plan.reports[0], sample_id="LATEST_SAMPLE"),))
    started, release = Event(), Event()
    calls = []
    def discover(folders, **kwargs):
        calls.append(folders)
        if len(calls) == 1:
            started.set()
            assert release.wait(3)
            return plan
        return latest
    monkeypatch.setattr(discovery, "discover_folders", discover)
    window.folder_fields[0].setText(str(tmp_path))
    window.start_scan()
    qtbot.waitUntil(started.is_set)
    window.folder_fields[0].setText(str(second_root))
    assert window.plan is None
    release.set()
    qtbot.waitUntil(lambda: window.plan is latest and window._worker is None)
    assert calls == [(tmp_path,), (second_root,)]
    assert window.plan_tree.topLevelItem(0).text(0) == "LATEST_SAMPLE"


def test_cancel_stops_pending_automatic_rescan(window, plan, qtbot, monkeypatch, tmp_path):
    import pronto_ingest.discovery as discovery
    second_root = tmp_path / "second"
    second_root.mkdir()
    started = Event()
    calls = []
    def discover(folders, **kwargs):
        calls.append(folders)
        started.set()
        while not kwargs["cancel"]():
            Event().wait(.01)
        return plan
    monkeypatch.setattr(discovery, "discover_folders", discover)
    window.folder_fields[0].setText(str(tmp_path))
    window.start_scan()
    qtbot.waitUntil(started.is_set)
    window.folder_fields[0].setText(str(second_root))
    window.cancel_job()
    qtbot.waitUntil(lambda: window._worker is None)
    qtbot.wait(800)
    assert len(calls) == 1 and window.plan is None
    assert not window.import_button.isEnabled()


def test_select_ready_samples_is_explicit_and_excludes_blocked_metadata(window, plan):
    base = replace(plan.reports[0], profile="tsoppi-run-v1", metadata_flag="-", selected=False)
    reports = (base, replace(base, sample_id="NEGATIVE", metadata_flag="N"),
               replace(base, sample_id="MISSING", issues=("variants: mangler",)))
    window.show_plan(replace(plan, reports=reports))
    assert "Klare prøver kan importeres" in window.plan_hint.text()
    assert not window.import_button.isEnabled()
    window.select_ready_button.click()
    assert window.plan.reports[0].selected and window.plan.reports[0].selection_confirmed
    assert all(not report.selected for report in window.plan.reports[1:])
    assert window.metrics["ready"].text() == "1"
    assert window.import_button.isEnabled()


def test_unused_files_are_collapsed_without_manual_selection_prompt(window, plan):
    window.show_plan(plan)
    group = window.plan_tree.topLevelItem(1)
    assert group.text(0) == "Andre filer"
    assert group.text(3) == "Ikke brukt"
    assert group.child(0).text(3) == "Ikke brukt"
    assert not group.isExpanded()
    assert "uten kobling" not in window.plan_summary.text()
    assert not window.mapping_button.isVisible()
    window.navigate(1)
    window.advanced_sources_button.click()
    assert window.mapping_button.isVisible()


def test_invalid_typed_folder_does_not_start_discovery(window, qtbot, monkeypatch, tmp_path):
    import pronto_ingest.discovery as discovery
    calls = []
    monkeypatch.setattr(discovery, "discover_folders", lambda *args, **kwargs: calls.append(args))
    window.folder_fields[0].setText(str(tmp_path / "not-present"))
    qtbot.waitUntil(lambda: "eksisterende mappe" in window.plan_summary.text() and window._worker is None)
    assert not calls and window.plan is None
    assert not window.import_button.isEnabled()


def test_auto_scan_waits_for_busy_worker_and_keeps_debounce_afterward(window, plan, qtbot, monkeypatch, tmp_path):
    import pronto_ingest.discovery as discovery
    release = Event()
    calls = []
    def discover(folders, **kwargs):
        calls.append(folders)
        return plan
    monkeypatch.setattr(discovery, "discover_folders", discover)
    window._job("Syntetisk bakgrunnsjobb", lambda progress, cancel: release.wait(3), lambda result: None)
    window.folder_fields[0].setText(str(tmp_path))
    qtbot.wait(700)
    assert not calls
    release.set()
    qtbot.waitUntil(lambda: len(calls) == 1 and window._worker is None)
    other = tmp_path / "other"
    other.mkdir()
    window.folder_fields[0].setText(str(other))
    qtbot.wait(70)
    assert len(calls) == 1
    window.folder_fields[0].setText(str(tmp_path))
    qtbot.waitUntil(lambda: len(calls) == 2 and window._worker is None)
    assert calls == [(tmp_path,), (tmp_path,)]


def test_choosing_same_folder_again_refreshes_sources(window, plan, qtbot, monkeypatch, tmp_path):
    from pronto_desktop import gui
    import pronto_ingest.discovery as discovery
    calls = []
    monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *args: str(tmp_path))
    def discover(folders, **kwargs):
        calls.append(folders)
        return plan
    monkeypatch.setattr(discovery, "discover_folders", discover)
    window._choose_folder(0)
    qtbot.waitUntil(lambda: len(calls) == 1 and window._worker is None)
    window._choose_folder(0)
    qtbot.waitUntil(lambda: len(calls) == 2 and window._worker is None)


def test_manual_file_validation_runs_on_worker(window, plan, qtbot, monkeypatch):
    from pronto_desktop import gui
    import pronto_ingest.discovery as discovery
    window.show_plan(plan)
    calls = []
    field = lambda value: SimpleNamespace(currentData=lambda: value)
    dialog = SimpleNamespace(exec=lambda: QDialog.DialogCode.Accepted,
                             report=field(plan.reports[0].key), role=field('variants'),
                             source=field(plan.reports[0].files['variants'][0]))
    monkeypatch.setattr(gui, 'MappingDialog', lambda *args: dialog)
    def validate(*args):
        calls.append(get_ident())
        return plan
    monkeypatch.setattr(discovery, 'assign_source', validate)
    window.map_source()
    qtbot.waitUntil(lambda: bool(calls) and window._worker is None)
    assert calls[0] != get_ident()
