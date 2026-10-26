"""16:9 MolMDT results page, with all overflow preserved on continuation pages."""
from io import BytesIO
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, PageBreak, Spacer

from .report_pdf import (_paragraph, _heading, _table, _variant_table, _cnv_table,
    _rna_table, _note, _qc, _header, _draw_column, BLUE, GREEN, FIELD_LABELS, QC_COLORS)

PAGE_SIZE = (960, 540)


def rna_read_support(fields):
    percentage = fields.get('Event_Support_Dedup_Percentage')
    if percentage not in (None, ''):
        return str(percentage) if str(percentage).endswith('%') else f'{percentage}%'
    return fields.get('Read_Support')


def highlighted_rows(model):
    rows = []
    for item in model['measurements']:
        if item['metricId'] in model['metricHighlights']:
            activity = model['metricReviews'].get(item['metricId'], {})
            rows.append({'label':item['metricId'].upper(), 'alteration':activity.get('presentation',{}).get('status',''),
                'effect':item['label'], 'value':item.get('value'), 'activity':activity})
    for kind in ('cnv','rna'):
        for item in model[kind]:
            if not item['review']['reportHighlight']:
                continue
            f=item['fields']
            rows.append({'label':f.get('Gene_Symbol') or f.get('Gene_A'),
                'alteration':'CNV' if kind=='cnv' else f.get('Gene_B') or f.get('Event_ID'),
                'effect':f.get('CN_Change') if kind=='cnv' else f.get('Provisional_Event_Type'),
                'value':f.get('Tumor_CN') if kind=='cnv' else rna_read_support(f), 'activity':item['review']})
    for item in model['variants']:
        if item['review']['reportHighlight']:
            rows.append({'label':item['gene'], 'alteration':item['protein'] or item['dna'],
                'effect':item['annotations'].get('codingStatus'), 'value':item['af'], 'activity':item['review']})
    return rows


def key_table(model, width):
    rows=highlighted_rows(model)
    labels=['Gene /\nMolecular marker','Alteration','Effect /\nEvent','VAF /\nCN / Score','GoF /\nLoF',
        'Therapeutic context','', 'Approved targeted therapy (EMA)','']
    second=['','','','','','Sensitive','Resistant',"Patient’s tumour type",'Other tumour type']
    weights=[72,64,62,48,38,79,79,90,80]
    widths=[width*w/sum(weights) for w in weights]
    data=[[_paragraph(x,size=8,bold=True) for x in labels],[_paragraph(x,size=7.4) for x in second]]
    for row in rows:
        annotation=row['activity'].get('presentation',{})
        values=[row['label'],row['alteration'],row['effect'],row['value'],annotation.get('functionalEffect'),
            annotation.get('sensitive'),annotation.get('resistant'),annotation.get('emaTumour'),annotation.get('emaOther')]
        data.append([_paragraph('—' if v in (None,'') else v,size=8,bold=i==0) for i,v in enumerate(values)])
    if not rows:
        data.append([_paragraph('No highlights selected',size=8)]+['']*8)
    table=Table(data,colWidths=widths,repeatRows=2,splitByRow=1,splitInRow=1,hAlign='LEFT')
    style=[('BACKGROUND',(0,0),(-1,1),colors.HexColor('#e6ecf2')),
        ('BACKGROUND',(5,1),(5,1),colors.HexColor('#d5e3bd')),
        ('BACKGROUND',(6,1),(6,1),colors.HexColor('#ff9898')),
        ('BACKGROUND',(7,2),(7,-1),colors.HexColor('#d1daea')),
        ('SPAN',(5,0),(6,0)),('SPAN',(7,0),(8,0)),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),
        ('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#dce4ef'))]
    for index in range(5): style.append(('SPAN',(index,0),(index,1)))
    table.setStyle(TableStyle(style))
    return table


def top_tables(model):
    values={item['metricId']:item for item in model['measurements']}
    signatures=_table(['Signature','Score','Status'],[
        [name.upper()+' — '+values.get(name,{}).get('label',name.upper()),values.get(name,{}).get('value'),
         model['metricReviews'].get(name,{}).get('presentation',{}).get('status','—')]
        for name in ('tmb','msi','hrd')],188,size=7.2,proportions=[.60,.17,.23])
    cnv=_table(['Gene','Chr/Loc','Tumour CN'],[
        [item['fields'].get('Gene_Symbol'),item['fields'].get('Cytoband') or item['fields'].get('Chromosome'),
         item['fields'].get('Tumor_CN')] for item in model['cnv']] or [['—']*3],155,size=7.2)
    rna=_table(['Gene','Alteration','Read support','Review'],[
        [item['fields'].get('Gene_A'),str(item['fields'].get('Gene_B') or '')+' '+str(item['fields'].get('Provisional_Event_Type') or ''),
         rna_read_support(item['fields']),item['review'].get('comment','—')]
        for item in model['rna']] or [['—']*4],245,size=7.2,proportions=[.18,.38,.23,.21])
    return [([_paragraph('Mutational signatures',size=12,color=BLUE,bold=True),signatures],108,188),
        ([_paragraph('Copy number alterations',size=12,color=BLUE,bold=True),cnv],302,155),
        ([_paragraph('Fusions and splice',size=12,color=BLUE,bold=True),rna],463,245)]


def presentation_story(model, doc, author):
    from reportlab.pdfgen.canvas import Canvas
    test=Canvas(BytesIO(),pagesize=PAGE_SIZE)
    sidebar=[_paragraph('InPreD',size=14,color=BLUE,bold=True)]
    for key,value in model['sample'].items():
        sidebar.extend([_paragraph(FIELD_LABELS.get(key,key),size=7,bold=True),_paragraph(value,size=8)])
    sidebar.extend([_paragraph('Assay / Run',size=7,bold=True),_paragraph(model['run'].get('runId'),size=7),
        _paragraph(f'Overall QC: {model["overallQc"]["status"]}',size=7,color=QC_COLORS[model['overallQc']['status']])])
    top=top_tables(model)
    # Reserve space for highlights; unusually long top tables continue after page 1.
    top_height=min(142,max(sum(flow.wrapOn(test,w,450)[1]+5 for flow in flows) for flows,_,w in top))
    main_top=PAGE_SIZE[1]-60-top_height-15
    main=[_heading('Key relevant findings'),key_table(model,600),Spacer(1,22),_heading('Variant description')]
    for row in highlighted_rows(model):
        description=row['activity'].get('presentation',{}).get('description')
        if description:
            main.extend([_paragraph(row['label'],size=9,bold=True),_paragraph(description,size=9)])
    for key,label in [('variantDescription',''),('summary','Summary'),('biomarkerContext','Therapeutic context')]:
        if model['notes'].get(key):
            if label: main.append(_paragraph(label,size=9,bold=True))
            main.append(_paragraph(model['notes'][key],size=9))
    if not any(model['notes'].get(k) for k in ('variantDescription','summary','biomarkerContext')) and not any(
            row['activity'].get('presentation',{}).get('description') for row in highlighted_rows(model)):
        main.append(_paragraph('—',size=9))
    right=[_paragraph(f'Mutations (N={len(model["variants"])})',size=12,color=BLUE,bold=True),
        _variant_table(model,223,True),_paragraph('VUS: Variant of uncertain significance',size=7)]
    columns=[(sidebar,9,PAGE_SIZE[1]-56,89,PAGE_SIZE[1]-90)]
    columns.extend((flows,x,PAGE_SIZE[1]-56,w,top_height) for flows,x,w in top)
    columns.extend([(main,108,main_top,600,main_top-28),(right,725,PAGE_SIZE[1]-56,223,PAGE_SIZE[1]-90)])
    remaining=[]
    for flows,x,y,w,h in columns:
        remaining.extend(_draw_column(test,flows,x,y,w,h))
    story=[Spacer(1,1)]
    if remaining: story.extend([PageBreak(),_heading('Results — continued'),*remaining])
    extra=[]
    # Preserve complete source annotations and all QC on detail pages.
    extra.extend([_qc('CNV',model['qc']['cnv']),_qc('RNA',model['qc']['rna']),
        _qc('Signatures',model['qc']['signatures']),_qc('Small variants',model['qc']['variants'])])
    if model['cnv']: extra.extend([_heading('Copy number alterations'),_cnv_table(model,916)])
    if model['rna']: extra.extend([_heading('Fusions and splice'),_rna_table(model,916)])
    if model['variants']: extra.extend([_heading('Mutation annotations'),_variant_table(model,916)])
    # The reference page omits source ranges; keep them explicitly in the appendix.
    from .report_pdf import _signatures
    extra.extend([_heading('Mutational signatures — details'),_signatures(model,916)])
    if model['overallQc'].get('comment'): extra.extend([_heading('Overall QC comment'),_paragraph(model['overallQc']['comment'])])
    for key,label in [('history','History / Reason for testing'),('patientDetails','Patient and sample details'),
        ('clinicalEvidence','Clinical actionability context'),('clinicalTrials','Clinical trial context'),('followUp','Follow-up'),
        ('additional','Additional comments'),('importedLegacyNote','Imported legacy note'),('assayMethods','Assay details'),('references','References')]:
        if model['notes'].get(key): extra.extend(_note(model,key,label))
    story.extend([PageBreak(),_heading('Additional results and context'),*extra])

    def first(canvas, document):
        _header(canvas,document,model,author,'Results',title_x=108)
        canvas.setFillColor(colors.HexColor('#e8edf3'))
        canvas.rect(4,8,99,PAGE_SIZE[1]-50,fill=1,stroke=0)
        for flows,x,y,w,h in columns: _draw_column(canvas,flows,x,y,w,h)
    return story,first
