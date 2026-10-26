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
    QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLayout,
    QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .theme import build_stylesheet
from .branding import application_icon, icon_pixmap

ROLE_LABELS = {
    "metadata": "Kliniske metadata", "summary": "TMB / MSI-sammendrag",
    "variants": "Småvarianter", "sample_list": "Prøveliste",
    "cnv_table": "CNV-tabell", "rna_table": "RNA-tabell",
    "cnv_plot": "CNV-plott", "qc_plot": "QC-plott", "other_plot": "Andre plott",
    "linkage": "Prøvekobling", "cancan_table": "Cancan-tabell",
    "signature_plot": "Mutasjonssignatur", "rna_profile_plot": "RNA-profil",
    "supporting": "Tilleggsgrunnlag",
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
        self._source_revision = 0
        self._auto_scan_pending = False
        self._scan_timer = QTimer(self)
        self._scan_timer.setSingleShot(True)
        self._scan_timer.setInterval(600)
        self._scan_timer.timeout.connect(self._auto_scan)
        self._history: list[tuple[str, str, str, str]] = []
        self._persisted_history: list[tuple[str, str, str, str]] = []
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self.setWindowTitle("PRONTO")
        self.setWindowIcon(application_icon())
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
        body.setContentsMargins(24, 24, 24, 16)
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
        self.statusBar().showMessage("Klar")
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
        sidebar.setFixedWidth(184)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 28, 16, 24)
        layout.setSpacing(8)
        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)
        brand_row.addStretch()
        mark = QLabel()
        mark.setObjectName("app-mark")
        mark.setAccessibleName("PRONTO")
        mark.setPixmap(icon_pixmap(28))
        mark.setFixedSize(28, 28)
        brand_row.addWidget(mark)
        brand = label("PRONTO")
        brand.setWordWrap(False)
        brand.setObjectName("brand")
        brand_row.addWidget(brand)
        brand_row.addStretch()
        layout.addLayout(brand_row)
        layout.addSpacing(30)
        self.nav_buttons: list[QPushButton] = []
        for index, name in enumerate(("Oversikt", "Importer", "Rapporter", "Innstillinger", "Log")):
            nav = button(name, f"nav-{index}")
            nav.setCheckable(True)
            nav.setProperty("nav", True)
            nav.setToolTip(f"{name} (Ctrl+{index + 1})")
            nav.clicked.connect(lambda checked=False, page=index: self.navigate(page))
            self.nav_buttons.append(nav)
            layout.addWidget(nav)
        layout.addStretch()
        caption = label("LOKAL SERVER")
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
        self.open_button = button("Åpne rapporter", "open-reports")
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
        if intro:
            layout.addWidget(label(intro, muted=True))
        return widget, layout

    def _overview(self) -> QWidget:
        page, layout = self._page("Oversikt", "")
        row = QHBoxLayout()
        self.metrics: dict[str, QLabel] = {}
        for key, title in (("reports", "Rapporter"), ("samples", "Prøver funnet"), ("ready", "Valgt for import")):
            frame, contents = card()
            contents.addWidget(label(title, muted=True))
            value = label("—" if key == "reports" else "0")
            value.setProperty("metric", True)
            self.metrics[key] = value
            contents.addWidget(value)
            row.addWidget(frame, 1)
        layout.addLayout(row)
        frame, contents = card()
        contents.addWidget(label("Ny kjøring", section=True))
        actionrow = QHBoxLayout()
        self.begin_button = button("Importer kjøring", "begin-import", primary=True)
        self.begin_button.clicked.connect(lambda: self.navigate(1))
        actionrow.addWidget(self.begin_button)
        actionrow.addStretch()
        contents.addLayout(actionrow)
        layout.addWidget(frame)
        layout.addStretch()
        return page

    def _import_page(self) -> QWidget:
        page, layout = self._page("Importer kjøring", "")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setObjectName("page")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 4, 0)
        inner_layout.setSpacing(12)
        foldercard, contents = card()
        heading = QHBoxLayout()
        heading.addWidget(label("Kilder", section=True))
        heading.addStretch()
        self.more_folders_button = button("Flere mapper", "more-folders")
        self.more_folders_button.setCheckable(True)
        self.more_folders_button.toggled.connect(self._toggle_folders)
        heading.addWidget(self.more_folders_button)
        contents.addLayout(heading)
        grid = QGridLayout()
        grid.setHorizontalSpacing(9)
        grid.setVerticalSpacing(7)
        self.folder_fields: list[QLineEdit] = []
        self.folder_buttons: list[QPushButton] = []
        self.folder_labels: list[QLabel] = []
        for index in range(5):
            field = QLineEdit()
            field.setAccessibleName(f"Mappe {index + 1}")
            field.setObjectName(f"folder-{index + 1}")
            field.setPlaceholderText("Mappe med kjøring og analyseresultater" if index == 0 else "Valgfri resultatmappe")
            field.textChanged.connect(self._folders_changed)
            browse = button("Velg …", f"choose-folder-{index + 1}")
            browse.setAccessibleName(f"Velg mappe {index + 1}")
            browse.clicked.connect(lambda checked=False, slot=index: self._choose_folder(slot))
            title = label("&Mappe" if index == 0 else f"Mappe {index + 1}")
            title.setBuddy(field)
            grid.addWidget(title, index, 0)
            grid.addWidget(field, index, 1)
            grid.addWidget(browse, index, 2)
            self.folder_fields.append(field)
            self.folder_buttons.append(browse)
            self.folder_labels.append(title)
            if index:
                for widget in (field, browse, title):
                    widget.hide()
        grid.setColumnStretch(1, 1)
        contents.addLayout(grid)
        options = QGridLayout()
        options.setHorizontalSpacing(12)
        self.report_version = QComboBox()
        self.report_version.setObjectName("report-version")
        self.report_version.setAccessibleName("Filversjon")
        self.report_version.setToolTip("Nyeste tilgjengelige prioriterer report_preQC_newPRONTO_version, deretter report_preQC og rådata.")
        for text, value in (("Nyeste tilgjengelige", "auto"), ("Ny PRONTO-versjon", "new"), ("Tidligere PRONTO-versjon", "legacy"), ("Rådata", "raw")):
            self.report_version.addItem(text, value)
        self.cnv_source = QComboBox()
        self.cnv_source.setObjectName("cnv-source")
        self.cnv_source.setAccessibleName("CNV-tabell")
        self.cnv_source.addItem("Sammenslått CNV-tabell", "merged")
        self.cnv_source.addItem("Cancan", "cancan")
        self.cnv_solution = QComboBox()
        self.cnv_solution.setObjectName("cnv-solution")
        self.cnv_solution.setAccessibleName("Cancan-løsning")
        for text, value in (("Main", "main"), ("Alternativ 01", "alt01"), ("Alternativ 02", "alt02")):
            self.cnv_solution.addItem(text, value)
        self.cnv_solution.setEnabled(False)
        for column, (title, widget) in enumerate((("Filversjon", self.report_version), ("CNV-tabell", self.cnv_source), ("Cancan-løsning", self.cnv_solution))):
            caption = label(title)
            caption.setBuddy(widget)
            options.addWidget(caption, 0, column)
            options.addWidget(widget, 1, column)
            options.setColumnStretch(column, 1)
            widget.currentIndexChanged.connect(self._import_options_changed)
        self.advanced_import = QWidget()
        self.advanced_import.setLayout(options)
        self.advanced_import.hide()
        advanced = button('Avansert', 'advanced-import-options')
        advanced.setCheckable(True)
        advanced.toggled.connect(self.advanced_import.setVisible)
        contents.addWidget(advanced, alignment=Qt.AlignmentFlag.AlignRight)
        contents.addWidget(self.advanced_import)
        inner_layout.addWidget(foldercard)
        self.plan_summary = label("Velg mappe. Filene finnes automatisk.", muted=True)
        self.plan_hint = label("", muted=True)
        self.plan_hint.setAccessibleName("Veiledning for prøvevalg")
        self.plan_hint.hide()
        summary_labels = QVBoxLayout()
        summary_labels.setSpacing(4)
        summary_labels.addWidget(self.plan_summary)
        summary_labels.addWidget(self.plan_hint)
        selection_row = QHBoxLayout()
        selection_row.addLayout(summary_labels, 1)
        self.select_ready_button = button("Velg klare prøver", "select-ready-samples")
        self.select_ready_button.clicked.connect(self.select_ready_samples)
        self.select_ready_button.setEnabled(False)
        selection_row.addWidget(self.select_ready_button)
        inner_layout.addLayout(selection_row)
        self.plan_tree = QTreeWidget()
        self.plan_tree.setObjectName("import-plan")
        self.plan_tree.setAccessibleName("Importplan med prøver, kildefiler og avvik")
        self.plan_tree.setHeaderLabels(["Prøve / kilde", "Kjøring / fil", "Metadata", "Status"])
        self.plan_tree.setAlternatingRowColors(True)
        self.plan_tree.setMinimumHeight(160)
        self.plan_tree.setUniformRowHeights(True)
        self.plan_tree.itemChanged.connect(self._selection_changed)
        self.plan_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.plan_tree.setColumnWidth(0, 230)
        self.plan_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.plan_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.plan_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
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
        self.mapping_button.hide()
        self.advanced_sources_button = button("Filvalg", "advanced-sources")
        self.advanced_sources_button.setCheckable(True)
        self.advanced_sources_button.setToolTip("Vis manuell kobling av kildefiler")
        self.advanced_sources_button.setEnabled(False)
        self.advanced_sources_button.toggled.connect(lambda: self._set_busy(self._worker is not None))
        self.cancel_button = button("Avbryt", "cancel-job")
        self.cancel_button.clicked.connect(self.cancel_job)
        self.cancel_button.hide()
        self.import_button = button("Importer valgte", "import-data", primary=True)
        self.import_button.clicked.connect(self.prepare_import)
        self.import_button.setEnabled(False)
        actions.addWidget(self.scan_button)
        actions.addWidget(self.advanced_sources_button)
        actions.addWidget(self.mapping_button)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        actions.addWidget(self.import_button)
        layout.addLayout(actions)
        return page

    def _reports_page(self) -> QWidget:
        page, layout = self._page("Rapporter", "Importhistorikk for innlogget bruker.")
        self.report_state = label("Henter rapportstatus …", section=True)
        layout.addWidget(self.report_state)
        self.history_table = table(["Tidspunkt", "Prøve", "Resultat", "Melding"])
        self.history_table.setObjectName("import-history")
        self.history_table.setAccessibleName("Resultater og historikk for importjobber")
        for column in range(3):
            self.history_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.history_table, 1)
        self.history_note = label("Logg inn under Innstillinger for å se historikken.", muted=True)
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
        page, layout = self._page("Innstillinger", "")
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
        storage_row = QHBoxLayout()
        storage_row.addWidget(frame, 1)
        selection, selection_contents = card()
        selection_contents.addWidget(label("Neste oppstart", section=True))
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
        new_database = button('Ny tom database …', 'new-empty-database')
        new_database.clicked.connect(self._new_database)
        selection_contents.addWidget(new_database)
        selection_contents.addStretch()
        storage_row.addWidget(selection, 1)
        layout.addLayout(storage_row)
        marker_card, marker_layout = card()
        marker_layout.addWidget(label('Biomarkørliste', section=True))
        self.marker_status = label('Ingen fil valgt', muted=True)
        if getattr(self.runtime, 'biomarker_info', None):
            info = self.runtime.biomarker_info
            self.marker_status.setText(f'{info["name"]} · {len(info["genes"])} gener')
        marker_layout.addWidget(self.marker_status)
        marker_button = button('Velg XLSX …', 'choose-biomarker-list')
        marker_button.clicked.connect(self._choose_biomarker_list)
        marker_layout.addWidget(marker_button, alignment=Qt.AlignmentFlag.AlignLeft)
        preferences_row = QHBoxLayout()
        preferences_row.addWidget(marker_card, 1)
        frame, contents = card()
        contents.addWidget(label("Sikkerhetskopi", section=True))
        contents.addWidget(label("Lag en kopi av databasen. Kildearkiv og nøkkel må sikkerhetskopieres separat."))
        row = QHBoxLayout()
        self.backup_button = button("Ta sikkerhetskopi", "backup-database")
        self.backup_button.clicked.connect(self.backup)
        row.addWidget(self.backup_button)
        row.addStretch()
        contents.addLayout(row)
        self.backup_result = label("", muted=True)
        self.backup_result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        contents.addWidget(self.backup_result)
        preferences_row.addWidget(frame, 1)
        layout.addLayout(preferences_row)
        self.account_state = label("Ikke innlogget", muted=True)
        layout.addWidget(self.account_state)
        self.account_button = button("Logg inn", "manage-account")
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
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        return scroll

    def _choose_data_root(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Velg datamappe ved neste oppstart", self.next_root.text())
        if directory:
            self.next_root.setText(directory)

    def _new_database(self):
        directory = QFileDialog.getExistingDirectory(self, 'Ny database: velg en tom mappe')
        if directory:
            self._job('Klargjør ny database …', lambda progress, cancel: self.runtime.prepare_empty_database(Path(directory)),
                      lambda result: self._log('Ny tom database valgt. Start appen på nytt.'))

    def _choose_biomarker_list(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Biomarkørliste', '', 'Excel (*.xlsx)')
        if path:
            self._job('Leser biomarkørliste …', lambda progress, cancel: self.runtime.set_biomarker_list(Path(path)),
                      lambda result: self.marker_status.setText(f'{result["name"]} · {len(result["genes"])} gener'))

    def _save_next_launch(self) -> None:
        root, port = Path(self.next_root.text()), self.next_port.value()
        self._job("Lagrer oppstartsinnstillinger …", lambda progress, cancel: self.runtime.save_next_launch(root, port), lambda result: self._log("Innstillingene er lagret. Lukk og åpne appen for å bruke den valgte datamappen."))

    def _diagnostics_page(self) -> QWidget:
        page, layout = self._page("Log", "")
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
        layout.addWidget(label("Loggen kan inneholde prøve-ID og filstier.", muted=True))
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
        self._resume_auto_scan()

    def _job_failed(self, message: str) -> None:
        operation = self._operation
        self._worker = None
        self._set_busy(False)
        self._log(f"{operation}: {message}")
        self.plan_summary.setText(f"{message}" + (" Forrige importplan er beholdt." if self.plan is not None else ""))
        if self._closing:
            self.close()
        else:
            self._resume_auto_scan()

    def _set_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self.progress.setRange(0, 0 if busy else 100)
        self.cancel_button.setVisible(busy)
        self.cancel_button.setEnabled(busy)
        self.scan_button.setEnabled(not busy)
        self.advanced_sources_button.setEnabled(not busy and self.plan is not None)
        self.mapping_button.setVisible(self.plan is not None and (
            self.advanced_sources_button.isChecked() or any(report.issues for report in self.plan.reports)))
        self.mapping_button.setEnabled(not busy and self.plan is not None and bool(self.plan.reports))
        self.select_ready_button.setEnabled(not busy and self.plan is not None and any(
            self._eligible_for_selection(report) and not getattr(report, "selected", True)
            for report in self.plan.reports))
        self.import_button.setEnabled(not busy and self.plan is not None and any(r.ready and getattr(r, "selected", True) for r in self.plan.reports))
        self.backup_button.setEnabled(not busy)
        self.account_button.setEnabled(not busy)
        self.logout_button.setEnabled(not busy and self.actor is not None)
        self.save_settings_button.setEnabled(not busy and hasattr(self.runtime, "save_next_launch"))
        for widget in (*self.folder_fields, *self.folder_buttons):
            widget.setEnabled(not busy)
        self.more_folders_button.setEnabled(not busy)
        self.report_version.setEnabled(not busy)
        self.cnv_source.setEnabled(not busy)
        self.cnv_solution.setEnabled(not busy and self.cnv_source.currentData() == "cancan")
        self.plan_tree.setEnabled(not busy)
        self._refresh_server()

    def cancel_job(self) -> None:
        self._scan_timer.stop()
        self._auto_scan_pending = False
        self._source_revision += 1
        if self._worker is not None:
            self._worker.cancel.set()
            self.cancel_button.setEnabled(False)
            self._log("Avbryter etter pågående fil eller prøve. Allerede lagrede rapporter beholdes.")

    def _choose_folder(self, index: int) -> None:
        start = self.folder_fields[index].text()
        directory = QFileDialog.getExistingDirectory(self, f"Velg mappe {index + 1} fra kjøringen", start)
        if directory:
            if directory == self.folder_fields[index].text():
                self._folders_changed()
            else:
                self.folder_fields[index].setText(directory)
            self._scan_timer.stop()
            self._auto_scan()

    def _toggle_folders(self, expanded: bool) -> None:
        for index in range(1, len(self.folder_fields)):
            for widget in (self.folder_fields[index], self.folder_buttons[index], self.folder_labels[index]):
                widget.setVisible(expanded)
        self._folder_button_text()

    def _folder_button_text(self) -> None:
        count = sum(bool(field.text().strip()) for field in self.folder_fields[1:])
        text = "Færre mapper" if self.more_folders_button.isChecked() else "Flere mapper"
        if count:
            text += f" ({count})"
        self.more_folders_button.setText(text)

    def _import_options_changed(self) -> None:
        self.cnv_solution.setEnabled(self.cnv_source.currentData() == "cancan" and self._worker is None)
        self._folders_changed()

    def _folders_changed(self) -> None:
        self._source_revision += 1
        self._scan_timer.stop()
        self._folder_button_text()
        if self.plan is not None:
            self.plan = None
            self.plan_tree.clear()
            self.import_button.setEnabled(False)
            self.mapping_button.setEnabled(False)
            self.metrics["samples"].setText("0")
            self.metrics["ready"].setText("0")
        self.plan_hint.hide()
        self.mapping_button.hide()
        self.advanced_sources_button.setChecked(False)
        self.advanced_sources_button.setEnabled(False)
        self.select_ready_button.setEnabled(False)
        paths = [field.text().strip() for field in self.folder_fields if field.text().strip()]
        self._auto_scan_pending = bool(paths) and all(Path(path).is_absolute() for path in paths)
        self.plan_summary.setText("Finner filer automatisk …" if self._auto_scan_pending
                                  else "Velg mappe. Filene finnes automatisk.")
        if self._auto_scan_pending and not self._closing:
            self._scan_timer.start(600)

    def _resume_auto_scan(self) -> None:
        if self._auto_scan_pending and not self._closing and not self._scan_timer.isActive():
            self._scan_timer.start(0)

    def _auto_scan(self) -> None:
        if self._closing or not self._auto_scan_pending or self._worker is not None:
            return
        self.start_scan(automatic=True)

    def start_scan(self, *, automatic: bool = False) -> None:
        if self._worker is not None:
            return
        self._scan_timer.stop()
        self._auto_scan_pending = False
        self.navigate(1)
        folders = tuple(Path(field.text().strip()) for field in self.folder_fields if field.text().strip())
        if not folders:
            self.plan_summary.setText("Velg minst én mappe før filkontroll.")
            self._log("Velg minst én mappe før filkontroll.")
            self.folder_fields[0].setFocus()
            return
        from pronto_ingest.discovery import discover_folders
        options = {"report_version": self.report_version.currentData(), "cnv_source": self.cnv_source.currentData(), "cnv_solution": self.cnv_solution.currentData()}
        revision = self._source_revision
        def discover(progress: Any, cancel: Any) -> Any:
            # Network paths and existence checks remain outside the GUI thread.
            if automatic and not all(folder.is_dir() for folder in folders):
                return None
            return discover_folders(folders, progress=progress, cancel=cancel, **options)
        self._job("Finner og kobler filer …", discover, lambda plan: self._scan_finished(plan, revision))

    def _scan_finished(self, plan: Any, revision: int) -> None:
        if revision != self._source_revision:
            return
        if plan is None:
            self.plan_summary.setText("Velg en eksisterende mappe.")
            return
        self.show_plan(plan)

    def show_plan(self, plan: Any) -> None:
        self._scan_timer.stop()
        self._auto_scan_pending = False
        self.plan = plan
        self.plan_tree.blockSignals(True)
        self.plan_tree.clear()
        for report in plan.reports:
            root = QTreeWidgetItem([str(report.sample_id), str(report.run_id), getattr(report, "metadata_flag", "") or "—", self._report_status(report)])
            root.setData(0, Qt.ItemDataRole.UserRole, report.key)
            root.setToolTip(0, str(report.sample_id))
            root.setToolTip(1, str(report.run_id))
            flag = getattr(report, "metadata_flag", "").strip().upper()
            if flag not in {"N", "NO", "NEI", "FALSE", "0"}:
                root.setFlags(root.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                root.setCheckState(0, Qt.CheckState.Checked if getattr(report, "selected", True) else Qt.CheckState.Unchecked)
            else:
                root.setFlags(root.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            root.setToolTip(2, "Create_report i metadata. Tomt felt eller «-» krever at du velger prøven for import.")
            self.plan_tree.addTopLevelItem(root)
            for role, paths in report.files.items():
                for path in paths:
                    child = QTreeWidgetItem([ROLE_LABELS.get(role, role), Path(path).name, "", "Funnet"])
                    child.setToolTip(1, str(path))
                    root.addChild(child)
            for issue in report.issues:
                child = QTreeWidgetItem(["Avvik", str(issue), "", "Kontroller"])
                child.setToolTip(1, str(issue))
                root.addChild(child)
        if plan.unassigned:
            group = QTreeWidgetItem(["Andre filer", str(len(plan.unassigned)), "", "Ikke brukt"])
            group.setToolTip(0, "Filer som ikke inngår i det valgte rapportgrunnlaget.")
            self.plan_tree.addTopLevelItem(group)
            for candidate in plan.unassigned:
                item = QTreeWidgetItem([ROLE_LABELS.get(candidate.role, candidate.role), Path(candidate.path).name, "", "Ikke brukt"])
                item.setToolTip(1, str(candidate.path))
                group.addChild(item)
        for warning in plan.warnings:
            item = QTreeWidgetItem(["Merknad", str(warning), "", "Kontroller"])
            item.setToolTip(1, str(warning))
            self.plan_tree.addTopLevelItem(item)
        self.plan_tree.blockSignals(False)
        self._update_plan_summary()
        self._set_busy(False)
        self._log(self.plan_summary.text())

    @staticmethod
    def _report_status(report: Any) -> str:
        if getattr(report, "metadata_flag", "").strip().upper() in {"N", "NO", "NEI", "FALSE", "0"}:
            return "Sperret i metadata"
        if not report.ready:
            return "Må avklares"
        return "Klar" if getattr(report, "selected", True) else "Ikke valgt"

    @staticmethod
    def _eligible_for_selection(report: Any) -> bool:
        return bool(report.ready and getattr(report, "metadata_flag", "").strip().upper()
                    in {"", "-", "Y", "YES", "JA", "TRUE", "1"})

    def select_ready_samples(self) -> None:
        if self.plan is None or self._worker is not None:
            return
        from pronto_ingest.discovery import set_report_selected
        plan = self.plan
        for report in self.plan.reports:
            if self._eligible_for_selection(report) and not report.selected:
                plan = set_report_selected(plan, report.key, True)
        self.show_plan(plan)

    def _update_plan_summary(self) -> None:
        if self.plan is None:
            return
        ready = sum(self._eligible_for_selection(report) for report in self.plan.reports)
        selected = sum(bool(report.ready and getattr(report, "selected", True)) for report in self.plan.reports)
        self.metrics["samples"].setText(str(len(self.plan.reports)))
        self.metrics["ready"].setText(str(selected))
        summary = f"{len(self.plan.reports)} prøver · {ready} klare · {selected} valgt for import"
        self.plan_summary.setText(summary)
        if ready:
            if ready != len(self.plan.reports):
                self.plan_hint.setText("Klare prøver kan importeres. Kontroller øvrige avvik.")
            else:
                self.plan_hint.setText("Filer funnet. Velg prøver for import." if not selected
                                       else "Filer funnet. Kontroller prøvevalget før import.")
        else:
            self.plan_hint.setText("Kontroller avvikene under prøvene." if self.plan.reports
                                   else "Fant ingen prøver. Kontroller at riktig kjøringsmappe er valgt.")
        self.plan_hint.show()

    def _selection_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0 or self.plan is None or self._worker is not None:
            return
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if not key:
            return
        from pronto_ingest.discovery import set_report_selected
        try:
            self.plan = set_report_selected(self.plan, key, item.checkState(0) == Qt.CheckState.Checked)
        except ValueError as exc:
            self._log(str(exc))
            self.show_plan(self.plan)
            return
        report = next(report for report in self.plan.reports if report.key == key)
        self.plan_tree.blockSignals(True)
        item.setText(3, self._report_status(report))
        self.plan_tree.blockSignals(False)
        self._update_plan_summary()
        self.statusBar().showMessage(self.plan_summary.text())
        self._set_busy(False)

    def map_source(self) -> None:
        if self.plan is None or self._worker is not None:
            return
        dialog = MappingDialog(self.plan, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            from pronto_ingest.discovery import assign_source
            plan, revision = self.plan, self._source_revision
            key, role, source = dialog.report.currentData(), dialog.role.currentData(), dialog.source.currentData()
            self._job("Kontrollerer filvalg …", lambda progress, cancel: assign_source(plan, key, role, source),
                      lambda result: self._scan_finished(result, revision))

    def prepare_import(self) -> None:
        if self.plan is None or self._worker is not None:
            return
        if not any(report.ready and getattr(report, "selected", True) for report in self.plan.reports):
            self.plan_summary.setText("Velg minst én prøve uten avvik for import.")
            self.plan_tree.setFocus()
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
        self.account_state.setText(f"Innlogget: {getattr(actor, 'username', str(actor))}")
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
        self.account_state.setText("Ikke innlogget")
        self.history_note.setText("Logg inn under Innstillinger for å se historikken.")
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
            self.history_note.setText("Lagret importhistorikk og resultater fra denne økten.")
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
        self._scan_timer.stop()
        self._auto_scan_pending = False
        if self._worker is not None:
            self._closing = True
            self.cancel_job()
            self._log("Avslutter når pågående arbeid er trygt ferdig …")
            event.ignore()
            return
        self._timer.stop()
        event.accept()
