"""Modular HTML renderer for validated PRONTO report snapshots."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Mapping

from pronto_report.models import ReportData, ReviewState


_PACKAGE_ROOT = Path(__file__).parents[1]
_TEMPLATE_ROOT = _PACKAGE_ROOT / "templates"
_PANEL_TEMPLATES = (
    "key-findings.html",
    "variant-review.html",
    "cnv-plots.html",
    "sequencing-qc.html",
    "tumour-board.html",
)


def _read_template(relative_path: str) -> str:
    return (_TEMPLATE_ROOT / relative_path).read_text(encoding="utf-8")


def _assemble_template() -> str:
    document = _read_template("report/base.html")
    for filename in _PANEL_TEMPLATES:
        include = f'{{% include "report/{filename}" %}}'
        document = document.replace(include, _read_template(f"report/{filename}"))
    return document


def _render_variables(template: str, context: Mapping[str, str]) -> str:
    document = template
    for name, value in context.items():
        document = document.replace(f"{{{{ {name} }}}}", escape(value, quote=True))
    return document


def render_html(report: ReportData, review: ReviewState | None = None) -> str:
    """Render the development HTML shell from validated contract models.

    Assets remain separate during development. Task 14 will bundle the same
    templates and assets into the deterministic, self-contained export.
    """
    if review is not None and review.report_id != report.report_id:
        raise ValueError("Review state does not belong to this report")

    status = review.status if review is not None else "DRAFT"
    status_label = "Endelig" if status == "FINAL" else "Utkast"
    context = {
        "sample_id": str(report.sample["sampleId"]),
        "report_id": report.report_id,
        "status_code": status.lower(),
        "status_label": status_label,
        "stylesheet_url": "/pronto_report/static/report.css",
        "script_url": "/pronto_report/static/report.js",
    }
    return _render_variables(_assemble_template(), context)
