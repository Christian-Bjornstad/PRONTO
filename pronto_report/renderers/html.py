"""Modular HTML renderer for validated PRONTO report snapshots."""

from __future__ import annotations

import base64
import json
from hashlib import sha256
from html import escape
from pathlib import Path
import re
from decimal import Decimal
from typing import Any, Mapping

from pronto_report.models import ReportData, ReviewState
from pronto_report.igv.locus import locus_for_variant
from pronto_report.migration import migrate_review_state_v1
from pronto_report.renderers.projection import project_reference_ui
from pronto_report.renderers.attribution import render_attribution, initials_dialog
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
        return "Not reported"
    if isinstance(value, float):
        rendered = format(Decimal(str(value)), "f")
        return (rendered.rstrip("0").rstrip(".") if "." in rendered else rendered).replace(".", ",")
    return str(value)


def _corrections(review: ReviewState | None) -> dict[str, Mapping[str, Any]]:
    return {str(item["path"]): item for item in review.value_corrections} if review else {}


def _correction_notice(correction: Mapping[str, Any] | None, unit: str = "") -> str:
    if not correction:
        return ""
    value = f'{_display(correction["correctedValue"])} {unit}'.strip()
    source = f'{_display(correction["originalValue"])} {unit}'.strip()
    return (
        '<details class="saved-correction">'
        '<summary>Corrected</summary>'
        f'<p>Current: {escape(value)}<br>Source: {escape(source)}'
        f'<br>Reason: {escape(str(correction["reason"]))}'
        f'<br>Recorded by {escape(str(correction["author"]))}'
        f' · <time datetime="{escape(str(correction["timestamp"]), quote=True)}">'
        f'{escape(str(correction["timestamp"]))}</time></p></details>'
    )


def _case_facts(ui: Mapping[str, Any], review: ReviewState | None, editable: bool) -> str:
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
    corrections = _corrections(review)
    for name, label in facts:
        fact = ui["facts"][name]
        original = _display(fact["value"])
        controls = ""
        correction = corrections.get(f"/sample/{name}")
        if editable and name in {"tumourType", "specimenType"}:
            path = f"/sample/{name}"
            field_value = "" if correction is None and fact["value"] is None else str(
                correction["correctedValue"] if correction else fact["value"]
            )
            source_value = "" if fact["value"] is None else str(fact["value"])
            controls = (
                f'<small class="patient-strip__source" data-source-value="{escape(original, quote=True)}">'
                f'Source: {escape(original)}</small>'
                '<div class="patient-strip__edit report-edit-controls" hidden>'
                f'<label for="{name}-edit">Proposed value</label>'
                f'<input id="{name}-edit" type="text" maxlength="512" '
                f'value="{escape(field_value, quote=True)}" '
                f'data-correction-path="{path}" data-original-value="{escape(source_value, quote=True)}">'
                f'<label for="{name}-correction-reason">Reason for correction</label>'
                f'<input id="{name}-correction-reason" type="text" maxlength="10000" '
                f'placeholder="Required before saving" {"required" if correction else "disabled"} value="{escape(str(correction["reason"]), quote=True) if correction else ""}">'
                '</div>'
            )
        cards.append(
            f'<div class="patient-strip__fact" data-fact="{name}" '
            f'data-availability="{fact["availability"]}">'
            f'<dt>{label}</dt><dd>{escape(original)}</dd>{_correction_notice(correction)}{controls}</div>'
        )
    return "".join(cards)


def _biomarker_cards(
    ui: Mapping[str, Any], report: ReportData, review: ReviewState | None, editable: bool
) -> str:
    cards = []
    corrections = _corrections(review)
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
        detail = f'Source value: {escape(str(raw))}' if raw is not None else "Not reported in source data"
        localapp = (
            '<p class="metric-card__detail" data-metric="localapp_tmb" '
            'data-availability="UNAVAILABLE">LocalApp TMB: Not reported</p>'
            if metric_id == "tmb" else ""
        )
        correction_path = next(
            (f"/biomarkers/{index}/value" for index, item in enumerate(report.biomarkers)
             if item["metricId"] == metric_id), None,
        )
        correction = corrections.get(correction_path) if correction_path else None
        correction_notice = _correction_notice(correction, unit)
        gauge = ""
        if metric_id == "tmb" and isinstance(biomarker["value"], (int, float)):
            original = escape(str(biomarker["value"]), quote=True)
            index = next(
                i for i, item in enumerate(report.biomarkers) if item["metricId"] == "tmb"
            )
            effective = correction["correctedValue"] if correction else biomarker["value"]
            gauge = (
                '<div class="tmb-gauge">'
                f'<label for="tmb-gauge">TMB (mut/Mb)</label>'
                '<div class="tmb-gauge__scale">'
                '<span class="tmb-gauge__tick tmb-gauge__tick--5"></span>'
                '<span class="tmb-gauge__tick tmb-gauge__tick--20"></span>'
                f'<input id="tmb-gauge" type="range" class="tmb-gauge__cursor" min="0" max="30" step="0.1" '
                f'value="{escape(str(effective), quote=True)}" data-original-value="{original}" '
                f'data-correction-path="/biomarkers/{index}/value" {"" if editable else "disabled"}>'
                '</div>'
                '<div class="tmb-gauge__legend"><span>0</span><span>5</span><span>10</span>'
                '<span>15</span><span>20</span><span>25</span><span>30 mut/Mb</span></div>'
                + ('<div class="tmb-gauge__details report-edit-controls" hidden>'
                '<label for="tmb-edit-value">TMB value</label>'
                f'<input id="tmb-edit-value" type="number" min="0" step="0.1" value="{escape(str(correction["correctedValue"]), quote=True) if correction else original}">'
                '<label for="tmb-correction-reason">Reason for correction</label>'
                '<input id="tmb-correction-reason" type="text" maxlength="10000" '
                f'placeholder="Required before saving" {"required" if correction else "disabled"} value="{escape(str(correction["reason"]), quote=True) if correction else ""}">'
                '<p id="tmb-correction-status" hidden>Proposed correction; the source value remains unchanged.</p>'
                '</div>' if editable else '')
                + '</div>'
            )
        elif metric_id == "msi" and editable and isinstance(biomarker["value"], (int, float)):
            original = escape(str(biomarker["value"]), quote=True)
            index = next(
                i for i, item in enumerate(report.biomarkers) if item["metricId"] == "msi"
            )
            gauge = (
                '<div class="metric-edit report-edit-controls" hidden>'
                '<label for="msi-edit-value">Proposed MSI value (%)</label>'
                f'<input id="msi-edit-value" type="number" min="0" max="100" step="0.01" '
                f'value="{escape(str(correction["correctedValue"]), quote=True) if correction else original}" data-original-value="{original}" '
                f'data-metric-correction-path="/biomarkers/{index}/value">'
                '<label for="msi-correction-reason">Reason for correction</label>'
                '<input id="msi-correction-reason" type="text" maxlength="10000" '
                f'placeholder="Required before saving" {"required" if correction else "disabled"} value="{escape(str(correction["reason"]), quote=True) if correction else ""}">'
                '</div>'
            )
        cards.append(
            f'<article class="metric-card" data-metric="{metric_id}" '
            f'data-availability="{biomarker["availability"]}">'
            f'<h3>{escape(label)}</h3>'
            f'<p class="metric-card__value">{escape(shown)}</p>'
            f'<p class="metric-card__detail">{detail}</p>'
            f'{correction_notice}'
            f'{localapp}'
            f'{gauge}'
            '</article>'
        )
    included = sum(item["reportingDecision"] == "INCLUDE" for item in review.variant_reviews) if review else 0
    excluded = sum(item["reportingDecision"] == "EXCLUDE" for item in review.variant_reviews) if review else 0
    decision_value = str(included) if review else "Unreviewed"
    decision_detail = (
        f"{excluded} excluded · revision {review.revision}"
        if review else "No review loaded"
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
            '<p class="metric-card__value">Not reported</p>'
            '<p class="metric-card__detail">No validated structured value</p>'
            '</article>'
        )
    empty = '<p class="empty-state">No biomarker values in source data.</p>' if not report.biomarkers else ""
    return "".join(cards) + empty


def _annotation(variant: Mapping[str, Any], key: str) -> object:
    for annotation in variant["annotations"]:
        if annotation["key"] == key:
            return annotation["value"]
    return None


def _af(value: object) -> str:
    return format(Decimal(str(value)), '.3f').replace('.', ',') if isinstance(value, (int, float)) else 'Not reported'


def _qc_review(review: ReviewState | None, snapshot: bool) -> str:
    if review is None:
        return '<p>No QC assessment saved.</p>'
    assessment = review.run_qc_assessment
    labels = {'NOT_REVIEWED': 'Not reviewed', 'PASS': 'Pass', 'FAIL': 'Fail', 'CONDITIONAL': 'Conditional'}
    comment = escape(str(assessment.get('comment', '')))
    if snapshot:
        return f'<p>{labels[assessment["status"]]}</p><p>{comment}</p>'
    disabled = ' disabled' if review.status == 'FINAL' else ''
    options = ''.join(f'<option value="{key}"' + (' selected' if key == assessment['status'] else '') + f'>{label}</option>' for key, label in labels.items())
    return (f'<label for="qc-review-status">Overall QC assessment</label><select id="qc-review-status"{disabled}>{options}</select>'
            f'<label for="qc-review-comment">QC comment</label><textarea id="qc-review-comment" maxlength="10000" rows="4"{disabled}>{comment}</textarea>')


def _key_variant_rows(report: ReportData, review: ReviewState | None) -> str:
    rows = []
    reviews = {item["variantId"]: item for item in review.variant_reviews} if review else {}
    decisions = {"UNREVIEWED": "Unreviewed", "INCLUDE": "Include", "EXCLUDE": "Exclude"}
    igv_labels = {"NOT_REVIEWED": "Not reviewed", "SUPPORTS": "Supports", "DOES_NOT_SUPPORT": "Does not support", "INCONCLUSIVE": "Inconclusive", "NOT_APPLICABLE": "Not applicable"}
    for variant in report.variants:
        protein = variant.get("proteinChange")
        if not protein:
            continue
        frequency = variant.get("alleleFrequency")
        vaf = _af(frequency)
        cells = (_display(variant.get("gene")), str(protein),
                 _display(_annotation(variant, "codingStatus")), vaf,
                 _display(_annotation(variant, "depthTumourDna")))
        activity = reviews.get(variant["variantId"], {})
        decision = str(activity.get("reportingDecision", "UNREVIEWED"))
        igv = str(activity.get("igvAssessment", "NOT_REVIEWED"))
        rows.append(
            '<tr class="key-variant-row" data-occurrence-id="{}" data-variant-id="{}">{}'
            '<td><span class="review-status" data-review-summary="igv">{}</span></td>'
            '<td><span class="review-status" data-review-summary="decision" data-status="{}">{}</span></td></tr>'.format(
                escape(str(variant["occurrenceId"]), quote=True),
                escape(str(variant["variantId"]), quote=True),
                "".join(f"<td>{escape(value)}</td>" for value in cells),
                escape(igv_labels[igv]), escape(decision, quote=True), escape(decisions[decision]),
            )
        )
    return "".join(rows) if rows else '<tr><td colspan="7">No variants with a reported protein change.</td></tr>'


def _review_select(
    variant_id: str, occurrence_id: str, field: str, selected: str, final: bool
) -> str:
    labels = {
        "reportingDecision": (
            "Reporting decision",
            (("UNREVIEWED", "Unreviewed"), ("INCLUDE", "Include"), ("EXCLUDE", "Exclude")),
        ),
        "clinicalClassification": (
            "Clinical classification",
            (("UNCLASSIFIED", "Unclassified"), ("PATHOGENIC", "Pathogenic"),
             ("UNCERTAIN", "Uncertain"), ("OTHER", "Other")),
        ),
        "igvAssessment": (
            "IGV assessment",
            (("NOT_REVIEWED", "Not reviewed"), ("SUPPORTS", "Supports"),
             ("DOES_NOT_SUPPORT", "Does not support"), ("INCONCLUSIVE", "Inconclusive"),
             ("NOT_APPLICABLE", "Not applicable")),
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


def _variant_rows(
    report: ReportData, review: ReviewState | None, snapshot: bool = False, web_igv: bool = False,
) -> str:
    if not report.variants:
        span = 8 + (2 if review is not None else 0) + int(web_igv)
        return f'<tr><td colspan="{span}">No variants in source data.</td></tr>'
    rows = []
    reviews = {item["variantId"]: item for item in review.variant_reviews} if review else {}
    for variant in report.variants:
        gene = _display(variant.get("gene"))
        location = _display(variant.get("genomicLocation"))
        dna = _display(variant.get("dnaChange"))
        protein = _display(variant.get("proteinChange"))
        tier = _display(_annotation(variant, "tier"))
        frequency = variant.get("alleleFrequency")
        vaf = _af(frequency)
        coding = _display(_annotation(variant, "codingStatus"))
        search = " ".join(str(value) for value in (gene, location, dna, protein, coding, vaf, tier)).casefold()
        igv_cell = ""
        if web_igv:
            variant_id = escape(str(variant["variantId"]), quote=True)
            locus = locus_for_variant(variant, str(report.sample["referenceBuild"]))
            if locus is None:
                igv_cell = (
                    '<td><span class="igv-unavailable">'
                    'IGV unavailable: unknown or mismatched reference genome, '
                    'or missing position</span></td>'
                )
            else:
                igv_cell = (
                    '<td><button type="button" data-igv-locus="{}" data-variant-id="{}">'
                    'View in IGV</button></td>'
                ).format(escape(locus, quote=True), variant_id)
        review_cells = ""
        review_details = ""
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
                    "reportingDecision": {"UNREVIEWED": "Unreviewed", "INCLUDE": "Include", "EXCLUDE": "Exclude"},
                    "clinicalClassification": {"UNCLASSIFIED": "Unclassified", "PATHOGENIC": "Pathogenic", "UNCERTAIN": "Uncertain", "OTHER": "Other"},
                    "igvAssessment": {"NOT_REVIEWED": "Not reviewed", "SUPPORTS": "Supports", "DOES_NOT_SUPPORT": "Does not support", "INCONCLUSIVE": "Inconclusive", "NOT_APPLICABLE": "Not applicable"},
                }
                review_cells = "".join(
                    f"<td>{escape(labels[field][value])}</td>"
                    for field, value in (("reportingDecision", decision), ("clinicalClassification", classification))
                )
                review_details = (
                    '<dt>IGV QC</dt><dd>' + escape(labels['igvAssessment'][igv]) + '</dd>'
                    '<dt>Review comment</dt><dd class="review-comment-readonly">'
                    + (escape(comment) if comment else '—') + '</dd>'
                )
            else:
                disabled = " disabled" if review.status == "FINAL" else ""
                report_buttons = ''.join(
                    '<button type="button" class="review-quick-choice" data-quick-field="reportingDecision" '
                    'data-quick-value="{}" {}aria-label="{} for {}" aria-pressed="{}"{}>{}</button>'.format(
                        value,
                        f'data-include-variant="{escape(variant_id, quote=True)}" ' if value == "INCLUDE" else "",
                        label, escape(occurrence_id, quote=True),
                        str(decision == value).lower(), disabled, short,
                    )
                    for value, label, short in (
                        ("INCLUDE", "Include in report", "Inc"),
                        ("EXCLUDE", "Exclude from report", "Exc"),
                    )
                )
                class_buttons = ''.join(
                    '<button type="button" class="review-quick-choice" data-quick-field="clinicalClassification" '
                    'data-quick-value="{}" aria-label="{} for {}" aria-pressed="{}"{}>{}</button>'.format(
                        value, label, escape(occurrence_id, quote=True),
                        str(classification == value).lower(), disabled, short,
                    )
                    for value, label, short in (
                        ("PATHOGENIC", "Pathogenic", "Path"),
                        ("UNCERTAIN", "Uncertain", "Uns"),
                    )
                )
                review_cells = (
                    '<td><div class="review-quick-group" role="group" aria-label="Report choice">' + report_buttons + '</div></td>'
                    + '<td><div class="review-quick-group" role="group" aria-label="Classification choice">' + class_buttons + '</div></td>'
                )
                review_details = (
                    '<dt>Report choice</dt><dd>' + _review_select(variant_id, occurrence_id, "reportingDecision", decision, review.status == "FINAL") + '</dd>'
                    + '<dt>Clinical class</dt><dd>' + _review_select(variant_id, occurrence_id, "clinicalClassification", classification, review.status == "FINAL") + '</dd>'
                    + '<dt>IGV QC</dt><dd>' + _review_select(variant_id, occurrence_id, "igvAssessment", igv, review.status == "FINAL") + '</dd>'
                    + '<dt>Review comment</dt><dd><textarea aria-label="Review comment for {}" data-variant-id="{}" '
                      'data-review-field="comment" maxlength="10000" rows="2"{}>{}</textarea></dd>'.format(
                          escape(occurrence_id, quote=True), escape(variant_id, quote=True),
                          disabled, escape(comment),
                      )
                )
        details = (
            '<td class="variant-detail-cell"><details><summary>Details</summary><dl>'
            + '<dt>Genomic location</dt><dd>' + escape(location) + '</dd>'
            + '<dt>DNA change</dt><dd>' + escape(dna) + '</dd>'
            + '<dt>Occurrence ID</dt><dd class="identifier">' + escape(str(variant['occurrenceId'])) + '</dd>'
            + '<dt>Variant-ID</dt><dd class="identifier">' + escape(str(variant['variantId'])) + '</dd>'
            + '<dt>Source tier</dt><dd>' + escape(tier) + '</dd>'
            + ''.join('<dt>' + escape(str(item['key'])) + '</dt><dd>' + escape(_display(item.get('value'))) + '</dd>' for item in variant.get('annotations', ()))
            + review_details + '</dl></details></td>'
        )
        rows.append(
            '<tr data-occurrence-id="{}" data-search="{}" data-vaf="{}">{}{}{}</tr>'.format(
                escape(str(variant["occurrenceId"]), quote=True),
                escape(search, quote=True),
                escape(str(frequency) if frequency is not None else "", quote=True),
                "".join(f"<td>{escape(value)}</td>" for value in (gene, protein, coding, vaf))
                + '<td>' + escape(_display(_annotation(variant, 'depthTumourDna'))) + '</td>'
                + '<td>Not received</td><td>Not cross-checked</td>'
                + igv_cell,
                review_cells,
                details,
            )
        )
    return "".join(rows)


def _plot_figure(kind: str, index: int, total: int, media_type: str, payload: bytes, description: str, panel: str | None = None) -> str:
    if media_type not in {"image/png", "image/jpeg"}:
        raise ValueError("Unsupported report plot image type")
    label = f"CNV {panel}" if kind == "cnv" and panel else f"CNV page {index} of {total}" if kind == "cnv" else f"QC plot {index} of {total}"
    data_uri = f"data:{media_type};base64,{base64.b64encode(payload).decode('ascii')}"
    hidden = " hidden" if kind == "cnv" and index != 1 and panel is None else ""
    return (
        f'<figure class="plot-figure" id="{kind}-{index}"{hidden}>'
        f'<img src="{data_uri}" alt="{escape(label)}. {escape(description)}">'
        f'<figcaption><strong>{escape(label)}</strong> · {escape(description)}</figcaption>'
        f'<button type="button" data-enlarge="{kind}-{index}">Enlarge plot</button>'
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
        label = "CNV plot" if kind == "cnv" else "QC plot"
        return f'<p class="empty-state">{label} is not available for this report.</p>'
    # Verified against the nine raster pages of the approved OUS CNV overview PDF.
    panels = ("A1", "A2", "B2", "B3", "C1", "C2", "C3", "C4", "C6") if (
        kind == "cnv" and len(images) == 9 and len(attachments) == 1
        and str(attachments[0]["name"]).endswith("_CNV_overview_plots.pdf")
    ) else ()
    figure_items = [
        _plot_figure(kind, index, len(images), media_type, payload, str(item.get("description", "")),
                     panels[index - 1] if panels else None)
        for index, (item, media_type, payload) in enumerate(images, start=1)
    ]
    if kind == "cnv":
        if panels:
            group_slices = ((0, 2), (2, 4), (4, 6), (6, 8), (8, 9))
            group_names = ("A1 / A2", "B2 / B3", "C1 / C2", "C3 / C4", "C6")
            buttons = "".join(
                f'<button type="button" data-plot-select="cnv-group-{index}" aria-pressed="{str(index == 1).lower()}">{name}</button>'
                for index, name in enumerate(group_names, start=1)
            )
            groups = "".join(
                f'<div class="plot-group" id="cnv-group-{index}"{" hidden" if index != 1 else ""}>'
                + "".join(figure_items[start:end]) + "</div>"
                for index, (start, end) in enumerate(group_slices, start=1)
            )
            return f'<div class="plot-switcher" role="group" aria-label="Select CNV plot group">{buttons}</div>{groups}'
        buttons = "".join(
            f'<button type="button" data-plot-select="cnv-{index}" aria-pressed="{str(index == 1).lower()}">{panels[index - 1] if panels else f"Page {index}"}</button>'
            for index in range(1, len(images) + 1)
        )
        return f'<div class="plot-switcher" role="group" aria-label="Select CNV plot">{buttons}</div>{"".join(figure_items)}'
    return "".join(figure_items)


def _qc_metrics(report: ReportData) -> str:
    if not report.qc_metrics:
        return '<p class="empty-state">No structured QC metrics in source data.</p>'
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
            + (f'<p>Threshold: {escape(thresholds)}</p>' if thresholds else "")
            + '</article>'
        )
    return "".join(cards)


def _tumour_content(report: ReportData, review: ReviewState | None, snapshot: bool = False) -> str:
    if review is None:
        return '<p class="empty-state">No review loaded.</p>'
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
        classification = {
            'UNCLASSIFIED': 'Unclassified', 'PATHOGENIC': 'Pathogenic',
            'UNCERTAIN': 'Uncertain', 'OTHER': 'Other',
        }[activity['clinicalClassification']]
        comment = str(activity.get('comment', '')).strip()
        findings.append(
            '<li><strong>{}</strong> · {} · {} · Classification: {}{}</li>'.format(
                escape(_display(variant.get("gene"))),
                escape(_display(variant.get("genomicLocation"))),
                escape(_display(variant.get("dnaChange"))),
                escape(classification),
                ' · Comment: ' + escape(comment) if comment else '',
            )
        )
    finding_html = (
        f'<ul class="board-findings" id="board-findings"{" hidden" if not findings else ""}>'
        f'{"".join(findings)}</ul>'
        '<p class="empty-state" id="board-empty"'
        f'{" hidden" if findings else ""}>No findings selected for the report.</p>'
    )
    signoff = (
        (f'Finalized by {escape(review.finalization_attribution["declaredInitials"])} {escape(review.finalized_at or "")}'
         if review.finalization_attribution else f'Signed by {escape(review.finalized_by or "")} {escape(review.finalized_at or "")}')
        if review.status == "FINAL" else "Not signed"
    )
    notes = review.notes or {}
    note_fields = (
        ("summary", "Interpretation summary", "note-summary"),
        ("biomarkerContext", "Biomarkers and therapeutic context", "note-biomarker-context"),
        ("additional", "Additional comments", "note-additional"),
    )
    disabled = " disabled" if review.status == "FINAL" else ""
    note_cards = "".join(
        '<div class="board-note-card">'
        + (f'<h4>{escape(label)}</h4><p class="board-note-readonly">{escape(str(notes.get(key, ""))) or "Not reported"}</p>'
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
        '<div class="board-legacy-note"><h3>Imported legacy note</h3>'
        f'<p>{escape(legacy)}</p></div>' if legacy else ""
    )
    saved_by = (
        f'{escape(review.last_saved_attribution["declaredInitials"])}'
        if review.last_saved_attribution else 'initials not recorded'
    )
    return (
        f'<h3>Findings for discussion</h3>{finding_html}'
        f'<div class="board-note-grid">{note_cards}'
        f'<div class="board-signoff"><h3>Sign-off</h3>'
        f'<p id="board-saved-attribution">Last saved by: {saved_by}</p>'
        f'<p id="board-saved-revision">Saved revision: {review.revision}</p>'
        f'<p>Sign-off status: {signoff}</p>'
        + '<button id="print-mdt-btn" type="button">Print MDT report</button>'
        + f'</div></div>{legacy_note}'
        + ('<p class="board-warning">Draft — not signed.</p>'
           if review.status != "FINAL" else "")
    )


def _inline_assets(
    web_igv: bool = False, *, allow_same_origin_requests: bool = False
) -> tuple[str, str, str]:
    stylesheet = (_STATIC_ROOT / "report.css").read_text(encoding="utf-8")
    script = (_STATIC_ROOT / "report-attribution.js").read_text(encoding="utf-8") + '\n' + (_STATIC_ROOT / "report.js").read_text(encoding="utf-8")
    if "</style" in stylesheet.casefold() or "</script" in script.casefold():
        raise ValueError("Unsafe static report asset")
    style_hash = base64.b64encode(sha256(stylesheet.encode("utf-8")).digest()).decode("ascii")
    script_hash = base64.b64encode(sha256(script.encode("utf-8")).digest()).decode("ascii")
    if web_igv:
        # igv.js injects style rules at runtime; keep this exception web-only.
        policy = (
            "default-src 'none'; connect-src 'self'; img-src 'self' data: blob:; "
            "font-src 'self' data:; worker-src blob:; style-src 'self' 'unsafe-inline'; "
            f"script-src 'self' 'wasm-unsafe-eval' 'sha256-{script_hash}'; "
            "base-uri 'none'; form-action 'none'; object-src 'none'"
        )
    else:
        policy = (
            "default-src 'none'; img-src data:; "
            f"style-src 'sha256-{style_hash}'; script-src 'sha256-{script_hash}'; "
            + ("connect-src 'self'; " if allow_same_origin_requests else "")
            + "base-uri 'none'; form-action 'none'; object-src 'none'"
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
        '<details class="report-provenance"><summary>Source and provenance</summary>'
        f'<p>Schema {escape(report.schema_version)} · '
        f'{escape(str(generator["name"]))} {escape(str(generator["version"]))} · '
        f'Generated {escape(str(details["generatedAt"]))}</p>'
        f'<ul>{sources}</ul></details>'
    )


def render_html(
    report: ReportData,
    review: ReviewState | None = None,
    *,
    plot_images: Mapping[str, tuple[tuple[str, bytes], ...]] | None = None,
    inline_assets: bool = False,
    snapshot: bool = False,
    save_url: str | None = None,
    finalize_url: str | None = None,
    csrf_token: str | None = None,
    require_initials: bool = False,
    print_url: str | None = None,
    actor_id: str | None = None,
    web_igv: bool = False,
    igv_save_enabled: bool = False,
    igv_sources: tuple[Mapping[str, str], ...] = (),
    igv_references: Mapping[str, Mapping[str, str]] | None = None,
    igv_registry_error: bool = False,
) -> str:
    """Render validated contracts as a development page or offline artifact."""
    if snapshot and not inline_assets:
        raise ValueError("snapshot requires inline_assets=True")
    if save_url and (snapshot or not csrf_token or not actor_id):
        raise ValueError("Live saving requires a non-snapshot report, CSRF token, and actor")
    if finalize_url and not save_url:
        raise ValueError("Finalization requires live saving")
    if (igv_sources or igv_references or igv_save_enabled) and not web_igv:
        raise ValueError("IGV configuration requires web_igv=True")
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
    status_label = "Final" if status == "FINAL" else "Draft"
    finalizer_label = (
        str(review.finalization_attribution['declaredInitials'])
        if review and review.finalization_attribution else str(review.finalized_by or '') if review else ''
    )
    csp_meta, stylesheet_tag, script_tag = (
        _inline_assets(web_igv, allow_same_origin_requests=save_url is not None or print_url is not None)
        if inline_assets else
        ("", '<link rel="stylesheet" href="/static/report.css">',
         '<script src="/static/report-attribution.js" defer></script><script src="/static/report.js" defer></script>')
    )
    if web_igv:
        igv_scripts = '<script type="module" src="/static/report-igv.js"></script>'
    else:
        igv_scripts = ""
    def safe_path(value: str) -> bool:
        return (isinstance(value, str) and value.startswith("/") and not value.startswith("//")
                and "\\" not in value and ".." not in value.split("/")
                and not any(ord(character) < 32 for character in value))

    safe_sources = []
    if print_url and (not safe_path(print_url) or snapshot or not csrf_token):
        raise ValueError('Printing requires a live same-origin URL and CSRF token')
    for source in igv_sources:
        if set(source) != {"sourceId", "role", "format", "referenceBuild", "dataURL", "indexURL"}:
            raise ValueError("Invalid IGV source descriptor")
        if not all(isinstance(value, str) for value in source.values()):
            raise ValueError("Invalid IGV source value")
        if any(not safe_path(source[key]) for key in ("dataURL", "indexURL")):
            raise ValueError("IGV source URL must be same-origin")
        safe_sources.append(dict(source))
    safe_references = dict(igv_references or {})
    for build, reference in safe_references.items():
        if build not in {"GRCh37", "GRCh38"}:
            raise ValueError("Invalid IGV reference build")
        if set(reference) != {"fastaURL", "indexURL"}:
            raise ValueError("Invalid IGV reference")
        if any(not safe_path(value) for value in reference.values()):
            raise ValueError("IGV reference URL must be same-origin")
    def safe_json(value: object) -> str:
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    review_columns = (
        '<th scope="col" class="review-decision-heading">Report</th><th scope="col">Clinical class</th>'
        if review is not None else ""
    )
    variant_colgroup = ""
    if review is not None:
        column_names = ["gene", "protein", "coding", "af", "depth", "oncokb", "biomarker"]
        if web_igv:
            column_names.append("igv")
        column_names.extend(("report", "clinical", "details"))
        variant_colgroup = '<colgroup>' + ''.join(
            f'<col class="variant-col--{name}">' for name in column_names
        ) + '</colgroup>'
    if review is None:
        review_toolbar = '<p class="review-notice">No review loaded. Read-only view.</p>'
        review_filters = ""
        review_actions = ""
        review_script = ""
        finalization = ""
    elif snapshot:
        review_filters = ""
        review_actions = ""
        review_toolbar = f'<p class="review-notice">Read-only export · revision {review.revision}</p>'
        review_script = ""
        finalization = (
            f'Finalized by {escape(finalizer_label)} '
            f'<time datetime="{escape(review.finalized_at or "")}">{escape(review.finalized_at or "")}</time>'
            if status == "FINAL" else ""
        )
    else:
        review_filters = (
            '<div class="review-filters" role="group" aria-label="Filter by review">'
            '<button type="button" data-review-filter="all" aria-pressed="true">All <span>0</span></button>'
            '<button type="button" data-review-filter="INCLUDE" aria-pressed="false">Include <span>0</span></button>'
            '<button type="button" data-review-filter="EXCLUDE" aria-pressed="false">Exclude <span>0</span></button>'
            '<button type="button" data-review-filter="PATHOGENIC" aria-pressed="false">Pathogenic <span>0</span></button>'
            '<button type="button" data-review-filter="UNCERTAIN" aria-pressed="false">Uncertain <span>0</span></button>'
            '<button type="button" data-review-filter="UNREVIEWED" aria-pressed="false">Unreviewed <span>0</span></button>'
            '</div>'
            '<div class="review-progress">'
            '<progress id="review-progress-bar" value="0" max="1" aria-label="Variants reviewed"></progress>'
            '<p id="review-progress" role="status" aria-live="polite">0 variants reviewed</p>'
            '</div>'
        )
        review_actions = (
            '<div class="review-bulk-actions" role="group" aria-label="Bulk review">'
            '<button type="button" data-bulk-decision="INCLUDE">Include visible unreviewed</button>'
            '<button type="button" data-bulk-decision="EXCLUDE">Exclude visible unreviewed</button>'
            '</div>'
            if status == "DRAFT" else ""
        )
        review_toolbar = (
            '<button id="download-review" type="button">Download ReviewState</button>'
            '<p id="review-feedback" role="status" aria-live="polite">'
            + ("Final report is locked." if status == "FINAL" else
               "Changes are saved when you select Save." if save_url else
               "Download ReviewState to keep changes.")
            + "</p>"
        )
        payload = serialize_review_state(review).decode("utf-8").strip()
        payload = payload.replace("<", r"\u003c").replace(">", r"\u003e").replace("&", r"\u0026")
        review_script = f'<script type="application/json" id="review-state-data">{payload}</script>'
        finalization = (
            f'Finalized by {escape(finalizer_label)} '
            f'<time datetime="{escape(review.finalized_at or "")}">{escape(review.finalized_at or "")}</time>'
            if status == "FINAL" else ""
        )
    editable = review is not None and status == "DRAFT" and not snapshot
    live_save = editable and save_url is not None
    save_feedback = (
        '<div class="save-feedback" id="save-feedback" hidden>'
        '<p id="save-error" role="alert" hidden></p>'
        '<div id="save-recovery" hidden>'
        '<button id="export-local-draft" type="button">Download local changes</button>'
        '<button id="reload-latest" type="button">Load latest saved revision</button>'
        '</div></div>' if live_save else ""
    )
    save_button = (
        f'<button id="save-btn" type="button" data-save-url="{escape(save_url, quote=True)}" '
        f'data-csrf-token="{escape(csrf_token or "", quote=True)}" '
        f'data-actor-id="{escape(actor_id or "", quote=True)}" disabled>Save</button>'
        if live_save else
        '<button id="save-btn" type="button" disabled title="Saving is unavailable here">Save</button>'
    )
    finalize_button = (
        f'<button id="finalize-btn" type="button" data-finalize-url="{escape(finalize_url, quote=True)}" '
        '>Finalize</button>'
        if live_save and finalize_url else ""
    )
    topbar_actions = (
        '<span class="report-topbar__saved">Read-only export</span>' if snapshot else
        '<span class="report-topbar__saved" id="dirty-lbl" role="status" aria-live="polite">Local view only</span>'
        + ('<button id="edit-btn" type="button" aria-pressed="false">Edit mode: OFF</button>' if editable else
           '<button id="edit-btn" type="button" disabled title="Report is read-only">Edit mode: OFF</button>')
        + save_button
        + finalize_button
    )
    context = {
        "sample_id": str(report.sample["sampleId"]),
        "report_id": report.report_id,
        "status_code": status.lower(),
        "status_label": status_label,
    }
    registry_notice = (
        '<p id="igv-registry-error" role="alert">Registered IGV sources are unavailable. '
        'Contact an administrator or select local files.</p>'
        if igv_registry_error else ""
    )
    igv_save_controls = (
        '<div id="igv-save-controls">'
        '<label for="igv-role">File role</label>'
        '<select id="igv-role">'
        '<option value="TUMOUR_DNA">Tumor DNA</option><option value="NORMAL_DNA">Normal DNA</option>'
        '<option value="TUMOUR_RNA">Tumor RNA</option><option value="NORMAL_RNA">Normal RNA</option>'
        '</select>'
        '<button type="button" id="igv-save" disabled>Save files for later use</button>'
        '<p id="igv-saved-state" role="status" hidden>Saved for later use</p>'
        '<p id="igv-save-error" role="alert" hidden></p>'
        '<div id="igv-upload-progress" hidden><label for="igv-upload-meter">Saving complete file pair</label>'
        '<progress id="igv-upload-meter" value="0" max="100"></progress>'
        '<button type="button" id="igv-cancel-upload">Cancel upload</button></div>'
        '<dialog id="igv-save-confirm"><h4>Confirm save</h4>'
        '<p>The complete BAM/CRAM file and index will be saved for later use.</p>'
        '<p id="igv-save-summary"></p>'
        '<button type="button" id="igv-confirm-cancel">Cancel</button>'
        '<button type="button" id="igv-confirm-save">Confirm save</button></dialog>'
        '</div>'
    ) if igv_save_enabled else ""
    html_context = {
        'attribution_controls': (
            render_attribution(review, snapshot)
            + (('<div id="attribution-config" data-required="{}" data-print-url="{}" data-csrf-token="{}"></div>'.format(
                str(require_initials).lower(), escape(print_url or '', quote=True), escape(csrf_token or '', quote=True))
                + initials_dialog()) if not snapshot else '')
        ),
        "case_facts": _case_facts(ui, review, editable),
        "biomarker_cards": _biomarker_cards(ui, report, review, editable),
        "key_variant_rows": _key_variant_rows(report, review),
        "variant_rows": _variant_rows(report, review, snapshot, web_igv),
        "igv_column": '<th scope="col">IGV</th>' if web_igv else "",
        "igv_panel": (
            '<section id="igv-panel" aria-label="IGV viewer" hidden '
            f'data-reference-build="{escape(str(report.sample["referenceBuild"]), quote=True)}" '
            f'data-report-id="{escape(report.report_id, quote=True)}" '
            f'data-sample-id="{escape(str(report.sample["sampleId"]), quote=True)}">'
            '<div class="igv-panel__heading"><h3>IGV</h3><button type="button" id="igv-close">Close IGV</button></div>'
            '<p id="igv-status" role="status" aria-live="polite">Select a source.</p>'
            + registry_notice +
            '<label for="igv-source">Registered source</label><select id="igv-source"><option value="">Select source</option></select>'
            '<button type="button" id="igv-open-source">Open registered source</button>'
            '<fieldset><legend>Or select files for this session only</legend>'
            '<label for="igv-data">BAM/CRAM</label><input id="igv-data" name="igv-data" type="file" accept=".bam,.cram">'
            '<label for="igv-index">Index</label><input id="igv-index" name="igv-index" type="file" accept=".bai,.csi,.crai">'
            '<button type="button" id="igv-open-local">Open local files</button></fieldset>'
            '<p id="igv-local-state" hidden>Not saved · files are used only in this browser tab.</p>'
            + igv_save_controls +
            '<div id="igv-viewer"></div>'
            f'<script type="application/json" id="igv-sources">{safe_json(safe_sources)}</script>'
            f'<script type="application/json" id="igv-references">{safe_json(safe_references)}</script>'
            '</section>'
        ) if web_igv else "",
        "review_columns": review_columns,
        "variant_colgroup": variant_colgroup,
        "review_toolbar": review_toolbar,
        "review_filters": review_filters,
        "review_actions": review_actions,
        "topbar_actions": topbar_actions,
        "save_feedback": save_feedback,
        "revision_label": f"Revision {review.revision}" if snapshot and review else "",
        "review_script": review_script,
        "finalization": finalization,
        "cnv_content": _plot_content(report, plot_images, "cnv"),
        "qc_content": _plot_content(report, plot_images, "qc"),
        "qc_metrics": _qc_metrics(report),
        "qc_review": _qc_review(review, snapshot),
        "tumour_content": _tumour_content(report, review, snapshot),
        "provenance": _provenance(report),
        "csp_meta": csp_meta,
        "stylesheet_tag": stylesheet_tag,
        "script_tag": script_tag,
        "igv_scripts": igv_scripts,
    }
    context["variant_count"] = str(len(report.variants))
    context["selected_finding_count"] = str(len({
        item['variantId'] for item in review.variant_reviews
        if item['reportingDecision'] == 'INCLUDE'
    })) if review else '0'
    return _render_variables(_assemble_template(), context, html_context)
