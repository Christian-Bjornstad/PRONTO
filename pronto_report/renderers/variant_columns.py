"""Stable extra columns joined to the exact source occurrence."""
from html import escape


def columns(report):
    result = [('field', 'genomicLocation', 'Genomic location'),
              ('field', 'dnaChange', 'DNA change'),
              ('annotation', 'tier', 'Source tier')]
    annotation_keys = dict.fromkeys(item['key'] for variant in report.variants
                                    for item in variant.get('annotations', ()))
    result.extend(('annotation', key, str(key)) for key in annotation_keys
                  if key not in {'codingStatus', 'depthTumourDna', 'tier'})
    for table in report.source_tables:
        if table['kind'] == 'VARIANTS':
            result.extend(('source', (table['tableId'], index), str(header))
                          for index, header in enumerate(table['headers']))
    return result + [('field', 'occurrenceId', 'Occurrence ID'),
                     ('field', 'variantId', 'Variant ID')]


def headers(report):
    return ('<th scope="col">IGV QC</th><th scope="col">Review comment</th>'
            '<th scope="col">Legacy classification (read-only)</th>'
            + ''.join(f'<th scope="col">{escape(label)}</th>'
                      for _, _, label in columns(report)))


def value_reader(report):
    """Index once per render, without retaining patient data in a global cache."""
    selected_columns=columns(report)
    source_rows={}
    for table in report.source_tables:
        if table['kind']=='VARIANTS':
            for row in table['rows']:
                source_rows.setdefault((table['tableId'],row.get('occurrenceId')),[]).append(row['values'])
    return lambda variant:_values(selected_columns,source_rows,variant)


def values(report, variant):
    return value_reader(report)(variant)


def _values(selected_columns, source_rows, variant):
    annotations = {item['key']: item.get('value') for item in variant.get('annotations', ())}
    result = []
    for kind, key, _ in selected_columns:
        if kind == 'source':
            table_id, index = key
            matches = [row[index] for row in source_rows.get((table_id,variant['occurrenceId']),())]
            value = ' / '.join('' if item is None else str(item) for item in matches)
        else:
            value = variant.get(key) if kind == 'field' else annotations.get(key)
        result.append('' if value is None else str(value))
    return result
