"""Modular HTML renderer for validated PRONTO report snapshots."""

from __future__ import annotations

from html import escape
from pathlib import Path
import re
from decimal import Decimal
from typing import Any, Mapping

from pronto_report.models import ReportData, ReviewState
from pronto_report.serialization import serialize_review_state


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


def _review_select(
    variant_id: str, occurrence_id: str, field: str, selected: str, final: bool
) -> str:
    labels = {
        "reportingDecision": (
            "Rapporteringsbeslutning",
            (("UNREVIEWED", "Ikke vurdert"), ("INCLUDE", "Inkluder"), ("EXCLUDE", "Ekskluder")),
        ),
        "clinicalClassification": (
            "Klinisk klassifikasjon",
            (("UNCLASSIFIED", "Ikke klassifisert"), ("PATHOGENIC", "Patogen"),
             ("UNCERTAIN", "Usikker"), ("OTHER", "Annet")),
        ),
    }
    label, choices = labels[field]
    options = "".join(
        f'<option value="{value}"{" selected" if value == selected else ""}>{text}</option>'
        for value, text in choices
    )
    disabled = " disabled" if final else ""
    return (
        f'<select aria-label="{label} for {escape(occurrence_id)}" '
        f'data-variant-id="{escape(variant_id)}" data-review-field="{field}"{disabled}>'
        f"{options}</select>"
    )


def _variant_rows(report: ReportData, review: ReviewState | None) -> str:
    if not report.variants:
        span = 9 if review is not None else 7
        return f'<tr><td colspan="{span}">Ingen varianter tilgjengelig i kildedata.</td></tr>'
    rows = []
    reviews = {item["variantId"]: item for item in review.variant_reviews} if review else {}
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
        review_cells = ""
        if review is not None:
            variant_id = str(variant["variantId"])
            occurrence_id = str(variant["occurrenceId"])
            activity = reviews.get(variant_id, {})
            decision = str(activity.get("reportingDecision", "UNREVIEWED"))
            classification = str(activity.get("clinicalClassification", "UNCLASSIFIED"))
            review_cells = (
                "<td>" + _review_select(variant_id, occurrence_id, "reportingDecision", decision, review.status == "FINAL") + "</td>"
                + "<td>" + _review_select(variant_id, occurrence_id, "clinicalClassification", classification, review.status == "FINAL") + "</td>"
            )
        rows.append(
            '<tr data-occurrence-id="{}" data-search="{}" data-vaf="{}">{}{}</tr>'.format(
                escape(str(variant["occurrenceId"]), quote=True),
                escape(search, quote=True),
                escape(str(frequency) if frequency is not None else "", quote=True),
                "".join(f"<td>{escape(value)}</td>" for value in cells)
                + f'<td class="identifier">{escape(str(variant["occurrenceId"]))}</td>',
                review_cells,
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
    review_columns = (
        '<th scope="col">Rapporteringsbeslutning</th><th scope="col">Klinisk klassifikasjon</th>'
        if review is not None else ""
    )
    if review is None:
        review_toolbar = '<p class="review-notice">Ingen ReviewState er lastet inn. Gjennomgang er skrivebeskyttet.</p>'
        review_script = ""
        finalization = ""
    else:
        review_toolbar = (
            '<button id="download-review" type="button">Last ned ReviewState</button>'
            '<p id="review-feedback" role="status" aria-live="polite">'
            + ("Endelig rapport er låst." if status == "FINAL" else "Endringer lagres når ReviewState lastes ned.")
            + "</p>"
        )
        payload = serialize_review_state(review).decode("utf-8").strip()
        payload = payload.replace("<", r"\u003c").replace(">", r"\u003e").replace("&", r"\u0026")
        review_script = f'<script type="application/json" id="review-state-data">{payload}</script>'
        finalization = (
            f'Ferdigstilt av {escape(review.finalized_by or "")} '
            f'<time datetime="{escape(review.finalized_at or "")}">{escape(review.finalized_at or "")}</time>'
            if status == "FINAL" else ""
        )
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
        "variant_rows": _variant_rows(report, review),
        "review_columns": review_columns,
        "review_toolbar": review_toolbar,
        "review_script": review_script,
        "finalization": finalization,
    }
    context["variant_count"] = str(len(report.variants))
    return _render_variables(_assemble_template(), context, html_context)
