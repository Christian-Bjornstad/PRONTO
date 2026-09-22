"""Modular HTML renderer for validated PRONTO report snapshots."""

from __future__ import annotations

from html import escape
from pathlib import Path
import re
from decimal import Decimal
from typing import Any, Mapping

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
_PLACEHOLDER = re.compile(r"{{\s*([a-z_]+)\s*}}")


def _read_template(relative_path: str) -> str:
    return (_TEMPLATE_ROOT / relative_path).read_text(encoding="utf-8")


def _assemble_template() -> str:
    document = _read_template("report/base.html")
    for filename in _PANEL_TEMPLATES:
        include = f'{{% include "report/{filename}" %}}'
        document = document.replace(include, _read_template(f"report/{filename}"))
    return document


def _render_variables(
    template: str, context: Mapping[str, str], html_context: Mapping[str, str]
) -> str:
    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in html_context:
            return html_context[name]
        if name in context:
            return escape(context[name], quote=True)
        raise ValueError(f"Unknown report template field: {name}")

    return _PLACEHOLDER.sub(substitute, template)


def _display(value: object) -> str:
    if value is None or value == "":
        return "Ikke oppgitt"
    if isinstance(value, float):
        return format(Decimal(str(value)), "f").rstrip("0").rstrip(".").replace(".", ",")
    return str(value)


def _case_facts(report: ReportData) -> str:
    facts = (
        ("Pasientkode", report.sample.get("patientPseudonym")),
        ("Referansegenom", report.sample.get("referenceBuild")),
        ("Tumortype", report.sample.get("tumourType")),
        ("Prøvemateriale", report.sample.get("specimenType")),
        ("Sekvenseringskjøring", report.run.get("runId")),
    )
    return "".join(
        f"<div><dt>{label}</dt><dd>{escape(_display(value))}</dd></div>"
        for label, value in facts
    )


def _biomarker_cards(report: ReportData) -> str:
    if not report.biomarkers:
        return '<p class="empty-state">Ingen biomarkørverdier tilgjengelig i kildedata.</p>'
    cards = []
    for biomarker in report.biomarkers:
        value = _display(biomarker["value"])
        unit = str(biomarker.get("unit", ""))
        shown = f"{value} {unit}".strip()
        cards.append(
            '<article class="metric-card">'
            f'<h4>{escape(str(biomarker["label"]))}</h4>'
            f'<p class="metric-card__value">{escape(shown)}</p>'
            '</article>'
        )
    return "".join(cards)


def _annotation(variant: Mapping[str, Any], key: str) -> object:
    for annotation in variant["annotations"]:
        if annotation["key"] == key:
            return annotation["value"]
    return None


def _variant_rows(report: ReportData) -> str:
    if not report.variants:
        return '<tr><td colspan="7">Ingen varianter tilgjengelig i kildedata.</td></tr>'
    rows = []
    for variant in report.variants:
        gene = _display(variant.get("gene"))
        location = _display(variant.get("genomicLocation"))
        dna = _display(variant.get("dnaChange"))
        protein = _display(variant.get("proteinChange"))
        tier = _display(_annotation(variant, "tier"))
        frequency = variant.get("alleleFrequency")
        vaf = (
            _display(float(Decimal(str(frequency)) * 100)) + " %"
            if isinstance(frequency, (int, float))
            else "Ikke oppgitt"
        )
        cells = (gene, location, dna, protein, vaf, tier)
        search = " ".join(str(value) for value in cells).casefold()
        rows.append(
            '<tr data-occurrence-id="{}" data-search="{}" data-vaf="{}">{}</tr>'.format(
                escape(str(variant["occurrenceId"]), quote=True),
                escape(search, quote=True),
                escape(str(frequency) if frequency is not None else "", quote=True),
                "".join(f"<td>{escape(value)}</td>" for value in cells)
                + f'<td class="identifier">{escape(str(variant["occurrenceId"]))}</td>',
            )
        )
    return "".join(rows)


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
    html_context = {
        "case_facts": _case_facts(report),
        "biomarker_cards": _biomarker_cards(report),
        "variant_rows": _variant_rows(report),
    }
    context["variant_count"] = str(len(report.variants))
    return _render_variables(_assemble_template(), context, html_context)
