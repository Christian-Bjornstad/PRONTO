"""Native PRONTO control centre. All file/database work runs outside the GUI thread."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Any, Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .theme import build_stylesheet

ROLE_LABELS = {
    "metadata": "Kliniske metadata", "summary": "TMB / MSI-sammendrag",
    "variants": "Småvarianter", "sample_list": "Prøveliste",
    "cnv_table": "CNV-tabell", "rna_table": "RNA-tabell",
    "cnv_plot": "CNV-plott", "qc_plot": "QC-plott", "other_plot": "Andre plott",
}
STATUS_LABELS = {"imported": "Importert", "already_imported": "Allerede importert", "failed": "Feilet", "cancelled": "Avbrutt"}


def label(text: str, *, muted: bool = False, section: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setWordWrap(True)
    widget.setProperty("muted", muted)
    widget.setProperty("section", section)
    return widget


def button(text: str, name: str, *, primary: bool = False) -> QPushButton:
    widget = QPushButton(text)
    widget.setObjectName(name)
    widget.setAccessibleName(text.replace("&", ""))
    widget.setProperty("primary", primary)
    widget.setMinimumHeight(40)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setProperty("card", True)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 15, 18, 15)
    layout.setSpacing(10)
    return frame, layout


def table(headers: list[str]) -> QTableWidget:
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    widget.verticalHeader().setVisible(False)
    widget.setAlternatingRowColors(True)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setMinimumHeight(110)
    return widget


class WorkerSignals(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)


class Worker(QRunnable):
    def __init__(self, operation: Callable[..., Any]) -> None:
        super().__init__()
        self.operation = operation
        self.cancel = Event()
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            result = self.operation(self.signals.progress.emit, self.cancel.is_set)
        except Exception as exc:
            self.signals.failed.emit(str(exc) or type(exc).__name__)
        else:
            self.signals.finished.emit(result)
        finally:
            # Each worker gets its own Django thread-local connection.
            try:
                from django.db import connections
                connections.close_all()
            except Exception:
                pass


class CredentialsDialog(QDialog):
    """Collect credentials only for the current operation; never persist passwords."""
    def __init__(self, *, first_user: bool, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Opprett første bruker" if first_user else "Logg inn for import")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        layout.addWidget(label(
            "Opprett den første PRONTO-brukeren. Kontoen brukes også i rapportene."
            if first_user else "Bruk PRONTO-kontoen din. Importen registreres på denne brukeren."
        ))
        form = QFormLayout()
        self.username = QLineEdit()
        self.username.setAccessibleName("Brukernavn")
        self.username.setObjectName("import-username")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setAccessibleName("Passord")
        self.password.setObjectName("import-password")
        form.addRow("&Brukernavn", self.username)
        form.addRow("&Passord", self.password)
        self.confirm = None
        if first_user:
            self.confirm = QLineEdit()
            self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm.setAccessibleName("Gjenta passord")
            form.addRow("&Gjenta passord", self.confirm)
        layout.addLayout(form)
        self.error = label("")
        self.error.setProperty("tone", "danger")
        layout.addWidget(self.error)
        buttons = QDialogButtonBox()
        self.submit = button("Opprett bruker" if first_user else "Logg inn", "submit-credentials", primary=True)
        buttons.addButton(self.submit, QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_button = button("Avbryt", "cancel-credentials")
        buttons.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.username.setFocus()

    def _validate(self) -> None:
        if not self.username.text().strip() or not self.password.text():
            self.error.setText("Fyll ut brukernavn og passord.")
        elif self.confirm is not None and self.password.text() != self.confirm.text():
            self.error.setText("Passordene er ulike.")
        else:
            self.accept()


class MappingDialog(QDialog):
    def __init__(self, plan: Any, parent: QWidget) -> None:
        super().__init__(parent)
        self.plan = plan
        self.setWindowTitle("Koble kildefil til prøve")
        self.setMinimumWidth(670)
        layout = QVBoxLayout(self)
        layout.addWidget(label("Velg en funnet fil og prøven den faktisk tilhører. Kontroller filinnhold og prøve-ID før du bekrefter."))
        form = QFormLayout()
        self.report = QComboBox()
        self.report.setAccessibleName("Prøve for kildefil")
        for report in plan.reports:
            self.report.addItem(f"{report.sample_id}  ·  {report.run_id}", report.key)
        self.role = QComboBox()
        self.role.setAccessibleName("Filtype")
        for role, title in ROLE_LABELS.items():
            self.role.addItem(title, role)
        self.source = QComboBox()
        self.source.setAccessibleName("Funnet kildefil")
        self.source.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.source.setMinimumContentsLength(35)
        self.source.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.detail = label("", muted=True)
        self.report.currentIndexChanged.connect(self._populate)
        self.role.currentIndexChanged.connect(self._populate)
        self.source.currentIndexChanged.connect(self._detail)
        form.addRow("&Prøve", self.report)
        form.addRow("&Filtype", self.role)
        form.addRow("&Kildefil", self.source)
        layout.addLayout(form)
        layout.addWidget(self.detail)
        actions = QDialogButtonBox()
        apply_button = button("Bekreft kobling", "confirm-mapping", primary=True)
        actions.addButton(apply_button, QDialogButtonBox.ButtonRole.AcceptRole)
        actions.addButton(button("Avbryt", "cancel-mapping"), QDialogButtonBox.ButtonRole.RejectRole)
        actions.accepted.connect(self.accept)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)
        self._populate()

    def _populate(self) -> None:
        self.source.clear()
        self.source.addItem("Ingen kilde / fjern kobling", None)
        role = self.role.currentData()
        paths = {Path(candidate.path) for candidate in self.plan.unassigned if candidate.role == role}
        for report in self.plan.reports:
            paths.update(Path(path) for path in report.files.get(role, ()))
        for path in sorted(paths, key=lambda p: str(p).casefold()):
            self.source.addItem(path.name, path)
            self.source.setItemData(self.source.count() - 1, str(path), Qt.ItemDataRole.ToolTipRole)
        selected = next((r for r in self.plan.reports if r.key == self.report.currentData()), None)
        current = selected.files.get(role, ()) if selected is not None else ()
        if len(current) == 1:
            for index in range(1, self.source.count()):
                if self.source.itemData(index) == Path(current[0]):
                    self.source.setCurrentIndex(index)
                    break
        self._detail()

    def _detail(self) -> None:
        value = self.source.currentData()
        self.detail.setText(str(value) if value else "Dette fjerner den valgte filtypen fra denne prøven.")


class MainWindow(QMainWindow):
    def __init__(self, runtime: Any) -> None:
        super().__init__()
        self.runtime = runtime
        self.plan: Any = None
        self.actor: Any = None
        self._worker: Worker | None = None
        self._closing = False
        self._operation = ""
        self._history: list[tuple[str, str, str, str]] = []
        self._persisted_history: list[tuple[str, str, str, str]] = []
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self.setWindowTitle("PRONTO · Kontrollsenter")
        self.setMinimumSize(1100, 760)
        self.resize(1280, 850)
        self.setStyleSheet(build_stylesheet())
        shell = QWidget()
        shell.setObjectName("shell")
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._sidebar())
        content = QWidget()
        content.setObjectName("content")
        body = QVBoxLayout(content)
        body.setContentsMargins(26, 22, 26, 18)
        body.setSpacing(16)
        body.addWidget(self._server_bar())
        self.stack = QStackedWidget()
        self.stack.setObjectName("pages")
        for page in (self._overview(), self._import_page(), self._reports_page(), self._settings_page(), self._diagnostics_page()):
            self.stack.addWidget(page)
        body.addWidget(self.stack, 1)
        self.progress = QProgressBar()
        self.progress.setAccessibleName("Fremdrift for pågående arbeid")
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        self.progress.hide()
        body.addWidget(self.progress)
        root.addWidget(content, 1)
        self.setCentralWidget(shell)
        self.statusBar().showMessage("Klar. Velg fem mapper fra samme kjøring for å starte.")
        for index in range(5):
            action = QAction(self)
            action.setShortcut(QKeySequence(f"Ctrl+{index + 1}"))
            action.triggered.connect(lambda checked=False, page=index: self.navigate(page))
            self.addAction(action)
        scan_action = QAction(self)
        scan_action.setShortcut(QKeySequence("Ctrl+R"))
        scan_action.triggered.connect(self.start_scan)
        self.addAction(scan_action)
        self.navigate(0)
        self._refresh_server()
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._refresh_server)
        self._timer.start()
        QTimer.singleShot(0, self.refresh_counts)

    def _sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(204)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 28, 18, 22)
        layout.setSpacing(8)
        brand = label("PRONTO")
        brand.setObjectName("brand")
        layout.addWidget(brand)
        detail = label("Rapportarbeidsplass")
        detail.setObjectName("brand-detail")
        layout.addWidget(detail)
        layout.addSpacing(30)
        self.nav_buttons: list[QPushButton] = []
        for index, name in enumerate(("Oversikt", "Importer", "Rapporter", "Innstillinger", "Diagnostikk")):
            nav = button(name, f"nav-{index}")
            nav.setCheckable(True)
            nav.setProperty("nav", True)
            nav.setToolTip(f"{name} (Ctrl+{index + 1})")
            nav.clicked.connect(lambda checked=False, page=index: self.navigate(page))
            self.nav_buttons.append(nav)
            layout.addWidget(nav)
        layout.addStretch()
        caption = label("LOKAL ARBEIDSPLASS")
        caption.setObjectName("sidebar-caption")
        layout.addWidget(caption)
        self.side_status = label("Server stoppet")
        self.side_status.setObjectName("sidebar-status")
        layout.addWidget(self.side_status)
        return sidebar

    def _server_bar(self) -> QFrame:
        panel, layout = card()
        row = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(3)
        titles.addWidget(label("Rapportserver", section=True))
        self.server_address = label("", muted=True)
        self.server_address.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        titles.addWidget(self.server_address)
        row.addLayout(titles, 1)
        self.server_status = label("Stoppet")
        self.server_status.setProperty("status", True)
        row.addWidget(self.server_status)
        self.start_button = button("Start server", "start-server")
        self.start_button.clicked.connect(self.start_server)
        self.open_button = button("Åpne rapporter", "open-reports", primary=True)
        self.open_button.clicked.connect(self.open_reports)
        self.stop_button = button("Stopp", "stop-server")
        self.stop_button.setAccessibleName("Stopp rapportserveren")
        self.stop_button.clicked.connect(self.stop_server)
        for widget in (self.start_button, self.open_button, self.stop_button):
            row.addWidget(widget)
        layout.addLayout(row)
        return panel

    def _page(self, title: str, intro: str) -> tuple[QWidget, QVBoxLayout]:
        widget = QWidget()
        widget.setObjectName("page")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        heading = label(title)
        heading.setObjectName("page-title")
        layout.addWidget(heading)
        layout.addWidget(label(intro, muted=True))
        return widget, layout

    def _overview(self) -> QWidget:
        page, layout = self._page("Fra kjøring til ferdig rapport", "Samle resultatene, kontroller prøvekoblingen og fortsett arbeidet i HTML-rapporten.")
        row = QHBoxLayout()
        self.metrics: dict[str, QLabel] = {}
        for key, title in (("reports", "Rapporter i databasen"), ("samples", "Prøver i importplanen"), ("ready", "Klare for import")):
            frame, contents = card()
            contents.addWidget(label(title, muted=True))
            value = label("—" if key == "reports" else "0")
            value.setProperty("metric", True)
            self.metrics[key] = value
            contents.addWidget(value)
            row.addWidget(frame, 1)
        layout.addLayout(row)
        frame, contents = card()
        contents.addWidget(label("Én kjøring. Fem mapper. Ett samlet grunnlag.", section=True))
        contents.addWidget(label("1    Velg de fem mappene fra samme kjøring.\n\n2    Kontroller filene og koblingen til hver prøve.\n\n3    Prosesser data og åpne rapportene for vurdering."))
        actionrow = QHBoxLayout()
        self.begin_button = button("Velg mapper og importer", "begin-import", primary=True)
        self.begin_button.clicked.connect(lambda: self.navigate(1))
        actionrow.addWidget(self.begin_button)
        actionrow.addStretch()
        contents.addLayout(actionrow)
        layout.addWidget(frame)
        layout.addWidget(label("Originalfilene beholdes. Importerte kilder arkiveres, og rapporter og vurderinger lagres i den valgte databasen.", muted=True))
        layout.addStretch()
        return page

    def _import_page(self) -> QWidget:
        page, layout = self._page("Importer kjøring", "Velg fem mapper. PRONTO søker i undermapper og lager en importplan før noe lagres.")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 3, 0)
        inner_layout.setSpacing(10)
        foldercard, contents = card()
        grid = QGridLayout()
        grid.setHorizontalSpacing(9)
        grid.setVerticalSpacing(7)
        self.folder_fields: list[QLineEdit] = []
        self.folder_buttons: list[QPushButton] = []
        for index in range(5):
            field = QLineEdit()
            field.setAccessibleName(f"Mappe {index + 1}")
            field.setObjectName(f"folder-{index + 1}")
            field.setPlaceholderText("Velg mappe fra kjøringen …")
            field.textChanged.connect(self._folders_changed)
            browse = button("Velg …", f"choose-folder-{index + 1}")
            browse.setAccessibleName(f"Velg mappe {index + 1}")
            browse.clicked.connect(lambda checked=False, slot=index: self._choose_folder(slot))
            title = label(f"Mappe {index + 1}")
            title.setBuddy(field)
            grid.addWidget(title, index, 0)
            grid.addWidget(field, index, 1)
            grid.addWidget(browse, index, 2)
            self.folder_fields.append(field)
            self.folder_buttons.append(browse)
        grid.setColumnStretch(1, 1)
        contents.addLayout(grid)
        inner_layout.addWidget(foldercard)
        self.plan_summary = label("Ingen importplan ennå. Velg mapper og trykk Kontroller filer.", muted=True)
        inner_layout.addWidget(self.plan_summary)
        self.plan_tree = QTreeWidget()
        self.plan_tree.setObjectName("import-plan")
        self.plan_tree.setAccessibleName("Importplan med prøver, kildefiler og avvik")
        self.plan_tree.setHeaderLabels(["Prøve / filtype", "Kjøring / kildefil", "Status"])
        self.plan_tree.setAlternatingRowColors(True)
        self.plan_tree.setMinimumHeight(170)
        self.plan_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.plan_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.plan_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        inner_layout.addWidget(self.plan_tree, 1)
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)
        actions = QHBoxLayout()
        self.scan_button = button("Kontroller filer", "scan-folders")
        self.scan_button.setToolTip("Søk etter kilder og bygg importplan (Ctrl+R)")
        self.scan_button.clicked.connect(self.start_scan)
        self.mapping_button = button("Koble kildefil …", "map-source")
        self.mapping_button.clicked.connect(self.map_source)
        self.mapping_button.setEnabled(False)
        self.cancel_button = button("Avbryt", "cancel-job")
        self.cancel_button.clicked.connect(self.cancel_job)
        self.cancel_button.hide()
        self.import_button = button("Prosesser og importer", "import-data", primary=True)
        self.import_button.clicked.connect(self.prepare_import)
        self.import_button.setEnabled(False)
        actions.addWidget(self.scan_button)
        actions.addWidget(self.mapping_button)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        actions.addWidget(self.import_button)
        layout.addLayout(actions)
        return page

    def _reports_page(self) -> QWidget:
        page, layout = self._page("Rapporter og importhistorikk", "Åpne rapportserveren for vurderinger, kildefiler, HTML og PDF. Tidligere importjobber beholdes i databasen.")
        self.report_state = label("Henter rapportstatus …", section=True)
        layout.addWidget(self.report_state)
        self.history_table = table(["Tidspunkt", "Prøve", "Resultat", "Melding"])
        self.history_table.setObjectName("import-history")
        self.history_table.setAccessibleName("Resultater og historikk for importjobber")
        layout.addWidget(self.history_table, 1)
        self.history_note = label("Logg inn under Innstillinger for å vise din lagrede importhistorikk.", muted=True)
        layout.addWidget(self.history_note)
        actions = QHBoxLayout()
        refresh = button("Oppdater oversikt", "refresh-reports")
        refresh.clicked.connect(self.refresh_counts)
        actions.addWidget(refresh)
        actions.addStretch()
        open_reports = button("Åpne rapportoversikt", "open-report-overview", primary=True)
        open_reports.clicked.connect(self.open_reports)
        actions.addWidget(open_reports)
        layout.addLayout(actions)
        return page

    def _settings_page(self) -> QWidget:
        page, layout = self._page("Innstillinger", "Lagringsplassene brukes av både appen og rapportserveren.")
        frame, contents = card()
        form = QFormLayout()
        form.setVerticalSpacing(14)
        self.database_field = QLineEdit(str(self.runtime.database_path))
        self.database_field.setAccessibleName("Aktiv database")
        self.database_field.setReadOnly(True)
        self.raw_field = QLineEdit(str(self.runtime.raw_root))
        self.raw_field.setAccessibleName("Arkiv for importerte kildefiler")
        self.raw_field.setReadOnly(True)
        self.port_field = QSpinBox()
        self.port_field.setAccessibleName("Port for rapportserveren")
        self.port_field.setRange(1024, 65535)
        self.port_field.setValue(self.runtime.port)
        self.port_field.setReadOnly(True)
        form.addRow("Database", self.database_field)
        form.addRow("Kildearkiv", self.raw_field)
        form.addRow("Serverport", self.port_field)
        contents.addLayout(form)
        contents.addWidget(label("Databasevalg og kildearkiv settes ved oppstart. Endring krever omstart, slik at samme database brukes i hele økten.", muted=True))
        storage_row = QHBoxLayout()
        storage_row.addWidget(frame, 1)
        selection, selection_contents = card()
        selection_contents.addWidget(label("Lagringsplass ved neste oppstart", section=True))
        selection_contents.addWidget(label("Velg en eksisterende PRONTO-datamappe. Appen kontrollerer at databasen finnes før valget lagres. Eksisterende data flyttes ikke.", muted=True))
        selection_row = QHBoxLayout()
        self.next_root = QLineEdit(str(getattr(self.runtime, "data_root", self.runtime.database_path.parent)))
        self.next_root.setAccessibleName("Datamappe ved neste oppstart")
        self.next_root.setReadOnly(True)
        choose_root = button("Velg mappe …", "choose-data-root")
        choose_root.clicked.connect(self._choose_data_root)
        selection_row.addWidget(self.next_root, 1)
        selection_row.addWidget(choose_root)
        selection_contents.addLayout(selection_row)
        options = QHBoxLayout()
        options.addWidget(label("Serverport"))
        self.next_port = QSpinBox()
        self.next_port.setRange(1024, 65535)
        self.next_port.setValue(self.runtime.port)
        self.next_port.setAccessibleName("Serverport ved neste oppstart")
        options.addWidget(self.next_port)
        options.addStretch()
        self.save_settings_button = button("Lagre for neste oppstart", "save-next-launch")
        self.save_settings_button.setEnabled(hasattr(self.runtime, "save_next_launch"))
        self.save_settings_button.clicked.connect(self._save_next_launch)
        selection_contents.addLayout(options)
        selection_contents.addWidget(self.save_settings_button)
        selection_contents.addStretch()
        storage_row.addWidget(selection, 1)
        layout.addLayout(storage_row)
        frame, contents = card()
        contents.addWidget(label("Sikkerhetskopi", section=True))
        contents.addWidget(label("Opprett en konsistent kopi av databasen før overlevering eller større import. Kildearkivet må også inngå i virksomhetens sikkerhetskopiering."))
        row = QHBoxLayout()
        self.backup_button = button("Ta sikkerhetskopi", "backup-database")
        self.backup_button.clicked.connect(self.backup)
        row.addWidget(self.backup_button)
        row.addStretch()
        contents.addLayout(row)
        self.backup_result = label("", muted=True)
        self.backup_result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        contents.addWidget(self.backup_result)
        layout.addWidget(frame)
        self.account_state = label("Import krever innlogging med en PRONTO-bruker.", muted=True)
        layout.addWidget(self.account_state)
        self.account_button = button("Logg inn / opprett første bruker", "manage-account")
        self.account_button.clicked.connect(lambda: self._request_credentials(False))
        account_actions = QHBoxLayout()
        account_actions.addWidget(self.account_button)
        self.logout_button = button("Logg ut av appen", "logout-import")
        self.logout_button.setEnabled(False)
        self.logout_button.clicked.connect(self._logout)
        account_actions.addWidget(self.logout_button)
        account_actions.addStretch()
        layout.addLayout(account_actions)
        layout.addStretch()
        return page

    def _choose_data_root(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Velg datamappe ved neste oppstart", self.next_root.text())
        if directory:
            self.next_root.setText(directory)

    def _save_next_launch(self) -> None:
        root, port = Path(self.next_root.text()), self.next_port.value()
        self._job("Lagrer oppstartsinnstillinger …", lambda progress, cancel: self.runtime.save_next_launch(root, port), lambda result: self._log("Innstillingene er lagret. Lukk og åpne appen for å bruke den valgte datamappen."))

    def _diagnostics_page(self) -> QWidget:
        page, layout = self._page("Diagnostikk", "Status, fremdrift og feil fra denne økten. Tidligere resultater beholdes ved avbrudd.")
        self.pdf_tools_status = label("PDF-kildeplott: kontrollerer verktøy …", muted=True)
        self.pdf_tools_status.setAccessibleName("Status for PDF-verktøy")
        layout.addWidget(self.pdf_tools_status)
        self.diagnostic_log = QPlainTextEdit()
        self.diagnostic_log.setObjectName("diagnostic-log")
        self.diagnostic_log.setAccessibleName("Hendelseslogg fra denne økten")
        self.diagnostic_log.setReadOnly(True)
        self.diagnostic_log.setMaximumBlockCount(3000)
        layout.addWidget(self.diagnostic_log, 1)
        copy = button("Kopier logg", "copy-log")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.diagnostic_log.toPlainText()))
        layout.addWidget(copy, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(label("Loggen kan inneholde prøve-ID og filstier. Håndter den som annet analysegrunnlag.", muted=True))
        return page

    def navigate(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, nav in enumerate(self.nav_buttons):
            nav.setChecked(i == index)

    def _log(self, message: str) -> None:
        self.diagnostic_log.appendPlainText(f"{datetime.now():%H:%M:%S}  {message}")
        self.statusBar().showMessage(message)

    def _job(self, title: str, operation: Callable[..., Any], finished: Callable[[Any], None]) -> bool:
        if self._worker is not None:
            self.statusBar().showMessage("Vent til pågående arbeid er ferdig, eller avbryt det.")
            return False
        worker = Worker(operation)
        self._worker = worker
        self._operation = title
        worker.signals.progress.connect(self._log)
        worker.signals.finished.connect(lambda result: self._job_finished(result, finished))
        worker.signals.failed.connect(self._job_failed)
        self._set_busy(True)
        self._log(title)
        self._pool.start(worker)
        return True

    def _job_finished(self, result: Any, callback: Callable[[Any], None]) -> None:
        self._worker = None
        self._set_busy(False)
        if self._closing:
            self.close()
            return
        try:
            callback(result)
        except Exception as exc:
            self._log(f"Kunne ikke vise resultatet: {exc}")

    def _job_failed(self, message: str) -> None:
        operation = self._operation
        self._worker = None
        self._set_busy(False)
        self._log(f"{operation}: {message}")
        self.plan_summary.setText(f"{message} Tidligere importplan er beholdt.")
        if self._closing:
            self.close()

    def _set_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self.progress.setRange(0, 0 if busy else 100)
        self.cancel_button.setVisible(busy)
        self.cancel_button.setEnabled(busy)
        self.scan_button.setEnabled(not busy)
        self.mapping_button.setEnabled(not busy and self.plan is not None and bool(self.plan.reports))
        self.import_button.setEnabled(not busy and self.plan is not None and any(r.ready for r in self.plan.reports))
        self.backup_button.setEnabled(not busy)
        self.account_button.setEnabled(not busy)
        self.logout_button.setEnabled(not busy and self.actor is not None)
        self.save_settings_button.setEnabled(not busy and hasattr(self.runtime, "save_next_launch"))
        for widget in (*self.folder_fields, *self.folder_buttons):
            widget.setEnabled(not busy)
        self._refresh_server()

    def cancel_job(self) -> None:
        if self._worker is not None:
            self._worker.cancel.set()
            self.cancel_button.setEnabled(False)
            self._log("Avbryter etter pågående fil eller prøve. Allerede lagrede rapporter beholdes.")

    def _choose_folder(self, index: int) -> None:
        start = self.folder_fields[index].text()
        directory = QFileDialog.getExistingDirectory(self, f"Velg mappe {index + 1} fra kjøringen", start)
        if directory:
            self.folder_fields[index].setText(directory)

    def _folders_changed(self) -> None:
        if self.plan is not None:
            self.plan = None
            self.plan_tree.clear()
            self.plan_summary.setText("Mappevalget er endret. Kontroller filene på nytt før import.")
            self.import_button.setEnabled(False)
            self.mapping_button.setEnabled(False)
            self.metrics["samples"].setText("0")
            self.metrics["ready"].setText("0")

    def start_scan(self) -> None:
        if self._worker is not None:
            return
        self.navigate(1)
        folders = tuple(Path(field.text().strip()) for field in self.folder_fields if field.text().strip())
        if len(folders) != 5:
            self._log("Velg alle fem mappene før filkontroll.")
            return
        from pronto_ingest.discovery import discover_folders
        self._job("Kontrollerer filer i de fem mappene …", lambda progress, cancel: discover_folders(folders, progress=progress, cancel=cancel), self.show_plan)

    def show_plan(self, plan: Any) -> None:
        self.plan = plan
        self.plan_tree.clear()
        ready = sum(bool(report.ready) for report in plan.reports)
        self.metrics["samples"].setText(str(len(plan.reports)))
        self.metrics["ready"].setText(str(ready))
        summary = f"{len(plan.reports)} prøver funnet · {ready} klare · {len(plan.unassigned)} kilder uten kobling"
        if ready != len(plan.reports):
            summary += ". Prøver med avvik blir ikke importert."
        self.plan_summary.setText(summary)
        for report in plan.reports:
            root = QTreeWidgetItem([str(report.sample_id), str(report.run_id), "Klar" if report.ready else "Må avklares"])
            self.plan_tree.addTopLevelItem(root)
            for role, paths in report.files.items():
                for path in paths:
                    child = QTreeWidgetItem([ROLE_LABELS.get(role, role), Path(path).name, "Funnet"])
                    child.setToolTip(1, str(path))
                    root.addChild(child)
            for issue in report.issues:
                child = QTreeWidgetItem(["Avvik", str(issue), "Kontroller"])
                child.setToolTip(1, str(issue))
                root.addChild(child)
        if plan.unassigned:
            group = QTreeWidgetItem(["Kilder uten kobling", "Velg Koble kildefil for å tilordne", "Ikke inkludert"])
            self.plan_tree.addTopLevelItem(group)
            for candidate in plan.unassigned:
                item = QTreeWidgetItem([ROLE_LABELS.get(candidate.role, candidate.role), Path(candidate.path).name, "Uavklart"])
                item.setToolTip(1, str(candidate.path))
                group.addChild(item)
        for warning in plan.warnings:
            self.plan_tree.addTopLevelItem(QTreeWidgetItem(["Merknad", str(warning), "Kontroller"]))
        self._set_busy(False)
        self._log(summary)

    def map_source(self) -> None:
        if self.plan is None or self._worker is not None:
            return
        dialog = MappingDialog(self.plan, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            from pronto_ingest.discovery import assign_source
            try:
                plan = assign_source(self.plan, dialog.report.currentData(), dialog.role.currentData(), dialog.source.currentData())
            except Exception as exc:
                self._log(f"Koblingen ble ikke endret: {exc}")
            else:
                self.show_plan(plan)

    def prepare_import(self) -> None:
        if self.plan is None or self._worker is not None:
            return
        if self.actor is None:
            self._request_credentials(True)
        else:
            self._import_authenticated()

    def _request_credentials(self, import_after: bool) -> None:
        self._job("Kontrollerer brukerkonto …", lambda progress, cancel: self.runtime.has_users(), lambda has_users: self._credentials(bool(has_users), import_after))

    def _credentials(self, has_users: bool, import_after: bool) -> None:
        dialog = CredentialsDialog(first_user=not has_users, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            dialog.password.clear()
            if dialog.confirm is not None:
                dialog.confirm.clear()
            dialog.deleteLater()
            return
        username, password = dialog.username.text().strip(), dialog.password.text()
        dialog.password.clear()
        if dialog.confirm is not None:
            dialog.confirm.clear()
        dialog.deleteLater()
        def authenticate(progress: Any, cancel: Any) -> Any:
            if not has_users:
                self.runtime.create_user(username, password)
            return self.runtime.authenticate(username, password)
        self._job("Logger inn …", authenticate, lambda actor: self._authenticated(actor, import_after))

    def _authenticated(self, actor: Any, import_after: bool) -> None:
        if actor is None:
            self._log("Innlogging mislyktes. Kontroller brukernavn og passord og prøv igjen.")
            return
        if self.actor is not None and getattr(self.actor, "pk", str(self.actor)) != getattr(actor, "pk", str(actor)):
            self._history.clear()
            self._persisted_history.clear()
            self._render_history()
        self.actor = actor
        self.logout_button.setEnabled(True)
        self.account_state.setText(f"Innlogget for import: {getattr(actor, 'username', str(actor))}")
        self._log("Innlogging fullført.")
        if import_after:
            self._import_authenticated()
        else:
            self.refresh_counts()

    def _logout(self) -> None:
        self.actor = None
        self._history.clear()
        self._persisted_history.clear()
        self._render_history()
        self.logout_button.setEnabled(False)
        self.account_state.setText("Import krever innlogging med en PRONTO-bruker.")
        self.history_note.setText("Logg inn under Innstillinger for å vise din lagrede importhistorikk.")
        self._log("Du er logget ut av appen. Nettleserens innlogging styres i rapportserveren.")

    def _import_authenticated(self) -> None:
        if self.plan is None:
            return
        from pronto_ingest.importer import import_plan
        plan, actor = self.plan, self.actor
        self._job("Prosesserer og importerer data …", lambda progress, cancel: import_plan(plan, actor=actor, raw_root=self.runtime.raw_root, progress=progress, cancel=cancel), self._import_finished)

    def _import_finished(self, result: Any) -> None:
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        for item in result.items:
            self._history.append((now, str(item.sample_id), STATUS_LABELS.get(item.status, str(item.status)), str(item.message)))
        self._render_history()
        self.navigate(2)
        self._log("Importjobben er avsluttet. Se resultatet for hver prøve.")
        self.refresh_counts()

    def _render_history(self) -> None:
        rows = list(dict.fromkeys([*reversed(self._history), *self._persisted_history]))
        self.history_table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.history_table.setItem(row, col, item)

    def refresh_counts(self) -> None:
        if self._worker is not None:
            return
        def load(progress: Any, cancel: Any) -> dict:
            result = {"counts": self.runtime.report_counts()}
            if hasattr(self.runtime, "capabilities"):
                result["capabilities"] = self.runtime.capabilities()
            if self.actor is not None and hasattr(self.runtime, "import_history"):
                result["history"] = self.runtime.import_history(self.actor)
            return result
        self._job("Oppdaterer databaseoversikt …", load, self._show_counts)

    def _show_counts(self, result: dict[str, Any]) -> None:
        counts = result["counts"]
        count = counts.get("reports", counts.get("total", 0))
        self.metrics["reports"].setText(str(count))
        self.report_state.setText(f"{count} rapporter i den aktive databasen")
        if "capabilities" in result:
            capabilities = result["capabilities"]
            detail = " · ".join(f"{name}: {'funnet' if capabilities.get(name) else 'mangler'}" for name in ("pdfinfo", "pdftoppm"))
            message = f"PDF-kildeplott klare · {detail}" if capabilities.get("pdf") else (
                f"PDF-kildeplott krever Poppler · {detail}. Installer Poppler og start appen på nytt."
            )
            self.pdf_tools_status.setText(message)
        if "history" in result:
            self._persisted_history = []
            for entry in result["history"]:
                timestamp = str(entry.get("time", ""))
                try:
                    timestamp = datetime.fromisoformat(timestamp).astimezone().strftime("%d.%m.%Y %H:%M")
                except ValueError:
                    pass
                self._persisted_history.append((timestamp, str(entry.get("sample_id", "")), STATUS_LABELS.get(entry.get("status"), str(entry.get("status", ""))), str(entry.get("message", ""))))
            self._render_history()
            self.history_note.setText("Din lagrede importhistorikk og resultatene fra denne økten vises her.")
        self._log("Databaseoversikten er oppdatert.")

    def _refresh_server(self) -> None:
        running = self.runtime.server.running
        owned = self.runtime.server.owned
        busy = self._worker is not None
        self.server_status.setText("Kjører" if running else "Stoppet")
        self.server_status.setProperty("tone", "success" if running else "warning")
        self.server_status.style().unpolish(self.server_status)
        self.server_status.style().polish(self.server_status)
        self.server_address.setText(self.runtime.server.url)
        self.side_status.setText("Serveren kjører" if running else "Serveren er stoppet")
        self.start_button.setEnabled(not running and not busy)
        self.stop_button.setEnabled(running and owned and not busy)
        self.open_button.setEnabled(not busy)
        self.stop_button.setToolTip("Stopp serveren som appen startet" if owned else "Denne serveren ble startet utenfor appen")

    def start_server(self) -> None:
        self._job("Starter rapportserveren …", lambda progress, cancel: self.runtime.server.start(), lambda url: self._server_started(str(url), False))

    def _server_started(self, url: str, open_browser: bool) -> None:
        self._refresh_server()
        self._log(f"Rapportserveren er klar: {url}")
        if open_browser:
            self._open_url(url)

    def open_reports(self) -> None:
        if self.runtime.server.running:
            self._open_url(self.runtime.server.url)
        else:
            self._job("Starter rapportserveren …", lambda progress, cancel: self.runtime.server.start(), lambda url: self._server_started(str(url), True))

    def _open_url(self, url: str) -> None:
        if not QDesktopServices.openUrl(QUrl(url)):
            self._log(f"Nettleseren kunne ikke åpnes. Åpne adressen manuelt: {url}")

    def stop_server(self) -> None:
        self._job("Stopper rapportserveren …", lambda progress, cancel: self.runtime.server.stop(), lambda result: self._server_stopped())

    def _server_stopped(self) -> None:
        self._refresh_server()
        self._log("Rapportserveren er stoppet.")

    def backup(self) -> None:
        self._job("Oppretter sikkerhetskopi …", lambda progress, cancel: self.runtime.backup(), self._backup_finished)

    def _backup_finished(self, path: Path) -> None:
        self.backup_result.setText(f"Sikkerhetskopi opprettet: {path}")
        self._log(f"Sikkerhetskopi opprettet: {path}")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker is not None:
            self._closing = True
            self.cancel_job()
            self._log("Avslutter når pågående arbeid er trygt ferdig …")
            event.ignore()
            return
        self._timer.stop()
        event.accept()
