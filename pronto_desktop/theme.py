"""Shared visual tokens for the native PRONTO workstation."""

COLORS = {
    "navy": "#12293D", "teal": "#006A68", "background": "#F3F6F8",
    "surface": "#FFFFFF", "text": "#182D3D", "muted": "#4B6172",
    "border": "#CED9E0", "focus": "#007C91", "success": "#146442",
    "warning": "#865400", "danger": "#A32735",
}


def build_stylesheet() -> str:
    return """
    * { font-family: 'Segoe UI', sans-serif; font-size: 14px; color: #182D3D; }
    QMainWindow, QWidget#shell, QWidget#content, QScrollArea, QWidget#page {
        background: #F3F6F8; }
    QScrollArea { border: none; }
    QFrame#sidebar { background: #12293D; border: none; }
    QLabel#brand { color: white; font-size: 29px; font-weight: 750; }
    QLabel#brand-detail { color: #BFD3DF; font-size: 14px; }
    QLabel#sidebar-caption { color: #BFD3DF; font-size: 14px; }
    QLabel#sidebar-status { color: white; font-size: 14px; }
    QLabel#page-title { font-size: 25px; font-weight: 700; }
    QLabel[muted='true'] { color: #4B6172; }
    QLabel[section='true'] { font-size: 17px; font-weight: 650; }
    QLabel[metric='true'] { font-size: 31px; font-weight: 700; color: #006A68; }
    QFrame[card='true'] { background: white; border: 1px solid #CED9E0; border-radius: 8px; }
    QLabel[status='true'] { background: #EAF0F4; border-radius: 5px; padding: 5px 9px; font-weight: 600; }
    QLabel[status='true'][tone='success'] { background: #E4F2EB; color: #146442; }
    QLabel[status='true'][tone='warning'] { background: #FFF1DA; color: #865400; }
    QLabel[status='true'][tone='danger'] { background: #FDEBED; color: #A32735; }
    QLabel[tone='danger'] { color: #A32735; }
    QPushButton { background: #FFFFFF; border: 1px solid #A7BAC7; border-radius: 6px;
        min-height: 40px; padding: 0 13px; font-weight: 600; }
    QPushButton:hover { background: #E9F3F4; border-color: #006A68; }
    QPushButton:pressed { background: #D5E9E9; }
    QPushButton:focus { border: 3px solid #007C91; }
    QPushButton:disabled { background: #EDF1F4; color: #647583; border-color: #CED9E0; }
    QPushButton[primary='true'] { background: #006A68; color: white; border-color: #006A68; }
    QPushButton[primary='true']:hover { background: #005452; }
    QPushButton[primary='true']:disabled { background: #DFE9E9; color: #556F70; border-color: #C4D6D6; }
    QPushButton[nav='true'] { text-align: left; color: #DFEAF1; background: transparent;
        border: 1px solid transparent; min-height: 44px; }
    QPushButton[nav='true']:hover { background: #213E54; }
    QPushButton[nav='true']:checked { color: white; background: #244B5C; border-color: #6EA9AD; }
    QPushButton[nav='true']:focus { border: 3px solid #84D0D0; }
    QLineEdit, QSpinBox, QComboBox { background: white; border: 1px solid #A7BAC7;
        border-radius: 5px; padding: 7px 9px; min-height: 23px; selection-background-color: #006A68; }
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTreeWidget:focus, QTableWidget:focus {
        border: 2px solid #007C91; }
    QLineEdit:read-only { background: #F5F8FA; color: #405867; }
    QPlainTextEdit { background: white; border: 1px solid #CED9E0; padding: 9px; }
    QTreeWidget, QTableWidget { background: white; alternate-background-color: #F5F8FA;
        border: 1px solid #CED9E0; border-radius: 5px; gridline-color: #E6EDF1;
        selection-background-color: #D7EBED; selection-color: #182D3D; }
    QTreeWidget::item { min-height: 29px; }
    QHeaderView::section { background: #EAF0F4; color: #314B5C; border: none;
        border-bottom: 1px solid #CED9E0; padding: 8px; font-weight: 600; }
    QProgressBar { background: #E6EDF0; border: none; border-radius: 3px; min-height: 5px; }
    QProgressBar::chunk { background: #007C7A; border-radius: 3px; }
    QStatusBar { background: white; border-top: 1px solid #CED9E0; }
    QToolTip { background: #12293D; color: white; border: none; padding: 7px; }
    QDialog { background: #F3F6F8; }
    """
