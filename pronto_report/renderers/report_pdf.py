"""Saved snapshot PDFs: landscape presentation and portrait ESMO-style report."""
from collections.abc import Mapping
from html import escape
from io import BytesIO
import json

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak, Image

from pronto_report.migration import migrate_review_state_to_v3
from pronto_report.serialization import serialize_report_data, serialize_review_state

TEMPLATE_VERSION = '1.0'
BLUE = '#203b63'; GREEN = '#14592c'; OLIVE = '#708322'
QC_COLORS = {'PASS':'#399a44', 'CONDITIONAL':'#e88917', 'FAIL':'#cf2525', 'NOT_REVIEWED':'#777777'}


def project_report_export(report, review):
    if review.report_id != report.report_id:
        raise ValueError('Saved report/review mismatch')
    r=json.loads(serialize_report_data(report))
    v=json.loads(serialize_review_state(migrate_review_state_to_v3(review)))
    for correction in v['valueCorrections']:
        parts=correction['path'].strip('/').split('/')
        if len(parts)==2 and parts[0]=='sample':
            r['sample'][parts[1]]=correction['correctedValue']
        elif len(parts)==3 and parts[0]=='biomarkers' and parts[2]=='value':
            r['biomarkers'][int(parts[1])]['value']=correction['correctedValue']
    selected={item['variantId']:item for item in v['variantReviews'] if item['reportingDecision']=='INCLUDE'}
    variants=[]
    for identifier,activity in selected.items():
        occurrences=[item for item in r['variants'] if item['variantId']==identifier]
        if not occurrences: raise ValueError('Unknown included variant')
        def common(key):
            values=list(dict.fromkeys(str(item[key]) for item in occurrences if item.get(key) is not None))
            return ' / '.join(values)
        annotations={}
        for item in occurrences:
            for annotation in item['annotations']:
                annotations.setdefault(annotation['key'],[])
                if annotation['value'] not in annotations[annotation['key']]: annotations[annotation['key']].append(annotation['value'])
        variants.append({'id':identifier,'gene':common('gene'),'protein':common('proteinChange'),
            'dna':common('dnaChange'),'location':common('genomicLocation'),'af':common('alleleFrequency'),
            'annotations':{key:' / '.join(str(value) for value in values) for key,values in annotations.items()},'review':activity})
    finding_activities={item['findingId']:item for item in v['findingReviews'] if item['reportingDecision']=='INCLUDE'}
    findings={'CNV':[],'RNA':[]}
    grouped={}
    for table in r.get('sourceTables',[]):
        if table['kind'] not in findings: continue
        for row in table['rows']:
            identifier=row['findingId']
            if identifier not in finding_activities: continue
            group=grouped.setdefault(identifier,{'kind':table['kind'],'fields':{},'source':table['fileName'],'demo':table['demo']})
            for header,value in zip(table['headers'],row['values']):
                values=group['fields'].setdefault(header,[])
                if value not in values and value is not None and value!='': values.append(value)
    for identifier,group in grouped.items():
        fields={header:(values[0] if len(values)==1 else ' / '.join(str(value) for value in values))
                for header,values in group['fields'].items()}
        findings[group['kind']].append({'id':identifier,'fields':fields,'review':finding_activities[identifier],
                                       'source':group['source'],'demo':group['demo']})
    highlights={item['metricId'] for item in v['biomarkerReviews'] if item['reportHighlight']}
    return {'reportId':report.report_id,'revision':review.revision,'status':review.status,
        'sample':r['sample'],'run':r['run'],'measurements':r['biomarkers'], 'variants':variants,
        'cnv':findings['CNV'],'rna':findings['RNA'],'notes':v['notes'],'qc':v['sectionQc'],
        'overallQc':v['runQcAssessment'],'metricHighlights':highlights,
        'figures':v['presentationFigures'],'reviewer':v.get('finalizationAttribution',v.get('lastSavedAttribution',{})),
        'corrections':v['valueCorrections'], 'diagnostics':r['diagnostics']}


def _text(value):
    return 'Not provided' if value is None or value=='' else str(value)


def _paragraph(value, *, size=9, color='#202833', bold=False):
    style=ParagraphStyle('cell',fontName='Helvetica-Bold' if bold else 'Helvetica',fontSize=size,
                         leading=size*1.3,textColor=colors.HexColor(color),spaceAfter=4,
                         splitLongWords=True)
    text=escape(_text(value)).replace('\n','<br/>')
    return Paragraph(text,style)


def _heading(label,color=BLUE):
    return _paragraph(label,size=15,color=color,bold=True)


def _table(headers, rows, width, color=GREEN, size=7.4, proportions=None):
    if not rows: return _paragraph('Not provided / no findings selected',size=8)
    widths=[width*weight/sum(proportions) for weight in proportions] if proportions else [width/len(headers)]*len(headers)
    data=[[_paragraph(value,size=size,color='#ffffff',bold=True) for value in headers]]
    data.extend([[_paragraph(value,size=size) for value in row] for row in rows])
    table=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT',splitByRow=1,splitInRow=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(color)),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#e6ede7'),colors.HexColor('#f6f8f6')]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),
        ('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
    return table


def _qc(label,assessment):
    status=assessment['status']
    choices=['PASS','CONDITIONAL','FAIL']
    indicator=Table([[('X' if choice==status else '') for choice in choices]],colWidths=[15]*3,rowHeights=[13])
    indicator.setStyle(TableStyle([('BACKGROUND',(i,0),(i,0),colors.HexColor(QC_COLORS[choice])) for i,choice in enumerate(choices)]+
        [('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('FONTSIZE',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    result=Table([[_paragraph(f'{label} QC: {status}',size=8,color=QC_COLORS[status],bold=True),indicator]],colWidths=[145,45],hAlign='LEFT')
    result.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    return result


def _signatures(model,width):
    values={item['metricId']:item for item in model['measurements']}
    return _table(['Signature','Score','Range','Source'],[
        [f'{identifier.upper()} — {values.get(identifier,{}).get("label",identifier.upper())}',values.get(identifier,{}).get('value'),
         values.get(identifier,{}).get('displayRange','[0-100+]' if identifier=='tmb' else '[0-100]'),
         'DEMO' if values.get(identifier,{}).get('demo') else 'Source / saved correction' if identifier in values else 'Not provided']
        for identifier in ('tmb','msi','hrd')],width)


def _variant_table(model,width,compact=False):
    if compact:
        return _table(['Gene','Variant','Effect','VAF','Review'],[
            [item['gene'],item['protein'] or item['dna'],item['annotations'].get('codingStatus'),item['af'],
             item['review']['clinicalClassification']] for item in model['variants']],width,BLUE,size=7)
    return _table(['Gene','Transcript','Position','Variant','Effect','Depth','VAF','Review'],[
        [item['gene'],item['annotations'].get('refSeqMrna') or item['annotations'].get('ensemblTranscript'),
         item['location'],item['protein'] or item['dna'],item['annotations'].get('codingStatus'),
         item['annotations'].get('depthTumourDna'),item['af'],item['review']['clinicalClassification']]
        for item in model['variants']],width,proportions=[.8,1.2,1.1,1.1,1,.7,.6,.8])


def _cnv_table(model,width):
    return _table(['Gene','Chromosome','Start','Tumour CN','Adjusted tumour CN','Normal CN'],[
        [item['fields'].get(key) for key in ('Gene_Symbol','Chromosome','Gene_Start','Tumor_CN','Adjusted_Tumor_CN','Normal_CN')]
        for item in model['cnv']],width)


def _rna_table(model,width):
    return _table(['Gene A','Gene B','Event','Transcript A','Exon A','Exon B','Source QC'],[
        [item['fields'].get('Gene_A'),item['fields'].get('Gene_B'),
         item['fields'].get('Provisional_Event_Type'),item['fields'].get('Transcript_A') or item['fields'].get('Transcript_S'),
         item['fields'].get('Exon_A'),item['fields'].get('Exon_B'),item['fields'].get('QC_Verdict')]
        for item in model['rna']],width)


def _highlight_table(model,width,color=OLIVE):
    rows=[[item['gene'],item['protein'] or item['dna'],item['review']['clinicalClassification']]
          for item in model['variants'] if item['review']['reportHighlight']]
    for key,label in [('cnv','CNV'),('rna','RNA')]:
        for item in model[key]:
            if item['review']['reportHighlight']:
                f=item['fields'];rows.append([f.get('Gene_Symbol') or f.get('Gene_A'),
                    f.get('Event_ID') or f.get('Gene_B') or f.get('Adjusted_Tumor_CN'),label])
    rows.extend([item['label'],item['value'],'DEMO' if item.get('demo') else 'Signature']
                for item in model['measurements'] if item['metricId'] in model['metricHighlights'])
    return _table(['Gene / molecular marker','Variant / result','Review / type'],rows,width,color)


def _note(model,key,label,color=BLUE):
    return [_heading(label,color),_paragraph(model['notes'].get(key))]


def _header(canvas,doc,model,initials,title=''):
    width,height=doc.pagesize;canvas.saveState()
    canvas.setFillColor(colors.HexColor(BLUE));canvas.setFont('Helvetica-Bold',18)
    canvas.drawString(22,height-31,title or 'InPreD - Report')
    canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#333333'))
    canvas.drawRightString(width-22,height-20,f'Patient ID: {_text(model["sample"].get("patientPseudonym"))}')
    canvas.drawRightString(width-22,height-32,f'Sample: {_text(model["sample"].get("sampleId"))}')
    canvas.drawRightString(width-22,15,f'{model["status"]} | revision {model["revision"]} | {initials} | page {doc.page}')
    canvas.restoreState()


def _draw_column(canvas,flowables,x,top,width,height):
    """Split flowables at the first-page boundary and return every remaining part."""
    remaining=[];available=height;y=top
    for index,item in enumerate(flowables):
        _,h=item.wrapOn(canvas,width,available)
        if h<=available:
            item.drawOn(canvas,x,y-h);y-=h+5;available-=h+5
        else:
            pieces=item.splitOn(canvas,width,max(0,available)) if available>20 else []
            if pieces:
                first=pieces[0];_,h=first.wrapOn(canvas,width,available);first.drawOn(canvas,x,y-h)
                remaining.extend(pieces[1:])
            else: remaining.append(item)
            remaining.extend(flowables[index+1:]);break
    return remaining


def render_report_pdf(report, review, *, layout, export_initials, figure_assets: Mapping[str,bytes] | None=None):
    if layout not in {'PRESENTATION','ESMO'} or not export_initials:
        raise ValueError('Invalid PDF layout or attribution')
    model=project_report_export(report,review);buffer=BytesIO()
    page_size=landscape(A4) if layout=='PRESENTATION' else A4
    doc=SimpleDocTemplate(buffer,pagesize=page_size,leftMargin=22,rightMargin=22,topMargin=58,bottomMargin=28,
        title=f'InPreD {layout} {model["reportId"]}',author=export_initials)
    width=page_size[0]-44
    warning=[_paragraph(d['message'],size=8,color='#9a6010') for d in model['diagnostics'] if d['code']=='MIXED_SAMPLE_DEMO']
    if layout=='ESMO':
        story=[_heading('Summary',BLUE),*warning,
            _heading('Patient and sample details'),
            _table(['Field','Value'],[[key,value] for key,value in model['sample'].items()],width,BLUE,size=9),
            *_note(model,'patientDetails','Additional patient and sample details'),
            _heading('Assay details'),_table(['Field','Value'],[[key,value] for key,value in model['run'].items()],width,BLUE,size=9),
            *_note(model,'assayMethods','Assay / methods / limitations'),
            _heading('Assay quality evaluation'),_qc('Overall',model['overallQc']),_paragraph(model['overallQc'].get('comment')),
            *_note(model,'history','History / Reason for testing'),
            *_note(model,'summary','Summary of most relevant findings'),PageBreak(),
            _heading('Results',GREEN),_heading('Mutations',GREEN),_qc('Small variants',model['qc']['variants']),_variant_table(model,width),
            _heading('Copy number alterations',GREEN),_qc('CNV',model['qc']['cnv']),_cnv_table(model,width),
            _heading('Gene fusions and splice variants',GREEN),_qc('RNA',model['qc']['rna']),_rna_table(model,width),
            _heading('Mutational signatures',GREEN),_qc('Mutational signatures',model['qc']['signatures']),_signatures(model,width),
            *_note(model,'variantDescription','Variant description',GREEN),PageBreak(),
            _heading('Key relevant findings',OLIVE),_highlight_table(model,width),
            *_note(model,'biomarkerContext','Therapeutic context',OLIVE),
            *_note(model,'clinicalEvidence','Clinical actionability annotation',OLIVE),
            *_note(model,'clinicalTrials','Clinical trial matching',OLIVE),
            *_note(model,'followUp','Findings for potential follow-up',OLIVE),
            *_note(model,'additional','Additional comments',OLIVE),
            *(_note(model,'importedLegacyNote','Imported legacy note',OLIVE) if model['notes'].get('importedLegacyNote') else []),
            *_note(model,'references','References',OLIVE)]
        first=lambda c,d:_header(c,d,model,export_initials)
    else:
        sidebar=[_paragraph('InPreD',size=13,color=BLUE,bold=True)]
        for key,value in model['sample'].items(): sidebar.extend([_paragraph(key,size=7,bold=True),_paragraph(value,size=8)])
        sidebar.extend([_paragraph('Assay / Run',size=7,bold=True),_paragraph(model['run'].get('runId'),size=7),_paragraph(f'Overall QC: {model["overallQc"]["status"]}',size=7,color=QC_COLORS[model['overallQc']['status']])])
        qc_summary=Table([[_qc('CNV',model['qc']['cnv']),_qc('RNA',model['qc']['rna'])]],colWidths=[210,210],hAlign='LEFT')
        qc_summary.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('VALIGN',(0,0),(-1,-1),'TOP')]))
        main=[*warning,_heading('Mutational signatures',BLUE),_qc('Signatures',model['qc']['signatures']),_signatures(model,420),qc_summary,
              _heading('Key relevant findings',BLUE),_highlight_table(model,420,BLUE),
              *_note(model,'summary','Summary of most relevant findings'),
              *_note(model,'biomarkerContext','Therapeutic context'),
              *_note(model,'variantDescription','Variant description')]
        right=[_heading(f'Mutations (N={len(model["variants"])})',BLUE),_qc('Small variants',model['qc']['variants']),_variant_table(model,225,True),_paragraph('VUS: Variant of uncertain significance',size=7)]
        # Measure with a throwaway canvas; actual columns are drawn in onFirstPage.
        from reportlab.pdfgen.canvas import Canvas
        test_canvas=Canvas(BytesIO(),pagesize=page_size)
        columns=[(sidebar,22,95),(main,129,420),(right,561,259)]
        remainders=[]
        for flows,x,w in columns:
            remainders.extend(_draw_column(test_canvas,flows,x,page_size[1]-62,w,page_size[1]-95))
        story=[Spacer(1,1)]
        if remainders: story += [PageBreak(),_heading('Results - continued'),*remainders]
        extra=[]
        if model['cnv']: extra += [_heading('Copy number alterations'),_qc('CNV',model['qc']['cnv']),_cnv_table(model,width)]
        if model['rna']: extra += [_heading('Fusions and splice'),_qc('RNA',model['qc']['rna']),_rna_table(model,width)]
        if model['overallQc'].get('comment'): extra += [_heading('Overall QC comment'),_paragraph(model['overallQc']['comment'])]
        for key,label in [('history','History / Reason for testing'),('patientDetails','Patient and sample details'),
                          ('clinicalEvidence','Clinical actionability context'),('clinicalTrials','Clinical trial context'),
                          ('followUp','Follow-up'),('additional','Additional comments'),('importedLegacyNote','Imported legacy note'),('assayMethods','Assay details'),('references','References')]:
            if model['notes'].get(key): extra.extend(_note(model,key,label))
        if extra: story += [PageBreak(),_heading('Additional results and context'),*extra]
        def first(c,d):
            _header(c,d,model,export_initials,'Results')
            c.setFillColor(colors.HexColor('#e8edf3'));c.rect(18,26,103,page_size[1]-75,fill=1,stroke=0)
            for flows,x,w in columns: _draw_column(c,flows,x,page_size[1]-62,w,page_size[1]-95)
        if model['figures']:
            assets=figure_assets or {}
            for number,figure in enumerate(model['figures'],1):
                payload=assets.get(figure['figureId'])
                if payload is None: raise ValueError('Presentation figure is unavailable')
                heading=_heading(f'Presentation figure {number}')
                caption=_paragraph(figure['caption'])
                caption_height=caption.wrap(width-12,doc.height)[1]
                heading_height=heading.wrap(width-12,doc.height)[1]
                image=Image(BytesIO(payload));image._restrictSize(width-12,max(80,doc.height-caption_height-heading_height-24))
                story.extend([PageBreak(),heading,image,caption])
    doc.build(story,onFirstPage=first,onLaterPages=lambda c,d:_header(c,d,model,export_initials))
    return buffer.getvalue()
