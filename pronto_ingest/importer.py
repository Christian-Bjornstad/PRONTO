"""Archive bounded inputs and atomically publish one validated report at a time."""
from __future__ import annotations

from datetime import datetime, timezone
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid
from io import BytesIO
import warnings

from .contracts import (ImportCancelled, ImportItemResult, ImportResult, REQUIRED_ROLES,
                        ROLES, check_cancel)
from .discovery import MAX_BYTES, SAMPLE_COLUMNS, IDENTIFIER, regular_file, table_rows
from .linkage import resolve_links
from .naming import classify_run_directory, declared_file_sample, file_matches, summary_run_id

MAX_ASSET_BYTES = 64 * 1024 * 1024
MAX_ASSETS = 100
PLOT_ROLES = ('cnv_plot', 'qc_plot', 'other_plot', 'signature_plot', 'rna_profile_plot')
PLOT_DESCRIPTIONS = {'cnv_plot': 'CNV', 'qc_plot': 'QC', 'other_plot': 'RNA / domene',
                     'signature_plot': 'Mutasjonssignatur', 'rna_profile_plot': 'RNA-profil'}


class ImportProblem(ValueError):
    """A fixed safe message, containing no private source paths or cell content."""


def _validate_plot(content, media):
    from pronto_report.renderers.assets import _MAX_ATTACHMENT_BYTES, _pdf_pages
    if len(content) > _MAX_ATTACHMENT_BYTES:
        raise ImportProblem('Et plott overskrider rapportgrensen på 12 MiB.')
    if media == 'application/pdf':
        if not shutil.which('pdfinfo') or not shutil.which('pdftoppm'):
            raise ImportProblem('PDF-verktøy mangler: installer Poppler (pdfinfo og pdftoppm) før import av PDF-plott.')
        try:
            _pdf_pages(content)
        except Exception:
            raise ImportProblem('Et PDF-plott kunne ikke leses eller overskrider sidegrensen.') from None
    else:
        from PIL import Image
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as image:
                    if image.format != 'PNG' or image.width * image.height > 64_000_000:
                        raise ValueError('Unsupported dimensions')
                    image.verify()
                with Image.open(BytesIO(content)) as image:
                    image.load()
        except Exception:
            raise ImportProblem('Et PNG-plott er skadet eller har for stor oppløsning.') from None


def _filename_identity(path, role, report_plan, linked):
    if report_plan.profile == 'tsoppi-run-v1':
        declared_sample = declared_file_sample(path.name, role, solution=report_plan.cnv_solution)
        allowed = linked if role == 'qc_plot' else linked - {report_plan.sample_id} if role in {'rna_table', 'rna_profile_plot'} else {report_plan.sample_id}
        if declared_sample is not None and declared_sample not in allowed:
            raise ImportProblem('Kildefilens prøve-ID avviker fra valgt prøve.')
    declared_run = summary_run_id(path.name) if role == 'summary' else None
    if declared_run and declared_run != report_plan.run_id:
        raise ImportProblem('Sammendragsfilens kjørings-ID avviker fra valgt kjøring.')
    if report_plan.profile == 'legacy' and role == 'summary' and path.name.endswith('_variant_summary.tsv'):
        if path.name[:-len('_variant_summary.tsv')] != report_plan.run_id:
            raise ImportProblem('Sammendragsfilens kjørings-ID avviker fra valgt kjøring.')
    suffixes = {'variants': ('_small_variant_table_forQC.tsv', '_small_variant_table.tsv'),
                'cnv_plot': ('_CNV_overview_plots.pdf',),
                'qc_plot': ('_sample_QC_plot.png', '_sample_QC_plot.pdf'),
                'signature_plot': ('_joint_mutational_signature.pdf',),
                'rna_profile_plot': ('_RNA_profiles.pdf',)}
    for suffix in suffixes.get(role, ()):
        allowed = linked if role in {'qc_plot', 'rna_profile_plot'} else {report_plan.sample_id}
        if path.name.endswith(suffix) and path.name[:-len(suffix)] not in allowed:
            raise ImportProblem('Kildefilens prøve-ID avviker fra valgt prøve.')
    if report_plan.profile == 'tsoppi-run-v1' and role in {'cnv_table', 'cancan_table'}:
        if report_plan.sample_id not in path.parts:
            raise ImportProblem('CNV-kilden mangler eksakt DNA-prøve i mappe og filnavn.')
        if role == 'cancan_table' and not file_matches(path.name, report_plan.sample_id, 'cancan_table', solution=report_plan.cnv_solution):
            raise ImportProblem('Cancan-tabellen avviker fra valgt løsning.')
    if (report_plan.profile == 'tsoppi-run-v1' and role == 'cnv_plot'
            and report_plan.cnv_source == 'cancan'
            and not file_matches(path.name, report_plan.sample_id, 'cancan_plot', solution=report_plan.cnv_solution)):
        raise ImportProblem('Cancan-plottet avviker fra valgt prøve og løsning.')


def _validate_run_scope(path, role, report_plan):
    """A manual choice must retain the versioned profile's run and DNA scope."""
    if report_plan.profile != 'tsoppi-run-v1':
        return
    version = report_plan.report_version
    versions = {
        'metadata': ('raw',), 'summary': ('raw',), 'variants': (version,),
        'sample_list': ('raw', version), 'linkage': ('raw',),
        'cnv_table': ('raw',), 'cancan_table': ('cnv',), 'qc_plot': ('raw',),
        'signature_plot': ('raw',), 'rna_profile_plot': ('raw',), 'rna_table': ('raw',),
        'supporting': (version,), 'other_plot': ('raw', version),
        'cnv_plot': ('cnv',) if report_plan.cnv_source == 'cancan' else ('raw', version),
    }
    for root in path.parents:
        family = classify_run_directory(root.name)
        if family is None:
            continue
        if family[0] != report_plan.run_id or family[1] not in versions[role]:
            break
        if role in {'metadata', 'summary'} and path.parent == root:
            return
        if role not in {'metadata', 'summary'} and path.is_relative_to(root / report_plan.sample_id):
            return
        break
    raise ImportProblem('Kildefilen avviker fra valgt kjøring, rapportversjon eller DNA-prøvemappe.')


def _hash(path, cancel=None):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            check_cancel(cancel)
            digest.update(chunk)
    return digest.hexdigest()


def _copy(source, target, cancel=None):
    if not regular_file(source) or source.stat().st_size > MAX_BYTES:
        raise ImportProblem('Kilden er utilgjengelig, for stor eller en lenke.')
    before = source.stat()
    expected = _hash(source, cancel)
    with source.open('rb') as original, target.open('xb') as archive:
        os.chmod(target, 0o600)
        size = 0
        while chunk := original.read(1024 * 1024):
            check_cancel(cancel)
            size += len(chunk)
            if size > MAX_BYTES:
                raise ImportProblem('Kildens størrelse ble endret under innlesing.')
            archive.write(chunk)
        archive.flush()
        os.fsync(archive.fileno())
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ImportProblem('Kilden ble endret under innlesing. Kjør kontroll på nytt.')
    if expected != _hash(target, cancel) or expected != _hash(source, cancel):
        raise ImportProblem('Kontrollsummen ble endret under innlesing.')
    return expected, size


def _validate_sources(report_plan, sources):
    if any(len(sources.get(role, ())) > 1 for role in ('metadata', 'summary', 'variants', 'sample_list', 'cnv_table', 'cancan_table', 'rna_table')):
        raise ImportProblem('Importen har flere konkurrerende tabeller for samme filrolle.')
    if report_plan.profile == 'tsoppi-run-v1' and (
            report_plan.cnv_source == 'cancan' and sources.get('cnv_table')
            or report_plan.cnv_source == 'merged' and sources.get('cancan_table')):
        raise ImportProblem('CNV-tabellen avviker fra valgt kilde.')
    metadata = table_rows(sources['metadata'][0], header={'Sample_id', 'Sequencing_run_id', 'Study_id'})
    exact = [r for r in metadata if r.get('Sample_id') == report_plan.sample_id
             and r.get('Sequencing_run_id') == report_plan.run_id]
    if len(exact) != 1:
        raise ImportProblem('Metadata har manglende eller flere rader for prøve og kjøring.')
    _validate_selection(report_plan, exact[0])
    # The legacy adapter picks by sample only. Refuse cross-run ambiguity here.
    if report_plan.profile != 'tsoppi-run-v1' and len([r for r in metadata if r.get('Sample_id') == report_plan.sample_id]) != 1:
        raise ImportProblem('Metadata inneholder samme prøve i flere kjøringer.')
    summary = table_rows(sources['summary'][0], header={'sample_id', 'TMB', 'MSI'})
    if len([r for r in summary if r['sample_id'] in {report_plan.sample_id, report_plan.sample_id + '_P'}]) != 1:
        raise ImportProblem('Analysesammendraget identifiserer ikke prøven entydig.')
    try:
        variants = table_rows(sources['variants'][0], header={'Gene_symbol', 'Genomic_location', 'DNA_change', 'Change_summary'})
    except ValueError:
        raise ImportProblem('Varianttabellen må inneholde Gene_symbol, Genomic_location, DNA_change og Change_summary.') from None
    for row in variants:
        ids = {str(row[c]) for c in SAMPLE_COLUMNS if row.get(c)}
        if ids and ids != {report_plan.sample_id}:
            raise ImportProblem('Varianttabellen inneholder en annen prøve-ID.')
    return _links(report_plan, sources)


def _validate_selection(report_plan, metadata):
    flag = metadata.get('Create_report', '').strip().upper()
    if flag in {'N', 'NO', 'NEI', 'FALSE', '0'}:
        raise ImportProblem('Metadata angir at rapport ikke skal opprettes for denne prøven.')
    if flag in {'Y', 'YES', 'JA', 'TRUE', '1'} or 'Create_report' not in metadata and report_plan.profile == 'legacy':
        return
    if (report_plan.profile == 'tsoppi-run-v1' and flag in {'', '-', '.'}
            and report_plan.selected and report_plan.selection_confirmed):
        return
    raise ImportProblem('Prøven må velges uttrykkelig når Create_report ikke er satt.')


def _links(report_plan, sources):
    try:
        return resolve_links(report_plan.sample_id, sources)
    except ValueError:
        raise ImportProblem('DNA/RNA-koblingen mangler, har ukjent format eller er ikke samstemt.') from None


def _canonical_sources(report_plan, sources, canonical, linked):
    """Derive an adapter view while keeping every original archived byte intact."""
    from pronto_report.adapters.pronto_output import _reference_build
    sample_dir = canonical / report_plan.sample_id
    sample_dir.mkdir(parents=True)
    metadata = table_rows(sources['metadata'][0], header={'Sample_id', 'Sequencing_run_id', 'Study_id'})
    row = next(r for r in metadata if r.get('Sample_id') == report_plan.sample_id
               and r.get('Sequencing_run_id') == report_plan.run_id)
    with (canonical / 'InPreD_PRONTO_metadata.txt').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row), delimiter='\t')
        writer.writeheader()
        writer.writerow(row)
    _canonical_table(sources['summary'][0], canonical / 'run_variant_summary.tsv')
    variant = sources['variants'][0]
    builds = {_reference_build(path) for path in dict.fromkeys((*sources.get('variants', ()), *sources.get('linkage', ())))}
    builds.discard(None)
    if len(builds) > 1:
        raise ImportProblem('Variantkildene angir ulike referansegenomer.')
    target = sample_dir / f'{report_plan.sample_id}_small_variant_table_forQC.tsv'
    reference_comment = (f'# Reference declared by archived source: /{next(iter(builds))}/\n'
                         if _reference_build(variant) is None and builds else '')
    _canonical_table(variant, target, extra_comment=reference_comment)
    if sources.get('sample_list'):
        shutil.copyfile(sources['sample_list'][0], sample_dir / 'sample_list.tsv')
    else:
        with (sample_dir / 'sample_list.tsv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream, delimiter='\t')
            writer.writerow(['sample_type', 'sample_ID'])
            writer.writerow(['dna_tumor', report_plan.sample_id])
            writer.writerows(['rna_tumor', sample] for sample in sorted(linked - {report_plan.sample_id}))


def _canonical_table(source, target, *, extra_comment=''):
    """Normalise the adapter delimiter only; archived source bytes are preserved."""
    rows = table_rows(source)
    if not rows:
        raise ImportProblem('Den påkrevde kildetabellen mangler datarader.')
    with target.open('w', encoding='utf-8', newline='') as output:
        output.write(extra_comment)
        with source.open(encoding='utf-8-sig') as original:
            for line in original:
                if not line.startswith('#'):
                    break
                output.write(line)
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), delimiter='\t')
        writer.writeheader()
        writer.writerows(rows)


def _build_report(report_plan, sources, archive, hashes, original_names, cancel=None):
    from pronto_report.adapters.pronto_output import adapt_pronto_output
    from pronto_report.adapters.source_tables import read_source_table
    from pronto_report.serialization import serialize_report_data
    from pronto_report.validation import validate_report_data
    linked = _validate_sources(report_plan, sources)
    canonical = archive / 'canonical'
    _canonical_sources(report_plan, sources, canonical, linked)
    now = datetime.now(timezone.utc).isoformat()
    report = adapt_pronto_output(canonical, sample_id=report_plan.sample_id,
                                generated_at=now, generator_version='desktop-1')
    document = json.loads(serialize_report_data(report))
    variant_source = sources['variants'][0]
    variant_table = read_source_table(variant_source, kind='VARIANTS')
    if len(variant_table['rows']) != len(document['variants']):
        raise ImportProblem('Varianttabellen avviker fra rapportens variantgrunnlag.')
    variant_table['fileName'] = original_names[variant_source]
    for row, variant in zip(variant_table['rows'], document['variants']):
        row['findingId'], row['occurrenceId'] = variant['variantId'], variant['occurrenceId']
    document['sourceTables'] = [variant_table]
    # Hash provenance points to the archived original bytes, using opaque relative
    # names. No workstation paths are exposed through report JSON or HTML.
    document['provenance']['sourceFiles'] = [
        {'name': p.name, 'sha256': hashes[p][0], 'sizeBytes': hashes[p][1]}
        for paths in sources.values() for p in paths]
    if report_plan.profile == 'tsoppi-run-v1':
        document['diagnostics'].append({'code': 'IMPORT_CONFIGURATION', 'severity': 'INFO', 'path': 'provenance',
            'message': f'Importprofil: tsoppi-run-v1; rapportversjon: {report_plan.report_version}; CNV: {report_plan.cnv_source}; løsning: {report_plan.cnv_solution}.'})
        if report_plan.selection_confirmed:
            document['diagnostics'].append({'code': 'EXPLICIT_REPORT_SELECTION', 'severity': 'INFO', 'path': 'provenance',
                'message': 'Prøven ble uttrykkelig valgt for import. Opprinnelig Create_report er bevart i kildearkivet.'})
    for role, kind in [('cnv_table', 'CNV'), ('cancan_table', 'CNV'), ('rna_table', 'RNA')]:
        for path in sources.get(role, ()):
            check_cancel(cancel)
            if role == 'cancan_table':
                from pronto_report.adapters.cancan import read_cancan_table
                table = read_cancan_table(path, sample_id=report_plan.sample_id)
            else:
                table = read_source_table(path, kind=kind)
            table['fileName'] = original_names[path]
            columns = [table['headers'].index(c) for c in SAMPLE_COLUMNS if c in table['headers']]
            if columns:
                allowed = linked - {report_plan.sample_id} if role == 'rna_table' else {report_plan.sample_id}
                def matches_identity(row):
                    identities = {str(row['values'][c]) for c in columns if row['values'][c] not in (None, '')}
                    return bool(identities) and identities <= allowed
                table['rows'] = [row for row in table['rows'] if matches_identity(row)]
                if not table['rows']:
                    raise ImportProblem('Tilleggstabellen mangler eksakt kobling til denne prøven.')
            document['sourceTables'].append(table)
    assets = {}
    for role in PLOT_ROLES:
        for path in sources.get(role, ()):
            check_cancel(cancel)
            content = path.read_bytes()
            if path.suffix.lower() == '.png':
                if not content.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ImportProblem('En plottfil har ugyldig PNG-format.')
                media = 'image/png'
            elif path.suffix.lower() == '.pdf' and content.startswith(b'%PDF-'):
                media = 'application/pdf'
            else:
                raise ImportProblem('En plottfil har ukjent format.')
            _validate_plot(content, media)
            asset_id = 'import-' + hashlib.sha256((role + hashes[path][0]).encode()).hexdigest()[:24]
            if asset_id in assets:
                continue
            assets[asset_id] = content
            document['attachments'].append({'assetId': asset_id, 'name': original_names[path],
                'sha256': hashes[path][0], 'mediaType': media,
                'description': PLOT_DESCRIPTIONS[role]})
    return validate_report_data(document), assets


def _review(report, actor):
    from pronto_report.validation import validate_review_state
    from pronto_report.migration import migrate_review_state_to_v3
    now = datetime.now(timezone.utc).isoformat()
    return migrate_review_state_to_v3(validate_review_state({
        'schemaVersion': '2.0', 'reportId': report.report_id, 'revision': 1, 'status': 'DRAFT',
        'reviewer': {'reviewerId': str(actor.pk)}, 'createdAt': now, 'updatedAt': now,
        'variantReviews': [], 'runQcAssessment': {'status': 'NOT_REVIEWED'}, 'valueCorrections': [],
        'notes': {'summary': '', 'biomarkerContext': '', 'additional': '', 'importedLegacyNote': ''}}, report=report))


def _import_one(plan, report_plan, actor, raw_root, batch, progress, cancel):
    from django.db import transaction
    from pronto_report.serialization import serialize_report_data, serialize_review_state
    from pronto_web.reports.models import (ImportItem, ImportSource, ReportRecord,
                                           ReportGrant, ReportAsset, ReviewRevision)
    archive = raw_root / uuid.uuid4().hex
    keep = False
    try:
        check_cancel(cancel)
        if not report_plan.ready:
            raise ImportProblem('Prøven mangler påkrevde filer eller har uavklarte kandidater.')
        if not IDENTIFIER.fullmatch(report_plan.sample_id) or not IDENTIFIER.fullmatch(report_plan.run_id):
            raise ImportProblem('Prøve- eller kjørings-ID er ugyldig.')
        if any(role not in ROLES for role in report_plan.files):
            raise ImportProblem('Importplanen har ukjente filroller.')
        if report_plan.profile not in {'legacy', 'tsoppi-run-v1'}:
            raise ImportProblem('Importplanen har ukjent profil.')
        if report_plan.profile == 'tsoppi-run-v1' and (report_plan.report_version not in {'new', 'legacy', 'raw'}
                or report_plan.cnv_source not in {'merged', 'cancan'} or report_plan.cnv_solution not in {'main', 'alt01', 'alt02'}):
            raise ImportProblem('Importplanen har ukjente kildevalg.')
        # Validate every source boundary before opening a linkage or table file.
        for role, paths in report_plan.files.items():
            for source in paths:
                source = Path(source).absolute()
                if not regular_file(source) or not any(source.resolve(strict=True).is_relative_to(folder.resolve(strict=True))
                                                       for folder in plan.folders):
                    raise ImportProblem('En kilde ligger utenfor de valgte mappene.')
                _validate_run_scope(source, role, report_plan)
                signature = plan.source_signatures.get(source)
                info = source.stat()
                if signature and signature != (info.st_size, info.st_mtime_ns):
                    raise ImportProblem('En kilde er endret siden mappekontrollen. Undersøk mappene på nytt.')
        plots = [path for role in PLOT_ROLES for path in report_plan.files.get(role, ())]
        if len(plots) > MAX_ASSETS or sum(path.stat().st_size for path in plots) > MAX_ASSET_BYTES:
            raise ImportProblem('Rapportens plott overskrider grensen på 100 filer eller 64 MiB samlet.')
        archive.mkdir(mode=0o700)
        sources, hashes, original_names = {}, {}, {}
        linked = _links(report_plan, report_plan.files)
        for role, paths in sorted(report_plan.files.items()):
            for index, source in enumerate(paths):
                source = Path(source).absolute()
                _filename_identity(source, role, report_plan, linked)
                target = archive / f'{role}-{index}{source.suffix.lower()}'
                hashes[target] = _copy(source, target, cancel)
                original_names[target] = source.name
                sources[role] = (*sources.get(role, ()), target)
        fingerprint_fields = [
            report_plan.sample_id, report_plan.run_id,
            sorted((role, hashes[p][0]) for role, paths in sources.items() for p in paths)
        ]
        if report_plan.profile == 'tsoppi-run-v1':
            fingerprint_fields.append([report_plan.profile, report_plan.report_version, report_plan.cnv_source, report_plan.cnv_solution])
        fingerprint = hashlib.sha256(json.dumps(fingerprint_fields, separators=(',', ':')).encode()).hexdigest()
        if progress:
            progress('Validerer og lagrer neste prøve …')
        report, assets = _build_report(report_plan, sources, archive, hashes, original_names, cancel)
        review = _review(report, actor)
        # Keep original input snapshots, discard the temporary adapter tree.
        shutil.rmtree(archive / 'canonical')
        check_cancel(cancel)
        with transaction.atomic():
            from django.contrib.auth import get_user_model
            if not get_user_model().objects.select_for_update().filter(pk=actor.pk, is_active=True).exists():
                raise ImportProblem('Importansvarlig bruker er ikke lenger aktiv.')
            record = ReportRecord.objects.select_for_update().filter(report_id=report.report_id).first()
            if record:
                if not ReportGrant.objects.filter(report=record, user=actor).exists():
                    raise ImportProblem('Denne rapportidentiteten finnes allerede uten tilgang for valgt bruker.')
                if not ImportItem.objects.filter(report=record, fingerprint=fingerprint, status='imported').exists():
                    raise ImportProblem('Rapporten finnes allerede med annet eller ukjent kildegrunnlag.')
                ImportItem.objects.create(batch=batch, report=record, sample_id=report_plan.sample_id,
                    run_id=report_plan.run_id, fingerprint=fingerprint, status='already_imported',
                    message='Allerede importert; rapporten er bevart.')
                return ImportItemResult(record.pk, report_plan.sample_id, 'already_imported', 'Allerede importert; rapporten er bevart.')
            record = ReportRecord.objects.create(report_id=report.report_id,
                report_data=json.loads(serialize_report_data(report)))
            ReviewRevision.objects.create(report=record, revision=1,
                review_data=json.loads(serialize_review_state(review)))
            ReportGrant.objects.create(report=record, user=actor)
            ReportAsset.objects.bulk_create([ReportAsset(report=record, asset_id=key, content=value)
                                            for key, value in assets.items()])
            item = ImportItem.objects.create(batch=batch, report=record, sample_id=report_plan.sample_id,
                run_id=report_plan.run_id, fingerprint=fingerprint, status='imported',
                message='Importert og klar til gjennomgang.')
            ImportSource.objects.bulk_create([ImportSource(item=item, role=role,
                original_name=original_names[p], archive_key=p.relative_to(raw_root).as_posix(),
                sha256=hashes[p][0], size_bytes=hashes[p][1])
                for role, paths in sources.items() for p in paths])
            check_cancel(cancel)
        keep = True
        return ImportItemResult(record.pk, report_plan.sample_id, 'imported', 'Importert og klar til gjennomgang.')
    finally:
        if not keep and archive.exists():
            # Generated direct child of raw_root; never a source directory.
            if archive.parent == raw_root and len(archive.name) == 32:
                shutil.rmtree(archive)


def import_plan(plan, actor, raw_root, progress=None, cancel=None):
    """Each sample commits independently. Failure/cancel never alters older reports."""
    from django.utils import timezone as django_timezone
    from django.contrib.auth import get_user_model
    from pronto_web.reports.models import ImportBatch, ImportItem
    if actor is None or not actor.pk or not get_user_model().objects.filter(pk=actor.pk, is_active=True).exists():
        raise ValueError('Velg en aktiv eksisterende bruker som importansvarlig.')
    reports = tuple(report for report in plan.reports if report.selected)
    if not reports:
        raise ValueError('Velg minst én prøve for import.')
    if not 1 <= len(plan.folders) <= 5:
        raise ValueError('Velg mellom én og fem kildemapper.')
    raw_root = Path(raw_root).absolute()
    for component in (raw_root, *raw_root.parents):
        if component.is_symlink() or (component.exists() and getattr(component.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Privat kildelager kan ikke være en lenke.')
    raw_root = raw_root.resolve()
    roots = tuple(folder.resolve(strict=True) for folder in plan.folders)
    if any(raw_root == folder or raw_root.is_relative_to(folder) or folder.is_relative_to(raw_root) for folder in roots):
        raise ValueError('Privat kildelager må ligge utenfor de valgte kildemappene.')
    raw_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    batch = ImportBatch.objects.create(actor=actor, folder_count=len(plan.folders))
    results, cancelled = [], False
    try:
        for report_plan in reports:
            try:
                if cancelled:
                    raise ImportCancelled()
                result = _import_one(plan, report_plan, actor, raw_root, batch, progress, cancel)
            except ImportCancelled:
                cancelled = True
                result = ImportItemResult('', report_plan.sample_id, 'cancelled', 'Avbrutt; tidligere fullførte prøver er bevart.')
            except ImportProblem as error:
                result = ImportItemResult('', report_plan.sample_id, 'failed', str(error))
            except Exception:
                # Parser/database exceptions may include private paths or cells.
                # Persist only a fixed diagnostic; raw Python errors are not logged.
                result = ImportItemResult('', report_plan.sample_id, 'failed', 'Import kunne ikke fullføres. Kontroller filstruktur og format.')
            if result.status in {'failed', 'cancelled'}:
                ImportItem.objects.create(batch=batch, sample_id=report_plan.sample_id,
                    run_id=report_plan.run_id, status=result.status, message=result.message)
            results.append(result)
            if progress:
                progress(f'{len(results)} av {len(reports)} prøver behandlet.')
    finally:
        batch.status = ('CANCELLED' if cancelled else 'PARTIAL' if any(r.status == 'failed' for r in results) else 'COMPLETED')
        batch.finished_at = django_timezone.now()
        batch.save(update_fields=['status', 'finished_at'])
    return ImportResult(tuple(results), str(batch.pk))
