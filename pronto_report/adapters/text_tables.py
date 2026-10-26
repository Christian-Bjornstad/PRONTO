"""Bounded text records with comments outside quoted cells only."""
import csv
from itertools import chain
from pathlib import Path


class _RecordLines:
    """Let csv.reader determine record boundaries, including multiline cells."""
    def __init__(self, stream, max_rows):
        self.stream = stream
        self.max_rows = max_rows
        self.at_record_start = True
        self.reading_header = True
        self.physical_rows = 0

    def __iter__(self):
        return self

    def __next__(self):
        for line in self.stream:
            self.physical_rows += 1
            if len(line) > 1024 * 1024 or self.physical_rows > self.max_rows + 500:
                raise ValueError('Kildetabell overskrider radgrensen.')
            if self.at_record_start:
                if line.startswith('#sample_type\t'):
                    line = line[1:]
                elif line.startswith('#') or (self.reading_header and line.startswith('"#')) or not line.strip():
                    continue
            self.at_record_start = False
            return line
        raise StopIteration


def read_text_rows(path, *, delimiter=None, max_bytes=25 * 1024 * 1024,
                   max_rows=10000, max_columns=500):
    """Read raw string values without exposing source paths in parser errors."""
    path = Path(path)
    try:
        if path.stat().st_size > max_bytes:
            raise ValueError('Kildetabell er for stor eller utilgjengelig.')
        with path.open(encoding='utf-8-sig', newline='') as stream:
            lines = _RecordLines(stream, max_rows)
            first = next(lines, None)
            if first is None:
                raise ValueError('Tom kildetabell.')
            selected = delimiter if delimiter is not None else '\t' if '\t' in first else ';' if ';' in first else ','
            reader = csv.reader(chain((first,), lines), delimiter=selected, strict=True)
            columns = next(reader)
            lines.reading_header = False
            lines.at_record_start = True
            # A known TSOPPI metadata export joins these three header names
            # with spaces while writing their data as three tab-separated cells.
            joined = 'Version_string_TSOPPI_reported_on_mol-MDT  Molecular_pathology_comment  Sample_info_comment'
            repair = bool(columns and columns[-1] == joined and
                          {'Sample_id', 'Sequencing_run_id', 'Study_id'} <= set(columns))
            if repair:
                columns = [*columns[:-1], *joined.split('  ')]
            nonempty_columns = [column for column in columns if column]
            if len(columns) > max_columns or len(nonempty_columns) != len(set(nonempty_columns)):
                raise ValueError('Kildetabell har ugyldige eller gjentatte kolonner.')
            rows = []
            for values in reader:
                lines.at_record_start = True
                if repair and len(values) == len(columns) - 2:
                    values = [*values, '', '']
                if len(values) != len(columns) or len(rows) >= max_rows:
                    raise ValueError('Kildetabell har ugyldig struktur eller størrelse.')
                rows.append(dict(zip(columns, values)))
    except (OSError, UnicodeError, csv.Error):
        raise ValueError('Kildetabell kunne ikke leses eller har ugyldig tekstformat.') from None
    return rows
