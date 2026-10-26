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
from .naming import (classify_run_directory, conflicts_sample_name, file_matches,
                     nearest_run_directory, normalise_role, plot_role, summary_run_id, variant_excluded)
from pronto_report.adapters.text_tables import read_text_rows

MAX_FILES = 50000
MAX_DEPTH = 30
MAX_BYTES = 25 * 1024 * 1024
MAX_ROWS = 10000
IDENTIFIER = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')
SAMPLE_COLUMNS = ('Sample_ID', 'Sample_id', 'sample_id', 'sample_ID')
POSITIVE_FLAGS = {'Y', 'YES', 'JA', 'TRUE', '1'}
NEGATIVE_FLAGS = {'N', 'NO', 'NEI', 'FALSE', '0'}


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
    rows = read_text_rows(path, max_bytes=MAX_BYTES, max_rows=MAX_ROWS)
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
        if columns & {'Sample_id', 'sample_id', 'sample_type', 'sample_ID', 'Gene_symbol', 'Gene_Symbol', 'Provisional_Event_Type', 'chr'}:
            return columns
    return set()


def _role(path, table_cache=None):
    if path.suffix.lower() in {'.tsv', '.txt', '.csv'}:
        if file_matches(path.name, path.parent.name, 'linkage'):
            return 'linkage'
        if normalise_role(path.parent.name) == 'extrafiles' and file_matches(path.name, path.parent.parent.name, 'supporting'):
            return 'supporting'
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
        if {'chr', 'gene.name', 'total.cn'} <= headers:
            return 'cancan_table'
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
        return plot_role(path.name)
    return ''


def _sample_bound(path, sample):
    if sample in path.parts[:-1]:
        return True
    return any(path.name == sample + suffix for suffix in (
        '_small_variant_table_forQC.tsv', '_small_variant_table.tsv',
        '_CNV_overview_plots.pdf', '_sample_QC_plot.png', '_sample_QC_plot.pdf'))


def _issues(files, profile='legacy'):
    if profile == 'tsoppi-run-v1':
        issues = [f'{role}: ' + ('mangler' if not files.get(role) else 'flere kandidater; velg én')
                  for role in REQUIRED_ROLES[:3] if len(files.get(role, ())) != 1]
        if not files.get('sample_list') and not files.get('linkage'):
            issues.append('DNA/RNA-kobling: mangler')
        issues.extend(f'{role}: flere kandidater; velg én' for role in ('sample_list', 'cnv_table', 'cancan_table', 'rna_table')
                      if len(files.get(role, ())) > 1)
        return tuple(issues)
    return tuple(f'{role}: ' + ('mangler' if not files.get(role) else 'flere kandidater; velg én')
                 for role in REQUIRED_ROLES if len(files.get(role, ())) != 1) + tuple(
        f'{role}: flere kandidater; velg én' for role in ('cnv_table', 'rna_table')
        if len(files.get(role, ())) > 1)


def _linked_ids(path, sample, rows=None):
    from .linkage import sample_list_links
    rows = table_rows(path, header={'sample_type', 'sample_ID'}) if rows is None else rows
    return sample_list_links(sample, rows)


def discover_folders(folders, progress=None, cancel=None, *, report_version='auto', cnv_source='merged', cnv_solution='main'):
    if report_version not in {'auto', 'new', 'legacy', 'raw'} or cnv_source not in {'merged', 'cancan'} or cnv_solution not in {'main', 'alt01', 'alt02'}:
        raise ValueError('Ukjent rapportversjon eller CNV-valg.')
    folders = tuple(Path(folder).absolute() for folder in folders)
    if not 1 <= len(folders) <= 5 or any(not folder.is_dir() for folder in folders):
        raise ValueError('Velg én til fem eksisterende mapper.')
    if any(a == b or a in b.parents or b in a.parents for i, a in enumerate(folders) for b in folders[i+1:]):
        raise ValueError('Mappene må være forskjellige og ikke ligge inne i hverandre.')
    for folder in folders:
        # Also reject a junction supplied as one of the five roots.
        for part in (folder, *folder.parents):
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Mapper med symbolske lenker støttes ikke.')
    folders = tuple(folder.resolve(strict=True) for folder in folders)
    if any(a == b or a in b.parents or b in a.parents for i, a in enumerate(folders) for b in folders[i+1:]):
        raise ValueError('Mappene må være forskjellige og ikke ligge inne i hverandre.')
    candidates = []
    row_cache, table_cache = {}, {}
    warnings, locations = [], {}
    visited = unknown_count = unreadable_count = omitted_count = 0
    for index, folder in enumerate(folders, 1):
        if progress:
            progress(f'Undersøker mappe {index} av {len(folders)} …')
        for directory, children, files in os.walk(folder, followlinks=False):
            check_cancel(cancel)
            current = Path(directory)
            family = classify_run_directory(current.name)
            if family:
                run, version = family
                locations.setdefault(run, {}).setdefault(version, []).append(current)
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
                        if role in REQUIRED_ROLES or role == 'cancan_table':
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
    actual_runs = {run: roots for run, roots in locations.items() if any(
        candidate.role == 'metadata' and candidate.path.parent in roots.get('raw', ())
        and any(row.get('Sequencing_run_id') == run for row in row_cache.get(candidate.path, ()))
        for candidate in candidates)}
    if actual_runs:
        return _actual_plan(folders, candidates, row_cache, table_cache, warnings, actual_runs,
                            report_version, cnv_source, cnv_solution, cancel,
                            unknown_count, unreadable_count, omitted_count)
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


def _exact_row_identity(rows, allowed, require_column=False):
    declared = False
    for row in rows:
        ids = {str(row[column]) for column in SAMPLE_COLUMNS if row.get(column) not in (None, '')}
        if ids and not ids <= allowed or require_column and not ids:
            return False
        declared = declared or bool(ids)
    return declared or not require_column


def _source_table_identity(table, allowed, require_column=False):
    columns = [table['headers'].index(column) for column in SAMPLE_COLUMNS if column in table['headers']]
    if not columns or not table['rows']:
        return not require_column
    return any(bool(ids := {str(row['values'][column]) for column in columns
                            if row['values'][column] not in (None, '')}) and ids <= allowed
               for row in table['rows'])


def _row_identity_issues(sample, files, linked, row_cache, table_cache):
    issues = []
    if any(not _exact_row_identity(row_cache[path], {sample}) for path in files.get('variants', ())):
        issues.append('variants: tabellen inneholder en annen prøve-ID')
    for role, allowed in (('cnv_table', {sample}), ('rna_table', linked - {sample})):
        if any(not _source_table_identity(table_cache[path], allowed) for path in files.get(role, ())):
            issues.append(role + ': tabellen mangler samstemt prøve-ID')
    return tuple(issues)


def _actual_plan(folders, candidates, row_cache, table_cache, warnings, runs,
                 report_version, cnv_source, cnv_solution, cancel,
                 unknown_count, unreadable_count, omitted_count):
    from .linkage import resolve_links
    reports, assigned = [], set()
    for run, roots in sorted(runs.items()):
        version = next((value for value in ('new', 'legacy', 'raw') if roots.get(value)), 'raw') if report_version == 'auto' else report_version
        metadata = [c.path for c in candidates if c.role == 'metadata'
                    and c.path.parent in roots.get('raw', ())]
        explicit_rna = set()
        for candidate in candidates:
            dna = candidate.path.parent.name
            if candidate.path.parent.parent not in roots.get('raw', ()):
                continue
            if not ((candidate.role == 'linkage' and file_matches(candidate.path.name, dna, 'linkage'))
                    or (candidate.role == 'variants' and file_matches(candidate.path.name, dna, 'raw_variants'))
                    or candidate.role == 'sample_list'):
                continue
            try:
                role = 'sample_list' if candidate.role == 'sample_list' else 'linkage'
                explicit_rna.update(resolve_links(dna, {role: (candidate.path,)}) - {dna})
            except ValueError:
                # A corrupt claim blocks its DNA report below, not other samples.
                continue
        identities = {}
        for path in metadata:
            for row in row_cache.get(path, ()):
                sample = row.get('Sample_id', '')
                # Scope the historical metadata to this run before considering
                # identities. The layout contains DNA directories, not RNA reports.
                if row.get('Sequencing_run_id') != run or not IDENTIFIER.fullmatch(sample):
                    continue
                if sample in explicit_rna or re.search(r'(?:^|[-_])R\d+(?:[-_]|$)', sample, re.IGNORECASE):
                    continue
                if not any((root / sample).is_dir() for root in roots.get('raw', ())):
                    continue
                identities.setdefault(sample, []).append((path, row.get('Create_report', '').strip()))
        for sample, rows in sorted(identities.items()):
            check_cancel(cancel)
            files = {'metadata': tuple(sorted({path for path, _ in rows}))}

            def matches(role, versions=('raw',), name_role=None, sample_id=None, nested=False):
                selected_roots = [root for value in versions for root in roots.get(value, ())]
                return tuple(sorted(c.path for c in candidates if c.role == role
                    and (name_role is None or file_matches(c.path.name, sample_id or sample, name_role, solution=cnv_solution))
                    and (boundary := nearest_run_directory(c.path)) is not None
                    and boundary[1] == run and boundary[2] in versions
                    and any((c.path.is_relative_to(root / sample) if nested else c.path.parent == root / sample)
                            for root in selected_roots)
                    and (role not in REQUIRED_ROLES and role != 'cancan_table' or c.path in row_cache)
                    and (role not in {'cnv_table', 'rna_table'} or c.path in table_cache)))

            summary = tuple(sorted(c.path for c in candidates if c.role == 'summary'
                and c.path in row_cache and c.path.parent in roots.get('raw', ())
                and summary_run_id(c.path.name) in {None, run}
                and sum(row.get('sample_id') in {sample, sample + '_P'} for row in row_cache[c.path]) == 1))
            if summary:
                files['summary'] = summary
            variants = matches('variants', (version,), 'raw_variants' if version == 'raw' else 'qc_variants')
            if not variants:
                # Renamed primary tables need exact row identity. A known
                # clinical subset or a foreign ID is never a fallback.
                variants = tuple(path for path in matches('variants', (version,))
                    if not variant_excluded(path.name)
                    and not conflicts_sample_name(path.name, sample, 'variants')
                    and not file_matches(path.name, sample, 'raw_variants')
                    and _exact_row_identity(row_cache[path], {sample}, require_column=True))
            if variants:
                files['variants'] = variants
            lists = matches('sample_list', ('raw', version) if version != 'raw' else ('raw',))
            if lists:
                files['sample_list'] = tuple(dict.fromkeys(lists))
            linkage = (*matches('linkage', name_role='linkage'),
                       *matches('variants', name_role='raw_variants'))
            if linkage:
                files['linkage'] = tuple(dict.fromkeys(linkage))
            link_issues, linked = (), {sample}
            try:
                linked = resolve_links(sample, files)
            except ValueError:
                link_issues = ('DNA/RNA-kobling: mangler eller er ikke samstemt',)
            if cnv_source == 'merged':
                # This versioned profile explicitly defines FC before fraction.
                for priority in ('FC', 'fraction'):
                    cnv = matches('cnv_table', name_role='cnv_fc' if priority == 'FC' else 'cnv_fraction')
                    if cnv:
                        files['cnv_table'] = cnv
                        break
                if not files.get('cnv_table'):
                    cnv = tuple(path for path in matches('cnv_table')
                                if not conflicts_sample_name(path.name, sample, 'cnv_table'))
                    if cnv:
                        files['cnv_table'] = cnv
                plots = matches('cnv_plot', (version,), 'cnv_plot')
                if not plots and version != 'raw':
                    plots = matches('cnv_plot', name_role='cnv_plot')
            else:
                cancan = matches('cancan_table', ('cnv',), 'cancan_table', nested=True)
                if cancan:
                    files['cancan_table'] = cancan
                plots = matches('cnv_plot', ('cnv',), 'cancan_plot', nested=True)
            if plots:
                files['cnv_plot'] = plots
            for role in ('signature_plot',):
                paths = matches(role, name_role=role)
                if paths:
                    files[role] = paths
            for linked_id in sorted(linked):
                for suffix in ('.png', '.pdf'):
                    paths = tuple(path for path in matches('qc_plot', name_role='qc_plot', sample_id=linked_id)
                                  if path.suffix.casefold() == suffix)
                    if paths:
                        files['qc_plot'] = (*files.get('qc_plot', ()), *paths)
                        break
                if linked_id != sample:
                    for role in ('rna_table', 'rna_profile_plot'):
                        paths = matches(role, name_role=role, sample_id=linked_id)
                        if role == 'rna_table' and not paths:
                            paths = tuple(path for path in matches(role)
                                if not conflicts_sample_name(path.name, linked_id, role)
                                and _source_table_identity(table_cache[path], {linked_id}, require_column=True))
                        if paths:
                            files[role] = (*files.get(role, ()), *paths)
            supporting = matches('supporting', (version,), nested=True)
            supporting = tuple(path for path in supporting if normalise_role(path.parent.name) == 'extrafiles'
                               and file_matches(path.name, sample, 'supporting'))
            if supporting:
                files['supporting'] = supporting
            flags = {flag.upper() for _, flag in rows}
            flag = rows[0][1] if len(flags) == 1 else ' | '.join(sorted(flags))
            issues = _issues(files, 'tsoppi-run-v1') + link_issues
            issues += _row_identity_issues(sample, files, linked, row_cache, table_cache)
            if len(rows) != 1:
                issues += ('metadata: prøve og kjøring må ha én entydig rad',)
            current_metadata = [row for path in files['metadata'] for row in row_cache.get(path, ())
                                if row.get('Sample_id') == sample and row.get('Sequencing_run_id') == run]
            if len(current_metadata) == 1 and current_metadata[0].get('Study_id', '').strip() in {'', '-', '.', 'NA'}:
                issues += ('metadata: Study_id mangler',)
            if len(flags) != 1 or not flags <= POSITIVE_FLAGS | NEGATIVE_FLAGS | {'-', ''}:
                issues += ('Create_report: ukjent eller motstridende verdi',)
            if cnv_source == 'cancan' and not files.get('cancan_table'):
                issues += ('cancan_table: mangler valgt løsning',)
            reports.append(ReportPlan(sample, run, files, issues, profile='tsoppi-run-v1',
                metadata_flag=flag, selected=flag.upper() in POSITIVE_FLAGS,
                cnv_source=cnv_source, cnv_solution=cnv_solution, report_version=version))
            assigned.update(path for paths in files.values() for path in paths)
    if not reports:
        warnings.append('Fant ingen DNA-prøver for de valgte kjøringene i metadata.')
    for count, message in ((unknown_count, 'filer har ukjent eller ustøttet type'),
                           (unreadable_count, 'mulige kildefiler kunne ikke leses'),
                           (omitted_count, 'mulige kildefiler ble utelatt på grunn av størrelse eller lenke')):
        if count:
            warnings.append(f'{count} {message}.')
    signatures = {}
    for candidate in candidates:
        if candidate.role != 'unknown':
            info = candidate.path.stat()
            signatures[candidate.path] = (info.st_size, info.st_mtime_ns)
    return DiscoveryPlan(folders, tuple(reports), tuple(c for c in candidates if c.path not in assigned),
                         tuple(dict.fromkeys(warnings)), signatures, profile='tsoppi-run-v1',
                         run_ids=tuple(sorted(runs)), report_version=report_version,
                         cnv_source=cnv_source, cnv_solution=cnv_solution)


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
            if role == 'metadata':
                report = replace(report, study_id_override='')
            files = dict(report.files)
            files[role] = (path,) if path is not None else ()
            issues = _issues(files, report.profile)
            if report.profile == 'tsoppi-run-v1':
                from .linkage import resolve_links
                linked = {report.sample_id}
                try:
                    linked = resolve_links(report.sample_id, files)
                except ValueError:
                    issues += ('DNA/RNA-kobling: mangler eller er ikke samstemt',)
                try:
                    metadata_paths = files.get('metadata', ())
                    if len(metadata_paths) == 1:
                        metadata = table_rows(metadata_paths[0], header={'Sample_id', 'Sequencing_run_id', 'Study_id'})
                        current = [row for row in metadata if row.get('Sample_id') == report.sample_id
                                   and row.get('Sequencing_run_id') == report.run_id]
                        flags = {row.get('Create_report', '').strip().upper() for row in current}
                        flag = next(iter(flags)) if len(flags) == 1 else ' | '.join(sorted(flags))
                        selected, confirmed = report.selected, report.selection_confirmed
                        if len(current) != 1 or flag not in POSITIVE_FLAGS | {'-', ''}:
                            selected = confirmed = False
                        elif role == 'metadata' and not confirmed:
                            selected = flag in POSITIVE_FLAGS
                        report = replace(report, metadata_flag=flag, selected=selected, selection_confirmed=confirmed)
                        if len(current) != 1:
                            issues += ('metadata: prøve og kjøring må ha én entydig rad',)
                        elif not report.study_id_override and current[0].get('Study_id', '').strip() in {'', '-', '.', 'NA'}:
                            issues += ('metadata: Study_id mangler',)
                    row_cache = {source: table_rows(source) for source in files.get('variants', ())}
                    from pronto_report.adapters.source_tables import read_source_table
                    table_cache = {source: read_source_table(source, kind=kind)
                                   for role, kind in (('cnv_table', 'CNV'), ('rna_table', 'RNA'))
                                   for source in files.get(role, ())}
                    issues += _row_identity_issues(report.sample_id, files, linked, row_cache, table_cache)
                except (OSError, ValueError):
                    issues += ('Kildetabell: format eller prøve-ID må kontrolleres',)
                if report.cnv_source == 'cancan' and not files.get('cancan_table'):
                    issues += ('cancan_table: mangler valgt løsning',)
                if report.metadata_flag.strip().upper() not in POSITIVE_FLAGS | NEGATIVE_FLAGS | {'-', ''}:
                    issues += ('Create_report: ukjent eller motstridende verdi',)
            report = replace(report, files=files, issues=issues)
        reports.append(report)
    if not found:
        raise ValueError('Ukjent rapport.')
    # Keep all candidates available when a different selection is made later.
    all_candidates = {(c.path, c.role): c for c in plan.unassigned}
    all_candidates.update({(p, r): SourceCandidate(p, r) for report in plan.reports for r, paths in report.files.items() for p in paths})
    used = {p for report in reports for paths in report.files.values() for p in paths}
    return replace(plan, reports=tuple(reports), unassigned=tuple(c for (p, _), c in all_candidates.items() if p not in used))


def set_report_selected(plan, report_key, selected):
    """Record an explicit sample selection without overriding negative metadata."""
    if not isinstance(selected, bool):
        raise ValueError('Prøvevalget må være av eller på.')
    reports, found = [], False
    for report in plan.reports:
        if report.key == report_key:
            found = True
            flag = report.metadata_flag.strip().upper()
            if selected and report.profile == 'tsoppi-run-v1' and flag not in POSITIVE_FLAGS | {'-', ''}:
                raise ValueError('Prøven er sperret for rapport i metadata.')
            report = replace(report, selected=selected, selection_confirmed=selected)
        reports.append(report)
    if not found:
        raise ValueError('Ukjent rapport.')
    return replace(plan, reports=tuple(reports))
