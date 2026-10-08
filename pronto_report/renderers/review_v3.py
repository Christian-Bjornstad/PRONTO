"""Markup for source-complete review and linked manual section QC."""
import base64
from html import escape

NOTE_FIELDS = (
    ('history','History / Reason for testing'), ('variantDescription','Variant description'),
    ('clinicalEvidence','Clinical actionability context'), ('clinicalTrials','Clinical trial context'),
    ('followUp','Findings for potential follow-up'), ('references','References'),
    ('assayMethods','Assay / methods / limitations'), ('patientDetails','Patient and sample details'),
)
QC_LABELS = {'variants':'Small variants', 'cnv':'CNV', 'rna':'Fusions and splice',
             'signatures':'Mutational signatures', 'overall':'Overall QC'}
QC_OPTIONS = {'NOT_REVIEWED':'Not reviewed', 'PASS':'Green / Pass',
              'CONDITIONAL':'Orange / Conditional', 'FAIL':'Red / Fail'}


def shown(value):
    return escape('' if value is None else str(value))


def checkbox(attribute, identifier, label, checked=False, disabled=False):
    return (f'<label class="review-check"><input type="checkbox" {attribute}="{escape(identifier,quote=True)}" '
            f'aria-label="{escape(label,quote=True)}"{" checked" if checked else ""}'
            f'{" disabled" if disabled else ""}> {escape(label)}</label>')


def qc_control(review, section, *, readonly=False, suffix='section'):
    assessment = review.run_qc_assessment if section == 'overall' else review.section_qc[section]
    status = assessment['status']
    identifier=f'qc-{section}-{suffix}'
    options=''.join(f'<option value="{key}"{" selected" if key == status else ""}>{label}</option>'
                    for key,label in QC_OPTIONS.items())
    return (f'<div class="section-qc" data-qc-status="{status}"><label for="{identifier}">'
            f'{QC_LABELS[section]} QC</label><select id="{identifier}" data-section-qc="{section}"'
            f'{" disabled" if readonly else ""}>{options}</select></div>')


def source_table(table, review, *, readonly=False):
    variant = table['kind'] == 'VARIANTS'
    activities={i['variantId'] if variant else i['findingId']:i
                for i in (review.variant_reviews if variant else review.finding_reviews)}
    rows=[]
    for row in table['rows']:
        identifier=str(row['findingId']); activity=activities.get(identifier,{})
        decision=activity.get('reportingDecision','UNREVIEWED')
        choice=''.join(f'<option value="{value}"{" selected" if value == decision else ""}>{text}</option>'
                       for value,text in [('UNREVIEWED','Not reviewed'),('INCLUDE','Include'),('EXCLUDE','Exclude')])
        controls=(f'<td class="source-review-cell"><select data-source-decision="{identifier}" '
                  f'data-source-kind="{table["kind"]}" aria-label="Report choice for source row {row["record"]}"'
                  f'{" disabled" if readonly else ""}>{choice}</select></td><td>'
                  + checkbox('data-source-highlight',identifier,'Key relevant findings',activity.get('reportHighlight',False),readonly)
                  + f'<span hidden data-source-kind="{table["kind"]}"></span></td>')
        search=' '.join(str(v) for v in row['values'] if v is not None).casefold()
        fields=dict(zip(table['headers'],row['values']))
        short=' · '.join(str(fields.get(key)) for key in ('Gene_Symbol','Gene_A','Gene_B','Event_ID','Adjusted_Tumor_CN') if fields.get(key) is not None)
        rows.append(f'<tr data-source-id="{identifier}" data-source-kind="{table["kind"]}" '
                    f'data-source-label="{escape(short,quote=True)}" '
                    f'data-source-search="{escape(search,quote=True)}" class="{"excluded-row" if decision == "EXCLUDE" else ""}">'
                    + controls + '<td class="source-data">' + ('Source QC highlighted' if row['sourceApproved'] else '') + '</td>'
                    + ''.join(f'<td class="source-data">{shown(v)}</td>' for v in row['values']) + '</tr>')
    table_id=escape(str(table['tableId']),quote=True)
    return (f'<section class="source-table-block"><p>{shown(table["fileName"])} · {shown(table["sheet"])} · '
            f'{len(rows)} source rows. Source QC highlighting is separate from report selection.</p>'
            + f'<label>Search all source columns <input type="search" data-source-search-for="{table_id}"></label>'
            f'<div class="table-scroll" role="region" aria-label="Full {table["kind"]} source table" tabindex="0">'
            f'<table class="full-source-table" id="{table_id}"><thead><tr><th>Include / Exclude</th>'
            '<th>Key relevant findings</th><th>Source QC highlight</th>'
            + ''.join(f'<th>{shown(header)}</th>' for header in table['headers'])
            + '</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
            '</section>')


def source_tables(report, review, kind, readonly=False):
    tables=[table for table in report.source_tables if table['kind']==kind]
    return ''.join(source_table(table,review,readonly=readonly) for table in tables) or '<p class="empty-state">No source table provided.</p>'


def figure(identifier, media, payload, caption):
    uri=f'data:{media};base64,{base64.b64encode(payload).decode()}'
    return f'<figure class="plot-figure" id="{identifier}"><img src="{uri}" alt="{shown(caption)}"><figcaption>{shown(caption)}</figcaption><button type="button" data-enlarge="{identifier}">Enlarge plot</button></figure>'


def cnv_plots(report, images):
    groups=[]
    panel_names=('A1','A2','B2','B3','C1','C2','C3','C4','C6')
    for asset in report.attachments:
        pages=images.get(str(asset['assetId']),())
        if str(asset['name']).endswith('_CNV_overview_plots.pdf') and len(pages)==9:
            pair=''.join(figure(f'cnv-panel-{name}',*pages[panel_names.index(name)],f'CNV {name}') for name in ('B3','C1'))
            groups.append(('B3 / C1',pair))
            for name in panel_names:
                if name not in {'B3','C1'}:
                    groups.append((name,figure(f'cnv-panel-{name}',*pages[panel_names.index(name)],f'CNV {name}')))
        elif 'cnv' in str(asset['name']).lower() or 'cancan' in str(asset['name']).lower():
            for page,(media,payload) in enumerate(pages):
                groups.append((str(asset['name']),figure(f'cnv-extra-{len(groups)}-{page}',media,payload,str(asset['name']))))
    if not groups:
        return '<p class="empty-state">No CNV plots provided.</p>'
    buttons=''.join(f'<button type="button" data-v3-plot="cnv-slide-{i}" aria-pressed="{str(i==0).lower()}">{shown(name)}</button>' for i,(name,_) in enumerate(groups))
    slides=''.join(f'<div class="cnv-slide" id="cnv-slide-{i}"{" hidden" if i else ""}>{body}</div>' for i,(_,body) in enumerate(groups))
    return '<div class="plot-switcher" role="group" aria-label="Select CNV plot">'+buttons+'</div>'+slides


def rna_plots(report, images):
    results=[]
    for asset in report.attachments:
        if 'domain_plot' not in str(asset['name']):
            continue
        for page,(media,payload) in enumerate(images.get(str(asset['assetId']),())):
            results.append(figure(f'rna-plot-{len(results)}-{page}',media,payload,str(asset['name'])))
    return ('<p>Source domain plots. Source QC approval and report highlights are independent; '
            'plots are not automatically matched by approximate filenames.</p>'+''.join(results)
            if results else '<p class="empty-state">No RNA domain plots provided.</p>')


def enhance_context(context, report, review, images, readonly):
    context['variant_source_tables']=''
    context['variant_section_qc']=qc_control(review,'variants',readonly=readonly)
    context['signature_section_qc']=qc_control(review,'signatures',readonly=readonly)
    context['cnv_content']=(qc_control(review,'cnv',readonly=readonly)
        + '<div class="subview-switcher" role="group" aria-label="CNV view"><button type="button" data-cnv-view="table" aria-pressed="true">Table</button><button type="button" data-cnv-view="plots" aria-pressed="false">Plots</button></div>'
        + '<div id="cnv-table-view">'+source_tables(report,review,'CNV',readonly)+'</div>'
        + '<div id="cnv-plots-view" hidden>'+cnv_plots(report,images)+'</div>')
    context['rna_content'] = qc_control(review,'rna',readonly=readonly) + source_tables(report,review,'RNA',readonly) + rna_plots(report,images)
    context['report_section_qc']=''.join(qc_control(review,key,readonly=readonly,suffix='report') for key in QC_LABELS)
    context['signature_highlights']=''
    from .report_pdf import project_report_export
    selected=project_report_export(report,review)
    source_items=[(kind,row) for kind in ('cnv','rna') for row in selected[kind]]
    def source_label(kind,row):
        fields=row['fields']
        return kind.upper()+' · '+' · '.join(str(fields.get(key)) for key in ('Gene_Symbol','Gene_A','Gene_B','Event_ID','Adjusted_Tumor_CN') if fields.get(key) is not None)
    source_list=''.join('<li>'+shown(source_label(kind,row))+'</li>' for kind,row in source_items)
    highlights=[row['gene']+' · '+row['protein'] for row in selected['variants'] if row['review']['reportHighlight']]
    highlights += [source_label(kind,row) for kind,row in source_items if row['review']['reportHighlight']]
    highlights += [item['metricId'].upper()+' · '+str(item['value']) for item in selected['measurements'] if item['metricId'] in selected['metricHighlights']]
    context['new_review_summary']=('<section><h3>Key relevant findings</h3><ul id="v3-key-findings">'+''.join('<li>'+shown(text)+'</li>' for text in highlights)
        +f'</ul><p id="v3-key-empty"{" hidden" if highlights else ""}>No included highlights selected.</p></section>'
        +'<section><h3>Included CNV and RNA findings</h3><ul id="v3-source-findings">'+source_list
        +f'</ul><p id="v3-source-empty"{" hidden" if source_items else ""}>No CNV or RNA findings selected.</p></section>')


def presentation_figures(review,assets,upload_url,csrf,readonly):
    cards=[]
    for item in review.presentation_figures:
        payload=assets.get(item['figureId'])
        if payload is None: continue
        uri='data:image/png;base64,'+base64.b64encode(payload).decode()
        cards.append(f'<div data-figure-card="{item["figureId"]}"><img src="{uri}" alt="Presentation figure">'
                     f'<p class="figure-caption-readonly">{shown(item["caption"])}</p></div>')
    controls=(f'<label>Add presentation figures <input type="file" id="figure-upload" accept="image/png,image/jpeg,image/webp" multiple data-figure-edit data-upload-url="{escape(upload_url,quote=True)}" data-csrf="{escape(csrf or "",quote=True)}"></label>'
              if upload_url and not readonly else '')
    return ('<section id="presentation-figures"><h3>Presentation figures</h3><p>Selected figures are appended at the end of the landscape presentation PDF. Captions and order are saved with the review. PNG, JPEG or WebP; up to 8 MB per image, 30 selected figures. Very large figures are resized while preserving their aspect ratio.</p>'
        +controls+'<p id="figure-upload-status" role="status" aria-live="polite"></p><div id="figure-list">'+''.join(cards)+'</div></section>')
