"""Source-backed labels and display fields; original source tables remain intact."""
import re


def effect_label(value):
    text = str(value or '')
    return text.removeprefix('x:').removesuffix('_variant').replace('_', ' ')


def _provided(value):
    return str(value).strip() if value is not None and str(value).strip() not in {'', '.', 'N/A', 'NA'} else ''


def _exon_label(value):
    text = _provided(value)
    if not text:
        return ''
    match = re.fullmatch(r'(?:exon\s*)?(\d+)(?:st|nd|rd|th)?', text, re.IGNORECASE)
    intron = re.fullmatch(r'intron\s*\(\s*(?:exon|ex)\s*(\d+)\s*[-–]\s*(\d+)\s*\)', text, re.IGNORECASE)
    if intron:
        return f'intron ex{intron[1]}-{intron[2]}'
    return 'ex' + match[1] if match else text.replace('exon', 'ex').replace('Exon', 'ex')


def rna_display_fields(fields):
    """Name only what the source declares; never infer an exon-skipping event."""
    result = dict(fields)
    first, second = _provided(fields.get('Gene_A')), _provided(fields.get('Gene_B'))
    fusion = str(fields.get('Provisional_Event_Type', '')).casefold() == 'fusion'
    result['Gene_Label'] = f'{first}::{second}' if fusion and second and first != second else first
    partners = [(gene, _exon_label(fields.get(exon))) for gene, exon in ((first, 'Exon_A'), (second, 'Exon_B'))]
    if all(gene and exon for gene, exon in partners):
        result['Alteration_Label'] = (f'{first} ({partners[0][1]} / {partners[1][1]})' if not fusion and first==second
                                      else '::'.join(f'{gene}({exon})' for gene, exon in partners))
    else:
        result['Alteration_Label'] = _provided(fields.get('Event_ID')) or effect_label(fields.get('Provisional_Event_Type'))
    result['Effect_Label'] = effect_label(fields.get('Provisional_Event_Type'))
    return result


def rna_read_support(fields):
    percentage = fields.get('Event_Support_Dedup_Percentage')
    if _provided(percentage):
        return str(percentage) if str(percentage).endswith('%') else f'{percentage}%'
    return fields.get('Read_Support')


def presentation_sources(report):
    """Report labels for the editor; all raw annotations remain in the review tables."""
    result = {}
    for metric in report.biomarkers:
        result[metric['metricId']] = {'kind':'metric', 'label':metric['metricId'].upper(),
            'alteration':'', 'effect':metric['label'], 'value':metric.get('value')}
    for variant in report.variants:
        annotations = {item['key']:item['value'] for item in variant['annotations']}
        result[variant['variantId']] = {'kind':'variant', 'label':variant['gene'],
            'alteration':variant.get('proteinChange') or variant.get('dnaChange'),
            'effect':effect_label(annotations.get('codingStatus')), 'value':variant.get('alleleFrequency')}
    for table in report.source_tables:
        if table['kind'] not in {'CNV','RNA'}:
            continue
        for row in table['rows']:
            fields=dict(zip(table['headers'],row['values']))
            if table['kind']=='CNV':
                fields=cnv_display_fields(fields)
                values={'label':fields.get('Gene_Symbol'), 'alteration':'CNV', 'effect':'', 'value':fields.get('Tumor_CN')}
            else:
                fields=rna_display_fields(fields)
                values={'label':fields['Gene_Label'], 'alteration':fields['Alteration_Label'],
                        'effect':fields['Effect_Label'], 'value':rna_read_support(fields)}
            result[row['findingId']]={'kind':'finding', 'sourceKind':table['kind'], **values}
    return result


def cnv_display_fields(fields):
    result = dict(fields)
    for label, source in (('Gene_Symbol', 'gene.name'), ('Chromosome', 'chr'), ('Tumor_CN', 'total.cn')):
        if label not in result and source in result:
            result[label] = result[source]
    return result
