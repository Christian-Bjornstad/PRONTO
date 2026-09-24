"""Modular HTML renderer for validated PRONTO report snapshots."""

from __future__ import annotations

import base64
from hashlib import sha256
from html import escape
from pathlib import Path
import re
from decimal import Decimal
from typing import Any, Mapping

from pronto_report.models import ReportData, ReviewState
from pronto_report.migration import migrate_review_state_v1
from pronto_report.renderers.projection import project_reference_ui
from pronto_report.serialization import serialize_review_state


_PACKAGE_ROOT = Path(__file__).parents[1]
_TEMPLATE_ROOT = _PACKAGE_ROOT / "templates"
_STATIC_ROOT = _PACKAGE_ROOT / "static"
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
        rendered = format(Decimal(str(value)), "f")
        return (rendered.rstrip("0").rstrip(".") if "." in rendered else rendered).replace(".", ",")
    return str(value)


def _case_facts(ui: Mapping[str, Any], editable: bool) -> str:
    facts = (
        ("sampleId", "Sample"),
        ("patientPseudonym", "Patient code"),
        ("referenceBuild", "Reference genome"),
        ("tumourType", "Tumour type"),
        ("specimenType", "Sample type"),
        ("tumourContent", "Tumour content"),
        ("runId", "Sequencing run"),
    )
    cards = []
    for name, label in facts:
        fact = ui["facts"][name]
        original = _display(fact["value"])
        controls = ""
        if editable and name in {"tumourType", "specimenType"}:
            path = f"/sample/{name}"
            field_value = "" if fact["value"] is None else str(fact["value"])
            controls = (
                f'<small class="patient-strip__source" data-source-value="{escape(original, quote=True)}">'
                f'Kilde: {escape(original)}</small>'
                '<div class="patient-strip__edit report-edit-controls" hidden>'
                f'<label for="{name}-edit">Foreslått verdi</label>'
                f'<input id="{name}-edit" type="text" maxlength="512" '
                f'value="{escape(field_value, quote=True)}" '
                f'data-correction-path="{path}" data-original-value="{escape(field_value, quote=True)}">'
                f'<label for="{name}-correction-reason">Begrunnelse for korreksjon</label>'
                f'<input id="{name}-correction-reason" type="text" maxlength="10000" '
                'placeholder="Påkrevd før lagring" disabled>'
                '</div>'
            )
        cards.append(
            f'<div class="patient-strip__fact" data-fact="{name}" '
            f'data-availability="{fact["availability"]}">'
            f'<dt>{label}</dt><dd>{escape(original)}</dd>{controls}</div>'
        )
    return "".join(cards)


def _biomarker_cards(
    ui: Mapping[str, Any], report: ReportData, review: ReviewState | None, editable: bool
) -> str:
    cards = []
    primary = (("tmb", "TMB"), ("msi", "MSI"))
    extra = (
        (key, str(item["label"])) for key, item in ui["biomarkers"].items()
        if key not in {"tmb", "msi", "localapp_tmb"}
    )
    for metric_id, label in (*primary, *extra):
        biomarker = ui["biomarkers"][metric_id]
        value = _display(biomarker["value"])
        unit = str(biomarker.get("unit", ""))
        shown = f"{value} {unit}".strip()
        source = biomarker.get("source") or {}
        raw = source.get("rawValue")
        detail = f'Kildeverdi: {escape(str(raw))}' if raw is not None else "Ikke oppgitt i kildedata"
        localapp = (
            '<p class="metric-card__detail" data-metric="localapp_tmb" '
            'data-availability="UNAVAILABLE">LocalApp TMB: Ikke oppgitt</p>'
            if metric_id == "tmb" else ""
        )
        gauge = ""
        if metric_id == "tmb" and editable and isinstance(biomarker["value"], (int, float)):
            original = escape(str(biomarker["value"]), quote=True)
            index = next(
                i for i, item in enumerate(report.biomarkers) if item["metricId"] == "tmb"
            )
            gauge = (
                '<div class="tmb-gauge report-edit-controls" hidden>'
                f'<label for="tmb-gauge">Juster TMB (mut/Mb)</label>'
                f'<input id="tmb-gauge" type="range" min="0" max="30" step="0.1" '
                f'value="{original}" data-original-value="{original}" '
                f'data-correction-path="/biomarkers/{index}/value">'
                '<div class="tmb-gauge__legend"><span>0</span><span>5</span>'
                '<span>20</span><span>30+</span></div>'
                '<label for="tmb-edit-value">TMB-verdi</label>'
                f'<input id="tmb-edit-value" type="number" min="0" step="0.1" value="{original}">'
                '<label for="tmb-correction-reason">Begrunnelse for korreksjon</label>'
                '<input id="tmb-correction-reason" type="text" maxlength="10000" '
                'placeholder="Påkrevd før lagring" disabled>'
                '<p id="tmb-correction-status" hidden>Foreslått korreksjon – kildetallet over er uendret.</p>'
                '</div>'
            )
        elif metric_id == "msi" and editable and isinstance(biomarker["value"], (int, float)):
            original = escape(str(biomarker["value"]), quote=True)
            index = next(
                i for i, item in enumerate(report.biomarkers) if item["metricId"] == "msi"
            )
            gauge = (
                '<div class="metric-edit report-edit-controls" hidden>'
                '<label for="msi-edit-value">Foreslått MSI-verdi (%)</label>'
                f'<input id="msi-edit-value" type="number" min="0" max="100" step="0.01" '
                f'value="{original}" data-original-value="{original}" '
                f'data-metric-correction-path="/biomarkers/{index}/value">'
                '<label for="msi-correction-reason">Begrunnelse for korreksjon</label>'
                '<input id="msi-correction-reason" type="text" maxlength="10000" '
                'placeholder="Påkrevd før lagring" disabled>'
                '</div>'
            )
        cards.append(
            f'<article class="metric-card" data-metric="{metric_id}" '
            f'data-availability="{biomarker["availability"]}">'
            f'<h3>{escape(label)}</h3>'
            f'<p class="metric-card__value">{escape(shown)}</p>'
            f'<p class="metric-card__detail">{detail}</p>'
            f'{localapp}'
            f'{gauge}'
            '</article>'
        )
    included = sum(item["reportingDecision"] == "INCLUDE" for item in review.variant_reviews) if review else 0
    excluded = sum(item["reportingDecision"] == "EXCLUDE" for item in review.variant_reviews) if review else 0
    decision_value = str(included) if review else "Ikke vurdert"
    decision_detail = (
        f"{excluded} ekskludert · fra gjennomgang revisjon {review.revision}"
        if review else "Ingen gjennomgang lastet"
    )
    cards.append(
        '<article class="metric-card" data-origin="REVIEW_STATE">'
        '<h3>Variants · include</h3>'
        f'<p class="metric-card__value" id="kpi-inc">{decision_value}</p>'
        f'<p class="metric-card__detail" id="kpi-exc">{decision_detail}</p>'
        '</article>'
    )
    for label in ("CNV / amplifications", "Fusions / splicing"):
        cards.append(
            '<article class="metric-card" data-availability="UNAVAILABLE">'
            f'<h3>{label}</h3>'
            '<p class="metric-card__value">Ikke oppgitt</p>'
            '<p class="metric-card__detail">Ingen strukturert, validert verdi</p>'
            '</article>'
        )
    empty = '<p class="empty-state">Ingen biomarkørverdier tilgjengelig i kildedata.</p>' if not report.biomarkers else ""
    return "".join(cards) + empty


def _annotation(variant: Mapping[str, Any], key: str) -> object:
    for annotation in variant["annotations"]:
        if annotation["key"] == key:
            return annotation["value"]
    return None


def _key_variant_rows(report: ReportData) -> str:
    rows = []
    for variant in report.variants:
        protein = variant.get("proteinChange")
        if not protein:
            continue
        frequency = variant.get("alleleFrequency")
        vaf = (
            _display(float(Decimal(str(frequency)) * 100)) + " %"
            if isinstance(frequency, (int, float))
            else "Ikke oppgitt"
        )
        cells = (_display(variant.get("gene")), str(protein), vaf)
        rows.append(
            '<tr class="key-variant-row" data-occurrence-id="{}">{}</tr>'.format(
                escape(str(variant["occurrenceId"]), quote=True),
                "".join(f"<td>{escape(value)}</td>" for value in cells),
            )
        )
    return "".join(rows) if rows else '<tr><td colspan="3">Ingen varianter med oppgitt proteinendring.</td></tr>'


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
        "igvAssessment": (
            "IGV-vurdering",
            (("NOT_REVIEWED", "Ikke vurdert"), ("SUPPORTS", "Støtter"),
             ("DOES_NOT_SUPPORT", "Støtter ikke"), ("INCONCLUSIVE", "Uavklart"),
             ("NOT_APPLICABLE", "Ikke relevant")),
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


def _variant_rows(report: ReportData, review: ReviewState | None, snapshot: bool = False) -> str:
    if not report.variants:
        span = 11 if review is not None else 7
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
            igv = str(activity.get("igvAssessment", "NOT_REVIEWED"))
            comment = str(activity.get("comment", ""))
            if snapshot:
                labels = {
                    "reportingDecision": {"UNREVIEWED": "Ikke vurdert", "INCLUDE": "Inkluder", "EXCLUDE": "Ekskluder"},
                    "clinicalClassification": {"UNCLASSIFIED": "Ikke klassifisert", "PATHOGENIC": "Patogen", "UNCERTAIN": "Usikker", "OTHER": "Annet"},
                    "igvAssessment": {"NOT_REVIEWED": "Ikke vurdert", "SUPPORTS": "Støtter", "DOES_NOT_SUPPORT": "Støtter ikke", "INCONCLUSIVE": "Uavklart", "NOT_APPLICABLE": "Ikke relevant"},
                }
                review_cells = "".join(
                    f"<td>{escape(labels[field][value])}</td>"
                    for field, value in (("reportingDecision", decision), ("clinicalClassification", classification), ("igvAssessment", igv))
                ) + f'<td class="review-comment-readonly">{escape(comment) if comment else "—"}</td>'
            else:
                disabled = " disabled" if review.status == "FINAL" else ""
                review_cells = (
                    "<td>" + _review_select(variant_id, occurrence_id, "reportingDecision", decision, review.status == "FINAL") + "</td>"
                    + "<td>" + _review_select(variant_id, occurrence_id, "clinicalClassification", classification, review.status == "FINAL") + "</td>"
                    + "<td>" + _review_select(variant_id, occurrence_id, "igvAssessment", igv, review.status == "FINAL") + "</td>"
                    + '<td><textarea aria-label="Vurderingskommentar for {}" data-variant-id="{}" '
                      'data-review-field="comment" maxlength="10000" rows="2"{}>{}</textarea></td>'.format(
                          escape(occurrence_id, quote=True), escape(variant_id, quote=True),
                          disabled, escape(comment),
                      )
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


def _plot_figure(kind: str, index: int, total: int, media_type: str, payload: bytes, description: str) -> str:
    if media_type not in {"image/png", "image/jpeg"}:
        raise ValueError("Unsupported report plot image type")
    label = f"CNV oversikt – side {index} av {total}" if kind == "cnv" else f"QC-plott {index} av {total}"
    data_uri = f"data:{media_type};base64,{base64.b64encode(payload).decode('ascii')}"
    hidden = " hidden" if kind == "cnv" and index != 1 else ""
    return (
        f'<figure class="plot-figure" id="{kind}-{index}"{hidden}>'
        f'<img src="{data_uri}" alt="{escape(label)}. {escape(description)}">'
        f'<figcaption><strong>{escape(label)}</strong> · {escape(description)}</figcaption>'
        f'<button type="button" data-enlarge="{kind}-{index}">Forstørr plott</button>'
        "</figure>"
    )


def _plot_content(
    report: ReportData,
    plot_images: Mapping[str, tuple[tuple[str, bytes], ...]],
    kind: str,
) -> str:
    attachments = [
        item for item in report.attachments
        if ("cnv" in str(item["name"]).casefold()) == (kind == "cnv")
        and (kind == "cnv" or "qc" in str(item["name"]).casefold())
    ]
    images = [
        (item, media_type, payload)
        for item in attachments
        for media_type, payload in plot_images.get(str(item["assetId"]), ())
    ]
    if not images:
        label = "CNV-plott" if kind == "cnv" else "QC-plott"
        return f'<p class="empty-state">{label} er ikke tilgjengelig i denne rapporten.</p>'
    figures = "".join(
        _plot_figure(kind, index, len(images), media_type, payload, str(item.get("description", "")))
        for index, (item, media_type, payload) in enumerate(images, start=1)
    )
    if kind == "cnv":
        buttons = "".join(
            f'<button type="button" data-plot-select="cnv-{index}" aria-pressed="{str(index == 1).lower()}">Side {index}</button>'
            for index in range(1, len(images) + 1)
        )
        return f'<div class="plot-switcher" role="group" aria-label="Velg CNV-side">{buttons}</div>{figures}'
    return figures


def _qc_metrics(report: ReportData) -> str:
    if not report.qc_metrics:
        return '<p class="empty-state">Ingen strukturerte QC-målinger tilgjengelig i kildedata.</p>'
    cards = []
    for metric in report.qc_metrics:
        unit = str(metric.get("unit", ""))
        value = f'{_display(metric["value"])} {unit}'.strip()
        status = str(metric.get("status", "NOT_AVAILABLE"))
        thresholds = ", ".join(
            str(item.get("label") or f'{item["operator"]} {_display(item["value"])}')
            for item in metric.get("thresholds", ())
        )
        cards.append(
            '<article class="metric-card">'
            f'<h3>{escape(str(metric["label"]))}</h3>'
            f'<p class="metric-card__value">{escape(value)}</p>'
            f'<p>Status: {escape(status)}</p>'
            + (f'<p>Grense: {escape(thresholds)}</p>' if thresholds else "")
            + '</article>'
        )
    return "".join(cards)


def _tumour_content(report: ReportData, review: ReviewState | None, snapshot: bool = False) -> str:
    if review is None:
        return '<p class="empty-state">Ingen ReviewState er lastet inn. Tumorboard-funn er ikke tilgjengelige.</p>'
    included = {
        item["variantId"]: item for item in review.variant_reviews
        if item["reportingDecision"] == "INCLUDE"
    }
    shown = set()
    findings = []
    for variant in report.variants:
        identifier = variant["variantId"]
        if identifier not in included or identifier in shown:
            continue
        shown.add(identifier)
        activity = included[identifier]
        findings.append(
            '<li><strong>{}</strong> · {} · {} · Klassifikasjon: {}</li>'.format(
                escape(_display(variant.get("gene"))),
                escape(_display(variant.get("genomicLocation"))),
                escape(_display(variant.get("dnaChange"))),
                escape(str(activity["clinicalClassification"])),
            )
        )
    finding_html = (
        f'<ul class="board-findings" id="board-findings"{" hidden" if not findings else ""}>'
        f'{"".join(findings)}</ul>'
        '<p class="empty-state" id="board-empty"'
        f'{" hidden" if findings else ""}>Ingen funn er markert for rapportering.</p>'
    )
    signoff = (
        f'Signert av {escape(review.finalized_by or "")} {escape(review.finalized_at or "")}'
        if review.status == "FINAL" else "Ikke signert"
    )
    notes = review.notes or {}
    note_fields = (
        ("summary", "Interpretation summary", "note-summary"),
        ("biomarkerContext", "Biomarkører og terapeutisk kontekst", "note-biomarker-context"),
        ("additional", "Tilleggskommentarer", "note-additional"),
    )
    disabled = " disabled" if review.status == "FINAL" else ""
    note_cards = "".join(
        '<div class="board-note-card">'
        + (f'<h4>{escape(label)}</h4><p class="board-note-readonly">{escape(str(notes.get(key, ""))) or "Ikke oppgitt"}</p>'
           if snapshot else
           f'<label for="{field_id}">{escape(label)}</label>'
           f'<textarea id="{field_id}" class="board-note" rows="5" maxlength="50000"'
           f'{disabled} data-review-note="{key}">{escape(str(notes.get(key, "")))}</textarea>'
           f'<p class="board-note-print" data-print-note="{key}">{escape(str(notes.get(key, "")))}</p>')
        + '</div>'
        for key, label, field_id in note_fields
    )
    legacy = str(notes.get("importedLegacyNote", ""))
    legacy_note = (
        '<div class="board-legacy-note"><h3>Importert eldre notat</h3>'
        f'<p>{escape(legacy)}</p></div>' if legacy else ""
    )
    reviewer = str(review.reviewer.get("displayName") or review.reviewer["reviewerId"])
    return (
        f'<h3>Funn til diskusjon</h3>{finding_html}'
        f'<div class="board-note-grid">{note_cards}</div>{legacy_note}'
        f'<div class="board-signoff"><h3>Signering</h3>'
        f'<p>Gjennomgås av: {escape(reviewer)}</p>'
        f'<p>Signeringsstatus: {signoff}</p>'
        + ('<p>Ferdigstilling krever lagret gjennomgang i databasen.</p>' if review.status != "FINAL" else "")
        + '</div>'
        + ('<p class="board-warning">Utkast / arbeidskopi – ikke signert. Dette er ikke en ferdigstilt rapport.</p>'
           if review.status != "FINAL" else "")
        + '<button id="print-mdt-btn" type="button">Generer MDT-utskrift</button>'
    )


def _inline_assets() -> tuple[str, str, str]:
    stylesheet = (_STATIC_ROOT / "report.css").read_text(encoding="utf-8")
    script = (_STATIC_ROOT / "report.js").read_text(encoding="utf-8")
    if "</style" in stylesheet.casefold() or "</script" in script.casefold():
        raise ValueError("Unsafe static report asset")
    style_hash = base64.b64encode(sha256(stylesheet.encode("utf-8")).digest()).decode("ascii")
    script_hash = base64.b64encode(sha256(script.encode("utf-8")).digest()).decode("ascii")
    policy = (
        "default-src 'none'; img-src data:; "
        f"style-src 'sha256-{style_hash}'; script-src 'sha256-{script_hash}'; "
        "base-uri 'none'; form-action 'none'; object-src 'none'"
    )
    return (
        f'<meta http-equiv="Content-Security-Policy" content="{escape(policy, quote=True)}">',
        f"<style>{stylesheet}</style>",
        f"<script>{script}</script>",
    )


def _provenance(report: ReportData) -> str:
    details = report.provenance
    generator = details["generator"]
    sources = "".join(
        f'<li>{escape(str(source["name"]))} · SHA-256 {escape(str(source["sha256"]))}</li>'
        for source in details["sourceFiles"]
    )
    return (
        '<details class="report-provenance"><summary>Kilde og proveniens</summary>'
        f'<p>Skjema {escape(report.schema_version)} · '
        f'{escape(str(generator["name"]))} {escape(str(generator["version"]))} · '
        f'Generert {escape(str(details["generatedAt"]))}</p>'
        f'<ul>{sources}</ul></details>'
    )


def render_html(
    report: ReportData,
    review: ReviewState | None = None,
    *,
    plot_images: Mapping[str, tuple[tuple[str, bytes], ...]] | None = None,
    inline_assets: bool = False,
    snapshot: bool = False,
) -> str:
    """Render validated contracts as a development page or offline artifact."""
    if snapshot and not inline_assets:
        raise ValueError("snapshot requires inline_assets=True")
    if review is not None and review.report_id != report.report_id:
        raise ValueError("Review state does not belong to this report")
    if review is not None and review.schema_version == "1.0":
        review = migrate_review_state_v1(review)
    ui = project_reference_ui(report, review)

    status = review.status if review is not None else "DRAFT"
    plot_images = plot_images or {}
    known_assets = {str(item["assetId"]) for item in report.attachments}
    if set(plot_images) - known_assets:
        raise ValueError("Plot image does not match a declared attachment")
    status_label = "Endelig" if status == "FINAL" else "Utkast"
    csp_meta, stylesheet_tag, script_tag = (
        _inline_assets() if inline_assets else
        ("", '<link rel="stylesheet" href="/pronto_report/static/report.css">',
         '<script src="/pronto_report/static/report.js" defer></script>')
    )
    review_columns = (
        '<th scope="col">Rapporteringsbeslutning</th><th scope="col">Klinisk klassifikasjon</th>'
        '<th scope="col">IGV-vurdering</th>'
        '<th scope="col">Vurderingskommentar</th>'
        if review is not None else ""
    )
    if review is None:
        review_toolbar = '<p class="review-notice">Ingen ReviewState er lastet inn. Gjennomgang er skrivebeskyttet.</p>'
        review_filters = ""
        review_actions = ""
        review_script = ""
        finalization = ""
    elif snapshot:
        review_filters = ""
        review_actions = ""
        review_toolbar = f'<p class="review-notice">Skrivebeskyttet eksport · revisjon {review.revision}</p>'
        review_script = ""
        finalization = (
            f'Ferdigstilt av {escape(review.finalized_by or "")} '
            f'<time datetime="{escape(review.finalized_at or "")}">{escape(review.finalized_at or "")}</time>'
            if status == "FINAL" else ""
        )
    else:
        review_filters = (
            '<div class="review-filters" role="group" aria-label="Filtrer etter vurdering">'
            '<button type="button" data-review-filter="all" aria-pressed="true">Alle <span>0</span></button>'
            '<button type="button" data-review-filter="INCLUDE" aria-pressed="false">Inkludert <span>0</span></button>'
            '<button type="button" data-review-filter="EXCLUDE" aria-pressed="false">Ekskludert <span>0</span></button>'
            '<button type="button" data-review-filter="PATHOGENIC" aria-pressed="false">Patogen <span>0</span></button>'
            '<button type="button" data-review-filter="UNCERTAIN" aria-pressed="false">Usikker <span>0</span></button>'
            '<button type="button" data-review-filter="UNREVIEWED" aria-pressed="false">Ikke vurdert <span>0</span></button>'
            '</div>'
            '<p class="review-count-note">Filtertall viser forekomster; fremdrift teller unike varianter.</p>'
            '<div class="review-progress">'
            '<progress id="review-progress-bar" value="0" max="1" aria-label="Andel varianter vurdert"></progress>'
            '<p id="review-progress" role="status" aria-live="polite">0 varianter vurdert</p>'
            '</div>'
        )
        review_actions = (
            '<div class="review-bulk-actions" role="group" aria-label="Massevurdering">'
            '<button type="button" data-bulk-decision="INCLUDE">Merk synlige, ikke vurderte som inkludert</button>'
            '<button type="button" data-bulk-decision="EXCLUDE">Merk synlige, ikke vurderte som ekskludert</button>'
            '</div>'
            if status == "DRAFT" else ""
        )
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
    editable = review is not None and status == "DRAFT" and not snapshot
    topbar_actions = (
        '<span class="report-topbar__saved">Skrivebeskyttet eksport</span>' if snapshot else
        '<span class="report-topbar__saved" id="dirty-lbl" role="status" aria-live="polite">Kun lokal visning</span>'
        + ('<button id="edit-btn" type="button" aria-pressed="false">Edit mode: OFF</button>' if editable else
           '<button id="edit-btn" type="button" disabled title="Rapporten er skrivebeskyttet">Edit mode: OFF</button>')
        + '<button id="save-btn" type="button" disabled title="Lagring i databasen kommer i neste steg">Lagre</button>'
        + '<button id="load-btn" type="button" disabled title="Import av gjennomgang er ikke aktivert">Laster</button>'
        + '<button id="reset-btn" type="button" disabled title="Tilbakestilling er ikke aktivert">Reset</button>'
    )
    context = {
        "sample_id": str(report.sample["sampleId"]),
        "report_id": report.report_id,
        "status_code": status.lower(),
        "status_label": status_label,
    }
    html_context = {
        "case_facts": _case_facts(ui, editable),
        "biomarker_cards": _biomarker_cards(ui, report, review, editable),
        "key_variant_rows": _key_variant_rows(report),
        "variant_rows": _variant_rows(report, review, snapshot),
        "review_columns": review_columns,
        "review_toolbar": review_toolbar,
        "review_filters": review_filters,
        "review_actions": review_actions,
        "topbar_actions": topbar_actions,
        "revision_label": f"Revisjon {review.revision}" if snapshot and review else "",
        "review_script": review_script,
        "finalization": finalization,
        "cnv_content": _plot_content(report, plot_images, "cnv"),
        "qc_content": _plot_content(report, plot_images, "qc"),
        "qc_metrics": _qc_metrics(report),
        "tumour_content": _tumour_content(report, review, snapshot),
        "provenance": _provenance(report),
        "csp_meta": csp_meta,
        "stylesheet_tag": stylesheet_tag,
        "script_tag": script_tag,
    }
    context["variant_count"] = str(len(report.variants))
    return _render_variables(_assemble_template(), context, html_context)
