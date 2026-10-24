"""Source-complete CNV/RNA tables with manual review annotations."""
from html import escape

from .review_v3 import checkbox, shown
from .source_fields import cnv_display_fields


def cnv_row(table, row, activities, readonly, manual=False):
    identifier=row['findingId']; activity=activities.get(identifier,{})
    fields=row.get('manualFields') or dict(zip(table['headers'],row['values']))
    if table['kind']=='CNV': fields=cnv_display_fields(fields)
    decision=activity.get('reportingDecision','UNREVIEWED')
    disabled=' disabled' if readonly else ''
    options=''.join(f'<option value="{value}"{" selected" if value==decision else ""}>{value}</option>'
                    for value in ('UNREVIEWED','INCLUDE','EXCLUDE'))
    buttons=''.join(f'<button type="button" class="review-quick-choice" data-v4-edit data-source-action="{value}" aria-label="{label} {escape(identifier)}" aria-pressed="{str(value==decision).lower()}"{disabled}>{short}</button>'
                    for value,label,short in (('INCLUDE','Include','Inc'),('EXCLUDE','Exclude','Exc')))
    cells=f'<td><div class="review-quick-group">{buttons}</div><select hidden data-source-decision="{identifier}">{options}</select></td>'
    cells+='<td>'+checkbox('data-source-highlight',identifier,'Key relevant findings',activity.get('reportHighlight',False),readonly)+'</td>'
    if table['kind']=='CNV':
        change=activity.get('cnChange','UNREVIEWED')
        cells+='<td><div class="review-quick-group">'+''.join(f'<button type="button" class="review-quick-choice" data-v4-edit data-cn-change="{value}" aria-label="{label} {escape(identifier)}" aria-pressed="{str(change==value).lower()}"{disabled}>{label}</button>'
                    for value,label in (('GAIN','Gain'),('LOSS','Loss')))+'</div></td>'
    headers=ordered_headers(table)
    for header in headers:
        value=activity.get('cytoband','') if header=='Cytoband' else fields.get(header)
        if header=='Cytoband':
            cells+=f'<td><input data-v4-edit data-cn-field="cytoband" aria-label="Cytoband {escape(identifier)}" maxlength="100" value="{escape(str(value),quote=True)}"{disabled}></td>'
        elif manual and header in {'Gene_Symbol','Tumor_FC'}:
            cells+=f'<td><input data-v4-edit data-manual-field="{header}" aria-label="{header} {escape(identifier)}" maxlength="128" value="{escape(str(value) if value is not None else "",quote=True)}"{disabled}></td>'
        else: cells+='<td class="source-data">'+shown(value)+'</td>'
    cells+='<td class="source-data">'+('Source QC highlighted' if row.get('sourceApproved') else '')+'</td>'
    if manual: cells+=f'<td><button type="button" data-v4-edit data-remove-cnv{disabled}>Remove row</button></td>'
    else: cells+='<td></td>'
    search=' '.join(str(v) for v in fields.values() if v is not None).casefold()
    label=' · '.join(str(fields[k]) for k in ('Gene_Symbol','Gene_A','Gene_B','Event_ID','Tumor_FC') if fields.get(k) is not None)
    return f'<tr data-source-id="{identifier}" data-source-kind="{table["kind"]}" data-source-search="{escape(search,quote=True)}" data-source-label="{escape(label,quote=True)}" class="{"excluded-row" if decision=="EXCLUDE" else ""}"'+(' data-manual-cnv' if manual else '')+'>'+cells+'</tr>'


def ordered_headers(table):
    headers=list(table['headers'])
    if table['kind']=='CNV':
        headers=[h for h in headers if h not in {'Gene_Symbol','Chromosome','Cytoband','Tumor_FC'}]
        headers=['Gene_Symbol','Chromosome','Cytoband','Tumor_FC',*headers]
    return headers


def source_tables(report,review,kind,readonly):
    tables=[t for t in report.source_tables if t['kind']==kind]
    if not tables and kind=='CNV':
        tables=[{'tableId':'manual-cnv-table','kind':'CNV','headers':['Gene_Symbol','Chromosome','Tumor_FC'],'rows':[]}]
    activities={i['findingId']:i for i in review.finding_reviews}
    parts=[]
    for index,table in enumerate(tables):
        manual=list(review.manual_cnv_rows) if kind=='CNV' and index==0 else []
        def manual_row(item):
            fields={'Gene_Symbol':item['geneSymbol'],'Tumor_FC':item['tumorFc']}
            row={'findingId':item['findingId'],'values':[fields.get(h) for h in table['headers']],'manualFields':fields}
            return cnv_row(table,row,activities,readonly,True)
        rows=''.join(manual_row(item) for item in manual)
        rows+=''.join(cnv_row(table,row,activities,readonly) for row in table['rows'])
        identifier=table['tableId']
        headings=['Report review','Report highlight']+(['CN Gain / Loss'] if kind=='CNV' else [])+ordered_headers(table)+['Source QC highlight','']
        toolbar=f'<button type="button" data-expand-table="{identifier}">Expand table</button>'
        if kind=='CNV' and index==0:
            toolbar+=f'<button type="button" data-add-cnv="{identifier}" data-v4-edit{" disabled" if readonly else ""}>Add CNV row</button>'
            toolbar+=f'<template id="template-{identifier}">'+manual_row({'findingId':'manual-cnv-template','geneSymbol':'','tumorFc':None})+'</template>'
        parts.append(f'<section class="source-table-block" data-table-workspace="{identifier}"><div class="table-toolbar">{toolbar}<label>Search all source columns <input type="search" data-source-search-for="{identifier}"></label></div>'
            f'<div class="table-scroll" role="region" aria-label="Full {kind} source table" tabindex="0"><table class="full-source-table" id="{identifier}"><thead><tr>'
            +''.join('<th>'+shown(h)+'</th>' for h in headings)+'</tr></thead><tbody>'+rows+'</tbody></table></div></section>')
    return ''.join(parts) or '<p class="empty-state">No source table provided.</p>'
