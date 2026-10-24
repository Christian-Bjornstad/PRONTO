"""Preserve one explicitly selected Cancan gene table without interpreting calls."""
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
import re

from .source_tables import MAX_BYTES, MAX_COLUMNS, MAX_ROWS

_SAMPLE = re.compile(r'^#\s*Sample\s*id\s*(?::|=|\t)\s*(\S+)\s*$', re.IGNORECASE)


def read_cancan_table(path: Path, *, sample_id: str) -> dict:
    path = Path(path)
    if path.suffix.lower() != '.tsv' or path.stat().st_size > MAX_BYTES:
        raise ValueError('Unsupported or oversized Cancan table')
    payload = path.read_bytes()
    preamble, claims, rows, headers = [], [], [], None
    with path.open(encoding='utf-8-sig', newline='') as stream:
        for index, row in enumerate(csv.reader(stream, delimiter='\t'), start=1):
            if index > MAX_ROWS + 500 or len(row) > MAX_COLUMNS:
                raise ValueError('Cancan table exceeds row or column limit')
            if not any(row):
                continue
            if headers is None and row[0].startswith('#'):
                comment = '\t'.join(row)
                if len(comment) > 10000 or len(preamble) >= 500:
                    raise ValueError('Cancan preamble exceeds limit')
                preamble.append(comment)
                match = _SAMPLE.fullmatch(comment)
                if match:
                    claims.append(match.group(1))
                continue
            if headers is None:
                if not {'chr', 'gene.name', 'total.cn'} <= set(row) or len(row) != len(set(row)):
                    raise ValueError('Expected Cancan gene table header was not found')
                headers = row
            else:
                if len(row) != len(headers) or len(rows) >= MAX_ROWS:
                    raise ValueError('Cancan row does not match table width or limit')
                rows.append((index, row))
    if headers is None or not claims or set(claims) != {sample_id}:
        raise ValueError('Cancan table lacks an exact matching sample declaration')
    table_id = 'source-' + sha256(('CNV-Cancan' + path.name).encode()).hexdigest()[:24]
    occurrences = Counter()
    records = []
    for index, values in rows:
        fields = dict(zip(headers, values))
        identity = [fields.get(key) for key in ('chr', 'start.pos.gene', 'end.pos.gene', 'gene.id', 'gene.name')]
        finding_id = 'finding-' + sha256(json.dumps([table_id, identity], sort_keys=True).encode()).hexdigest()[:24]
        occurrences[finding_id] += 1
        records.append({'findingId': finding_id, 'occurrenceId': f'{finding_id}:{occurrences[finding_id]}',
                        'record': index, 'values': values, 'sourceApproved': False, 'sourceSampleId': sample_id})
    return {'tableId': table_id, 'kind': 'CNV', 'fileName': path.name, 'sheet': '',
            'sha256': sha256(payload).hexdigest(), 'headers': headers, 'rows': records,
            'preamble': preamble, 'demo': False}
