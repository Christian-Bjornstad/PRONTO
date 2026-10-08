"""Offline, print-ready HTML for one saved report review revision."""

from __future__ import annotations

from decimal import Decimal
from html import escape
from typing import Any, Mapping

from pronto_report.models import ReportData, ReviewState


_CSS = """
:root{color-scheme:light;font-family:Arial,Helvetica,sans-serif;color:#17364a;background:#fff}
body{max-width:62rem;margin:0 auto;padding:2rem;line-height:1.45}
header{border-bottom:3px solid #0077ae;padding-bottom:1rem;margin-bottom:1.5rem}
h1{font-size:1.7rem;margin:0 0 .3rem}h2{font-size:1.2rem;margin:1.6rem 0 .5rem;color:#00517a}
.meta{display:flex;flex-wrap:wrap;gap:.35rem 1.5rem;color:#405d70;font-size:.88rem}
.facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.6rem}
.fact{border:1px solid #c7dce6;padding:.65rem}.fact dt{font-size:.75rem;color:#405d70}.fact dd{margin:.2rem 0 0;font-weight:700}
table{width:100%;border-collapse:collapse;font-size:.86rem}th,td{border-bottom:1px solid #c7dce6;padding:.45rem;text-align:left;vertical-align:top;overflow-wrap:anywhere}
th{background:#eaf4f8;color:#00517a}.note{white-space:pre-wrap;border-left:3px solid #b6dff5;padding:.45rem .7rem;margin:.3rem 0}
.muted{color:#526b79}.provenance{font-size:.8rem;color:#405d70;overflow-wrap:anywhere}
@media print{body{padding:0;max-width:none}h2{break-after:avoid}tr{break-inside:avoid}header{break-after:avoid}}
""".strip()


def _shown(value: object, *, unavailable: str = "Not available") -> str:
    if value is None or value == "":
        return unavailable
    if isinstance(value, float):
        rendered = format(Decimal(str(value)), "f")
        return (rendered.rstrip("0").rstrip(".") if "." in rendered else rendered).replace(".", ",")
    return str(value)


def _annotation(variant: Mapping[str, Any], key: str) -> object:
    return next((item["value"] for item in variant["annotations"] if item["key"] == key), None)


def _fact(label: str, value: object) -> str:
    return f'<div class="fact"><dt>{escape(label)}</dt><dd>{escape(_shown(value))}</dd></div>'


def render_summary_html(report: ReportData, review: ReviewState, *, export_initials: str) -> str:
    """Render only immutable facts and the exact saved human review snapshot."""
    if review.report_id != report.report_id or review.schema_version not in {'2.0','3.0'}:
        raise ValueError('A matching saved review is required')
    if not export_initials:
        raise ValueError("Export initials are required")
    if review.schema_version=='3.0':
        return _render_v3(report,review,export_initials)
    corrections = {str(item["path"]): item for item in review.value_corrections}
    def effective(path: str, source: object) -> object:
        correction = corrections.get(path)
        return correction["correctedValue"] if correction else source

    tmb = next((item for item in report.biomarkers if item["metricId"] == "tmb"), None)
    tmb_index = next((index for index, item in enumerate(report.biomarkers) if item["metricId"] == "tmb"), None)
    tmb_correction = corrections.get(f"/biomarkers/{tmb_index}/value") if tmb_index is not None else None
    tmb_value = effective(f"/biomarkers/{tmb_index}/value", tmb["value"]) if tmb else None
    tmb_label = f'{_shown(tmb_value)} mut/Mb' if tmb_value is not None else 'Not available'
    msi = next((item for item in report.biomarkers if item["metricId"] == "msi"), None)
    msi_index = next((index for index, item in enumerate(report.biomarkers) if item["metricId"] == "msi"), None)
    msi_value = effective(f"/biomarkers/{msi_index}/value", msi["value"]) if msi else None
    msi_label = f'{_shown(msi_value)} {msi.get("unit", "")}'.strip() if msi_value is not None else 'Not available'
    selected = {item["variantId"]: item for item in review.variant_reviews
                if item["reportingDecision"] == "INCLUDE"}
    rows = []
    seen = set()
    for variant in report.variants:
        identifier = str(variant["variantId"])
        if identifier not in selected or identifier in seen:
            continue
        seen.add(identifier)
        activity = selected[identifier]
        frequency = variant.get("alleleFrequency")
        af = format(Decimal(str(frequency)), ".3f").replace(".", ",") if isinstance(frequency, (float, int)) else "Not available"
        cells = (
            variant.get("gene"), variant.get("proteinChange"), _annotation(variant, "codingStatus"),
            af, _annotation(variant, "depthTumourDna"),
            "Not available", "Not cross-checked",
            activity["clinicalClassification"].replace("_", " ").title(), activity.get("comment", ""),
        )
        rows.append(f'<tr data-variant-id="{escape(identifier, quote=True)}">'
                    + "".join(f'<td>{escape(_shown(value))}</td>' for value in cells) + '</tr>')
    variant_table = (
        '<table><thead><tr><th>Gene</th><th>Protein</th><th>Coding</th><th>AF tumour (0–1)</th>'
        '<th>Tumour DNA depth</th><th>OncoKB</th><th>Biomarker list</th><th>Clinical class</th><th>Comment</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
        if rows else '<p class="muted">No variants selected for this report.</p>'
    )
    notes = review.notes or {}
    note_sections = "".join(
        f'<h3>{escape(label)}</h3><p class="note">{escape(_shown(notes.get(key)))}</p>'
        for key, label in (
            ("summary", "Interpretation summary"),
            ("biomarkerContext", "Biomarkers and therapeutic context"),
            ("additional", "Additional comments"),
        )
    )
    correction_rows = []
    for item in review.value_corrections:
        unit = ' mut/Mb' if item is tmb_correction else ''
        correction_rows.append(
            f'<li>{escape(str(item["path"]))}: {escape(_shown(item["originalValue"]))}{unit} → '
            f'{escape(_shown(item["correctedValue"]))}{unit}. Reason: {escape(str(item["reason"]))}. '
            f'Recorded by {escape(str(item["author"]))} · {escape(str(item["timestamp"]))}</li>'
        )
    correction_notes = ''.join(correction_rows)
    correction_section = f'<section class="provenance"><h2>Saved corrections</h2><ul>{correction_notes}</ul></section>' if correction_notes else ''
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>PRONTO report</title><style>' + _CSS + '</style></head><body>'
        '<header><h1>PRONTO report</h1><div class="meta">'
        f'<span>Report {escape(report.report_id)}</span><span>Revision {review.revision}</span>'
        f'<span>{escape(review.status.title())}</span><span>Prepared by {escape(export_initials)}</span>'
        '</div></header><main>'
        '<section><h2>Key findings</h2><dl class="facts">'
        + _fact('Sample', report.sample.get('sampleId'))
        + _fact('Patient code', report.sample.get('patientPseudonym'))
        + _fact('Reference genome', report.sample.get('referenceBuild'))
        + _fact('Tumour type', effective('/sample/tumourType', report.sample.get('tumourType')))
        + _fact('Sample type', effective('/sample/specimenType', report.sample.get('specimenType')))
        + _fact('TMB', tmb_label)
        + _fact('MSI', msi_label)
        + _fact('Selected variants', len(rows))
        + '</dl></section><section><h2>Selected variants</h2>' + variant_table + '</section>'
        + '<section><h2>Conclusion notes</h2>' + note_sections + '</section>'
        + correction_section + '</main></body></html>'
    )


def _render_v3(report,review,initials):
    from .report_pdf import project_report_export
    from .review_v3 import NOTE_FIELDS
    model=project_report_export(report,review)
    def table(headers,rows):
        if not rows: return '<p>No findings selected.</p>'
        return '<table><thead><tr>'+''.join(f'<th>{escape(h)}</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{escape(_shown(c))}</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table>'
    body='<section><h2>Key findings</h2><dl class="facts">'+''.join(_fact(key,value) for key,value in model['sample'].items())+'</dl></section>'
    body+='<h2>Mutational signatures</h2><dl class="facts">'+''.join(_fact(item['metricId'].upper(),f'{_shown(item["value"])} {item.get("unit", "")} · {item.get("displayRange", "[0-100+]" if item["metricId"]=="tmb" else "[0-100]")}') for item in model['measurements'] if item['metricId'] in {'tmb','msi','hrd'})+'</dl>'
    body+='<h2>Selected variants</h2>'+table(['Gene','Protein','Clinical class','Highlight'],[[i['gene'],i['protein'],i['review']['clinicalClassification'].title() if i['review']['clinicalClassification']!='VUS' else 'VUS',i['review']['reportHighlight']] for i in model['variants']])
    for key,title in [('cnv','Selected CNV'),('rna','Selected RNA')]:
        headers=list(dict.fromkeys(h for row in model[key] for h in row['fields']))
        body+=f'<h2>{title}</h2>'+table(headers,[[row['fields'].get(h) for h in headers] for row in model[key]])
    body+='<h2>Key relevant findings</h2><ul>'+''.join(f'<li>{escape(i["gene"])} {escape(i["protein"])} </li>' for i in model['variants'] if i['review']['reportHighlight'])+'</ul>'
    body+='<h2>Quality assessment</h2>'+''.join(_fact(key,value['status']) for key,value in {**model['qc'],'overall':model['overallQc']}.items())
    body+='<h2>Conclusion notes</h2>'+''.join(f'<h3>{escape(label)}</h3><p class="note">{escape(_shown(model["notes"].get(key)))}</p>' for key,label in [('summary','Interpretation summary'),('biomarkerContext','Therapeutic context'),('additional','Additional comments'),*NOTE_FIELDS])
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>PRONTO report</title><style>'+_CSS+'</style></head><body><header><h1>PRONTO report</h1><p>Revision '+str(review.revision)+' · '+review.status.title()+' · Prepared by '+escape(initials)+'</p></header><main>'+body+'</main></body></html>'
