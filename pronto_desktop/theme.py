"""Shared visual tokens for the native PRONTO workstation."""

COLORS = {
    "navy": "#12293D", "teal": "#006A68", "background": "#F3F6F8",
    "surface": "#FFFFFF", "text": "#182D3D", "muted": "#4B6172",
    "border": "#CED9E0", "focus": "#007C91", "success": "#146442",
    "warning": "#865400", "danger": "#A32735",
    "nav_muted": "#BFD3DF", "nav_text": "#DFEAF1", "nav_hover": "#213E54",
    "nav_selected": "#244B5C", "nav_border": "#6EA9AD", "nav_focus": "#84D0D0",
    "hover": "#E9F3F4", "pressed": "#D5E9E9", "primary_hover": "#005452",
    "control_border": "#A7BAC7", "disabled": "#EDF1F4", "disabled_text": "#647583",
    "primary_disabled": "#DFE9E9", "primary_disabled_text": "#556F70",
    "primary_disabled_border": "#C4D6D6", "subtle": "#F5F8FA",
    "selection": "#D7EBED", "header": "#EAF0F4", "header_text": "#314B5C",
    "grid": "#E6EDF1", "success_bg": "#E4F2EB", "warning_bg": "#FFF1DA",
    "danger_bg": "#FDEBED",
}


def build_stylesheet() -> str:
    stylesheet = """
    * { font-family: 'Segoe UI', sans-serif; font-size: 14px; color: @text; }
    QMainWindow, QWidget#shell, QWidget#content, QScrollArea, QWidget#page {
        background: @background; }
    QScrollArea { border: none; }
    QFrame#sidebar { background: @navy; border: none; }
    QLabel#brand { color: @surface; font-size: 28px; font-weight: 700; }
    QLabel#brand-detail { color: @nav_muted; font-size: 14px; }
    QLabel#sidebar-caption { color: @nav_muted; font-size: 12px; font-weight: 600; }
    QLabel#sidebar-status { color: @surface; font-size: 14px; }
    QLabel#page-title { font-size: 26px; font-weight: 650; }
    QLabel[muted='true'] { color: @muted; }
    QLabel[section='true'] { font-size: 17px; font-weight: 600; }
    QLabel[metric='true'] { font-size: 32px; font-weight: 600; color: @text; }
    QFrame[card='true'] { background: @surface; border: 1px solid @border; border-radius: 6px; }
    QLabel[status='true'] { background: @header; border-radius: 4px; padding: 5px 9px; font-weight: 600; }
    QLabel[status='true'][tone='success'] { background: @success_bg; color: @success; }
    QLabel[status='true'][tone='warning'] { background: @warning_bg; color: @warning; }
    QLabel[status='true'][tone='danger'] { background: @danger_bg; color: @danger; }
    QLabel[tone='danger'] { color: @danger; }
    QPushButton { background: @surface; border: 1px solid @control_border; border-radius: 5px;
        min-height: 40px; padding: 0 13px; font-weight: 600; }
    QPushButton:hover { background: @hover; border-color: @teal; }
    QPushButton:pressed { background: @pressed; }
    QPushButton:focus { border: 3px solid @focus; }
    QPushButton:disabled { background: @disabled; color: @disabled_text; border-color: @border; }
    QPushButton[primary='true'] { background: @teal; color: @surface; border-color: @teal; }
    QPushButton[primary='true']:hover { background: @primary_hover; }
    QPushButton[primary='true']:disabled { background: @primary_disabled; color: @primary_disabled_text; border-color: @primary_disabled_border; }
    QPushButton[nav='true'] { text-align: left; color: @nav_text; background: transparent;
        border: 1px solid transparent; min-height: 44px; }
    QPushButton[nav='true']:hover { background: @nav_hover; }
    QPushButton[nav='true']:checked { color: @surface; background: @nav_selected; border-color: @nav_border; }
    QPushButton[nav='true']:focus { border: 3px solid @nav_focus; }
    QLineEdit, QSpinBox, QComboBox { background: @surface; border: 1px solid @control_border;
        border-radius: 4px; padding: 7px 9px; min-height: 23px; selection-background-color: @teal; }
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTreeWidget:focus, QTableWidget:focus {
        border: 2px solid @focus; }
    QLineEdit:read-only { background: @subtle; color: @muted; }
    QComboBox:disabled { background: @disabled; color: @disabled_text; }
    QPlainTextEdit { background: @surface; border: 1px solid @border; padding: 8px; }
    QTreeWidget, QTableWidget { background: @surface; alternate-background-color: @subtle;
        border: 1px solid @border; border-radius: 4px; gridline-color: @grid;
        selection-background-color: @selection; selection-color: @text; }
    QTreeWidget::item { min-height: 30px; }
    QTreeWidget::indicator { width: 16px; height: 16px; }
    QHeaderView::section { background: @header; color: @header_text; border: none;
        border-bottom: 1px solid @border; padding: 8px; font-weight: 600; }
    QProgressBar { background: @grid; border: none; border-radius: 2px; min-height: 5px; }
    QProgressBar::chunk { background: @teal; border-radius: 2px; }
    QStatusBar { background: @surface; border-top: 1px solid @border; }
    QToolTip { background: @navy; color: @surface; border: none; padding: 8px; }
    QDialog { background: @background; }
    """
    for name, color in sorted(COLORS.items(), key=lambda item: -len(item[0])):
        stylesheet = stylesheet.replace("@" + name, color)
    return stylesheet
