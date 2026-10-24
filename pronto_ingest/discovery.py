"""Recognise known outputs without reading alignments or following directory links.

No fuzzy patient matching: metadata defines identities, exact path components
identify sample-specific outputs, and unscoped supplementary tables need selection.
"""
from __future__ import annotations

import csv
from dataclasses import replace
import os
from pathlib import Path
import re
import stat

from .contracts import (DiscoveryPlan, ReportPlan, SourceCandidate, REQUIRED_ROLES,
                        ROLES, check_cancel)

MAX_FILES = 50000
MAX_DEPTH = 30
MAX_BYTES = 25 * 1024 * 1024
MAX_ROWS = 10000
IDENTIFIER = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')
SAMPLE_COLUMNS = ('Sample_ID', 'Sample_id', 'sample_id', 'sample_ID')


def regular_file(path):
    """Reject symlinks and Windows junction/reparse components, including parents."""
    path = Path(path).absolute()
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            return False
    return path.is_file()


def table_rows(path, *, header=None):
    """Bound complete text tables. Keep source bytes separately during import."""
    if not regular_file(path) or path.stat().st_size > MAX_BYTES:
        raise ValueError('Kildetabell er for stor eller utilgjengelig.')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        lines = []
        for line in stream:
            if len(line) > 1024 * 1024 or len(lines) > MAX_ROWS + 500:
                raise ValueError('Kildetabell overskrider radgrensen.')
            if line.startswith('#'):
                if line.startswith('#sample_type\t'):
                    lines.append(line[1:])
                continue
            if line.strip():
                lines.append(line)
    if not lines:
        raise ValueError('Tom kildetabell.')
    delimiter = '\t' if '\t' in lines[0] else ';' if ';' in lines[0] else ','
    rows = list(csv.DictReader(lines, delimiter=delimiter))
    if len(rows) > MAX_ROWS or any(None in row or len(row) > 500 for row in rows):
        raise ValueError('Kildetabell har ugyldig struktur eller størrelse.')
    if header and (not rows or not set(header) <= rows[0].keys()):
        raise ValueError('Kildetabell har ukjente kolonner.')
    return rows


def _headers(path):
    if path.stat().st_size > MAX_BYTES:
        return set()
    with path.open('rb') as stream:
        prefix = stream.read(256 * 1024).decode('utf-8-sig')
    for line in prefix.splitlines()[:500]:
        if line.startswith('#sample_type\t'):
            return set(line[1:].split('\t'))
        if line.startswith('#') or not line.strip():
            continue
        delimiter = '\t' if '\t' in line else ';' if ';' in line else ','
        columns = set(next(csv.reader([line], delimiter=delimiter)))
        if columns & {'Sample_id', 'sample_id', 'sample_type', 'sample_ID', 'Gene_symbol', 'Gene_Symbol', 'Provisional_Event_Type'}:
            return columns
    return set()


def _role(path, table_cache=None):
    name = path.name.lower()
    if path.suffix.lower() in {'.tsv', '.txt', '.csv'}:
        headers = _headers(path)
        if {'Sample_id', 'Sequencing_run_id', 'Study_id'} <= headers:
            return 'metadata'
        if {'sample_id', 'TMB', 'MSI'} <= headers:
            return 'summary'
        if {'Gene_symbol', 'Genomic_location', 'DNA_change'} <= headers:
            return 'variants'
        if {'sample_type', 'sample_ID'} <= headers:
            return 'sample_list'
        if 'Provisional_Event_Type' in headers:
            return 'rna_table'
        if 'Gene_Symbol' in headers:
            return 'cnv_table'
    elif path.suffix.lower() == '.xlsx':
        # The established reader bounds ZIP expansion and worksheet dimensions.
        from pronto_report.adapters.source_tables import read_source_table
        for kind, role in [('RNA', 'rna_table'), ('CNV', 'cnv_table')]:
            try:
                table = read_source_table(path, kind=kind)
                if table_cache is not None:
                    table_cache[path] = table
                return role
            except (ValueError, KeyError):
                continue
    elif path.suffix.lower() in {'.png', '.pdf'}:
        if 'cnv_overview_plots' in name or 'cancan' in name:
            return 'cnv_plot'
        if 'sample_qc_plot' in name:
            return 'qc_plot'
        if 'domain_plot' in name:
            return 'other_plot'
    return ''


def _sample_bound(path, sample):
    if sample in path.parts[:-1]:
        return True
    return any(path.name == sample + suffix for suffix in (
        '_small_variant_table_forQC.tsv', '_small_variant_table.tsv',
        '_CNV_overview_plots.pdf', '_sample_QC_plot.png', '_sample_QC_plot.pdf'))


def _issues(files):
    return tuple(f'{role}: ' + ('mangler' if not files.get(role) else 'flere kandidater; velg én')
                 for role in REQUIRED_ROLES if len(files.get(role, ())) != 1) + tuple(
        f'{role}: flere kandidater; velg én' for role in ('cnv_table', 'rna_table')
        if len(files.get(role, ())) > 1)


def _linked_ids(path, sample, rows=None):
    rows = table_rows(path, header={'sample_type', 'sample_ID'}) if rows is None else rows
    dna = {row['sample_ID'] for row in rows if row['sample_type'].casefold() in {'dna_tumor', 'dna_tumour'}}
    if dna != {sample}:
        raise ValueError('Prøvelisten må være avgrenset til én eksakt DNA-prøve.')
    return {sample, *(row['sample_ID'] for row in rows if row['sample_type'].casefold() in {'rna_tumor', 'rna_tumour'})}


def discover_folders(folders, progress=None, cancel=None):
    folders = tuple(Path(folder).absolute() for folder in folders)
    if len(folders) != 5 or any(not folder.is_dir() for folder in folders):
        raise ValueError('Velg nøyaktig fem eksisterende mapper.')
    if any(a == b or a in b.parents or b in a.parents for i, a in enumerate(folders) for b in folders[i+1:]):
        raise ValueError('De fem mappene må være forskjellige og ikke ligge inne i hverandre.')
    for folder in folders:
        # Also reject a junction supplied as one of the five roots.
        for part in (folder, *folder.parents):
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Mapper med symbolske lenker støttes ikke.')
    folders = tuple(folder.resolve(strict=True) for folder in folders)
    if any(a == b or a in b.parents or b in a.parents for i, a in enumerate(folders) for b in folders[i+1:]):
        raise ValueError('De fem mappene må være forskjellige og ikke ligge inne i hverandre.')
    candidates = []
    row_cache, table_cache = {}, {}
    warnings = []
    visited = unknown_count = unreadable_count = omitted_count = 0
    for index, folder in enumerate(folders, 1):
        if progress:
            progress(f'Undersøker mappe {index} av 5 …')
        for directory, children, files in os.walk(folder, followlinks=False):
            check_cancel(cancel)
            current = Path(directory)
            children[:] = sorted(child for child in children if not (current / child).is_symlink()
                                  and not getattr((current / child).lstat(), 'st_file_attributes', 0) & 0x400)
            if len(current.relative_to(folder).parts) >= MAX_DEPTH:
                children[:] = []
                warnings.append('Undermapper dypere enn 30 nivåer ble utelatt.')
            for filename in sorted(files):
                check_cancel(cancel)
                visited += 1
                if visited > MAX_FILES:
                    raise ValueError('Mer enn 50 000 filer; velg mer avgrensede mapper.')
                path = current / filename
                if path.suffix.lower() not in {'.csv', '.tsv', '.txt', '.xlsx', '.png', '.pdf'}:
                    unknown_count += 1
                    if unknown_count <= 200:
                        candidates.append(SourceCandidate(path, 'unknown'))
                    continue
                try:
                    if not regular_file(path) or path.stat().st_size > MAX_BYTES:
                        omitted_count += 1
                        continue
                    role = _role(path, table_cache)
                    if role:
                        candidates.append(SourceCandidate(path, role))
                        if role in REQUIRED_ROLES:
                            row_cache[path] = table_rows(path)
                        elif role in {'cnv_table', 'rna_table'} and path not in table_cache:
                            from pronto_report.adapters.source_tables import read_source_table
                            table_cache[path] = read_source_table(path, kind='CNV' if role == 'cnv_table' else 'RNA')
                    else:
                        unknown_count += 1
                        if unknown_count <= 200:
                            candidates.append(SourceCandidate(path, 'unknown'))
                except Exception:
                    # A single corrupt candidate must not discard the rest of
                    # a run. Third-party workbook/XML parsers use varied errors.
                    unreadable_count += 1
    dna_ids, rna_ids = set(), set()
    for candidate in (c for c in candidates if c.role == 'sample_list'):
        for row in row_cache.get(candidate.path, ()):
            sample_type = row.get('sample_type', '').casefold()
            if sample_type in {'dna_tumor', 'dna_tumour'}:
                dna_ids.add(row.get('sample_ID', ''))
            elif sample_type in {'rna_tumor', 'rna_tumour'}:
                rna_ids.add(row.get('sample_ID', ''))
    identities = {}
    for candidate in candidates:
        if candidate.role == 'metadata':
            for row in row_cache.get(candidate.path, ()):
                if 'Create_report' in row and row['Create_report'].strip().upper() not in {'Y', 'YES', 'JA', 'TRUE', '1'}:
                    continue
                sample, run = row.get('Sample_id', ''), row.get('Sequencing_run_id', '')
                if sample in rna_ids and sample not in dna_ids:
                    continue
                if IDENTIFIER.fullmatch(sample) and IDENTIFIER.fullmatch(run):
                    identities.setdefault((sample, run), []).append(candidate.path)
    reports, assigned = [], set()
    for (sample, run), metadata in sorted(identities.items()):
        check_cancel(cancel)
        files = {'metadata': tuple(sorted(set(metadata)))}
        for role in ('summary', 'variants', 'sample_list', 'cnv_plot', 'qc_plot', 'other_plot'):
            matched = []
            for candidate in candidates:
                if candidate.role != role:
                    continue
                if role in REQUIRED_ROLES and candidate.path not in row_cache:
                    continue
                if role == 'summary':
                    suffix = '_variant_summary.tsv'
                    if candidate.path.name.endswith(suffix) and candidate.path.name[:-len(suffix)] != run:
                        continue
                    rows = row_cache.get(candidate.path, ())
                    matches = [row for row in rows if row.get('sample_id') in {sample, sample + '_P'}]
                    if len(matches) == 1:
                        matched.append(candidate.path)
                elif role == 'sample_list':
                    try:
                        _linked_ids(candidate.path, sample, row_cache.get(candidate.path, []))
                    except ValueError:
                        continue
                    matched.append(candidate.path)
                elif _sample_bound(candidate.path, sample):
                    matched.append(candidate.path)
            # Established preference: forQC over unfiltered small-variant tables.
            if role == 'variants' and any(p.name.endswith('_small_variant_table_forQC.tsv') for p in matched):
                matched = [p for p in matched if p.name.endswith('_small_variant_table_forQC.tsv')]
            if matched:
                files[role] = tuple(matched)
        linked = {sample}
        if len(files.get('sample_list', ())) == 1:
            try:
                linked = _linked_ids(files['sample_list'][0], sample, row_cache.get(files['sample_list'][0], []))
            except ValueError:
                pass
        # DNA/RNA QC files belong to the same report only through the scoped
        # sample list; a shared run directory alone is never a patient link.
        for role in ('qc_plot', 'other_plot'):
            matched = tuple(c.path for c in candidates if c.role == role
                            and any(_sample_bound(c.path, sample_id) for sample_id in linked))
            if matched:
                files[role] = matched
        for role, kind in [('cnv_table', 'CNV'), ('rna_table', 'RNA')]:
            for candidate in (c for c in candidates if c.role == role):
                table = table_cache.get(candidate.path)
                if table is None:
                    continue
                cols = [table['headers'].index(col) for col in SAMPLE_COLUMNS if col in table['headers']]
                allowed = linked if role == 'rna_table' else {sample}
                if cols and any(str(row['values'][col]) in allowed for row in table['rows'] for col in cols):
                    files[role] = (*files.get(role, ()), candidate.path)
        reports.append(ReportPlan(sample, run, files, _issues(files)))
        assigned.update(p for paths in files.values() for p in paths)
    if not reports:
        warnings.append('Fant ingen gyldige prøve- og kjøringsidentiteter i metadata.')
    if unknown_count:
        warnings.append(f'{unknown_count} filer har ukjent eller ustøttet type; de første 200 vises uten tilordning.')
    if unreadable_count:
        warnings.append(f'{unreadable_count} mulige kildefiler kunne ikke leses; kontroller filformatet.')
    if omitted_count:
        warnings.append(f'{omitted_count} mulige kildefiler ble utelatt på grunn av størrelse eller lenke.')
    signatures = {}
    for candidate in candidates:
        if candidate.role != 'unknown':
            info = candidate.path.stat()
            signatures[candidate.path] = (info.st_size, info.st_mtime_ns)
    return DiscoveryPlan(folders, tuple(reports), tuple(c for c in candidates if c.path not in assigned),
                         tuple(dict.fromkeys(warnings)), signatures)


def assign_source(plan, report_key, role, path):
    """Select a discovered candidate only; assignment is explicit user intent."""
    if role not in ROLES:
        raise ValueError('Ukjent filrolle.')
    known = {(c.path, c.role) for c in plan.unassigned}
    known.update((p, r) for report in plan.reports for r, paths in report.files.items() for p in paths)
    path = Path(path).absolute() if path is not None else None
    if path is not None and (path, role) not in known:
        raise ValueError('Velg en fil fra den kontrollerte mappekjøringen.')
    reports, found = [], False
    for report in plan.reports:
        if report.key == report_key:
            found = True
            files = dict(report.files)
            files[role] = (path,) if path is not None else ()
            report = replace(report, files=files, issues=_issues(files))
        reports.append(report)
    if not found:
        raise ValueError('Ukjent rapport.')
    # Keep all candidates available when a different selection is made later.
    all_candidates = {(c.path, c.role): c for c in plan.unassigned}
    all_candidates.update({(p, r): SourceCandidate(p, r) for report in plan.reports for r, paths in report.files.items() for p in paths})
    used = {p for report in reports for paths in report.files.values() for p in paths}
    return replace(plan, reports=tuple(reports), unassigned=tuple(c for (p, _), c in all_candidates.items() if p not in used))
