"""Archive bounded inputs and atomically publish one validated report at a time."""
from __future__ import annotations

from datetime import datetime, timezone
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
from .discovery import MAX_BYTES, SAMPLE_COLUMNS, IDENTIFIER, _linked_ids, regular_file, table_rows

MAX_ASSET_BYTES = 64 * 1024 * 1024
MAX_ASSETS = 100


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
    if role == 'summary' and path.name.endswith('_variant_summary.tsv'):
        if path.name[:-len('_variant_summary.tsv')] != report_plan.run_id:
            raise ImportProblem('Sammendragsfilens kjørings-ID avviker fra valgt kjøring.')
    suffixes = {'variants': ('_small_variant_table_forQC.tsv', '_small_variant_table.tsv'),
                'cnv_plot': ('_CNV_overview_plots.pdf',),
                'qc_plot': ('_sample_QC_plot.png', '_sample_QC_plot.pdf')}
    for suffix in suffixes.get(role, ()):
        allowed = linked if role == 'qc_plot' else {report_plan.sample_id}
        if path.name.endswith(suffix) and path.name[:-len(suffix)] not in allowed:
            raise ImportProblem('Kildefilens prøve-ID avviker fra valgt prøve.')


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
    metadata = table_rows(sources['metadata'][0], header={'Sample_id', 'Sequencing_run_id', 'Study_id'})
    exact = [r for r in metadata if r.get('Sample_id') == report_plan.sample_id
             and r.get('Sequencing_run_id') == report_plan.run_id]
    if len(exact) != 1:
        raise ImportProblem('Metadata har manglende eller flere rader for prøve og kjøring.')
    if 'Create_report' in exact[0] and exact[0]['Create_report'].strip().upper() not in {'Y', 'YES', 'JA', 'TRUE', '1'}:
        raise ImportProblem('Metadata angir at rapport ikke skal opprettes for denne prøven.')
    # The legacy adapter picks by sample only. Refuse cross-run ambiguity here.
    if len([r for r in metadata if r.get('Sample_id') == report_plan.sample_id]) != 1:
        raise ImportProblem('Metadata inneholder samme prøve i flere kjøringer.')
    summary = table_rows(sources['summary'][0], header={'sample_id', 'TMB', 'MSI'})
    if len([r for r in summary if r['sample_id'] in {report_plan.sample_id, report_plan.sample_id + '_P'}]) != 1:
        raise ImportProblem('Analysesammendraget identifiserer ikke prøven entydig.')
    variants = table_rows(sources['variants'][0], header={'Gene_symbol', 'Genomic_location', 'DNA_change'})
    for row in variants:
        ids = {str(row[c]) for c in SAMPLE_COLUMNS if row.get(c)}
        if ids and ids != {report_plan.sample_id}:
            raise ImportProblem('Varianttabellen inneholder en annen prøve-ID.')
    return _linked_ids(sources['sample_list'][0], report_plan.sample_id)


def _build_report(report_plan, sources, archive, hashes, original_names, cancel=None):
    from pronto_report.adapters.pronto_output import adapt_pronto_output
    from pronto_report.adapters.source_tables import read_source_table
    from pronto_report.serialization import serialize_report_data
    from pronto_report.validation import validate_report_data
    linked = _validate_sources(report_plan, sources)
    canonical = archive / 'canonical'
    sample_dir = canonical / report_plan.sample_id
    sample_dir.mkdir(parents=True)
    shutil.copyfile(sources['metadata'][0], canonical / 'InPreD_PRONTO_metadata.txt')
    shutil.copyfile(sources['summary'][0], canonical / 'run_variant_summary.tsv')
    shutil.copyfile(sources['variants'][0], sample_dir / f'{report_plan.sample_id}_small_variant_table_forQC.tsv')
    shutil.copyfile(sources['sample_list'][0], sample_dir / 'sample_list.tsv')
    now = datetime.now(timezone.utc).isoformat()
    report = adapt_pronto_output(canonical, sample_id=report_plan.sample_id,
                                generated_at=now, generator_version='desktop-1')
    document = json.loads(serialize_report_data(report))
    # Hash provenance points to the archived original bytes, using opaque relative
    # names. No workstation paths are exposed through report JSON or HTML.
    document['provenance']['sourceFiles'] = [
        {'name': p.name, 'sha256': hashes[p][0], 'sizeBytes': hashes[p][1]}
        for paths in sources.values() for p in paths]
    for role, kind in [('cnv_table', 'CNV'), ('rna_table', 'RNA')]:
        for path in sources.get(role, ()):
            check_cancel(cancel)
            table = read_source_table(path, kind=kind)
            columns = [table['headers'].index(c) for c in SAMPLE_COLUMNS if c in table['headers']]
            if columns:
                allowed = linked if role == 'rna_table' else {report_plan.sample_id}
                table['rows'] = [r for r in table['rows'] if any(str(r['values'][c]) in allowed for c in columns)]
                if not table['rows']:
                    raise ImportProblem('Tilleggstabellen mangler eksakt kobling til denne prøven.')
            document['sourceTables'].append(table)
    assets = {}
    for role in ('cnv_plot', 'qc_plot', 'other_plot'):
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
                'description': {'cnv_plot': 'CNV', 'qc_plot': 'QC', 'other_plot': 'RNA / domene'}[role]})
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
        plots = [path for role in ('cnv_plot', 'qc_plot', 'other_plot') for path in report_plan.files.get(role, ())]
        if len(plots) > MAX_ASSETS or sum(path.stat().st_size for path in plots) > MAX_ASSET_BYTES:
            raise ImportProblem('Rapportens plott overskrider grensen på 100 filer eller 64 MiB samlet.')
        archive.mkdir(mode=0o700)
        sources, hashes, original_names = {}, {}, {}
        linked = _linked_ids(report_plan.files['sample_list'][0], report_plan.sample_id)
        for role, paths in sorted(report_plan.files.items()):
            for index, source in enumerate(paths):
                source = Path(source).absolute()
                if not regular_file(source) or not any(source.resolve(strict=True).is_relative_to(folder.resolve(strict=True))
                                                       for folder in plan.folders):
                    raise ImportProblem('En kilde ligger utenfor de fem valgte mappene.')
                signature = plan.source_signatures.get(source)
                info = source.stat()
                if signature and signature != (info.st_size, info.st_mtime_ns):
                    raise ImportProblem('En kilde er endret siden mappekontrollen. Undersøk mappene på nytt.')
                _filename_identity(source, role, report_plan, linked)
                target = archive / f'{role}-{index}{source.suffix.lower()}'
                hashes[target] = _copy(source, target, cancel)
                original_names[target] = source.name
                sources[role] = (*sources.get(role, ()), target)
        fingerprint = hashlib.sha256(json.dumps([
            report_plan.sample_id, report_plan.run_id,
            sorted((role, hashes[p][0]) for role, paths in sources.items() for p in paths)
        ], separators=(',', ':')).encode()).hexdigest()
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
    if not plan.reports:
        raise ValueError('Ingen rapporter å importere. Kontroller metadata og filoversikt.')
    if len(plan.folders) != 5:
        raise ValueError('En import krever fem mapper.')
    raw_root = Path(raw_root).absolute()
    for component in (raw_root, *raw_root.parents):
        if component.is_symlink() or (component.exists() and getattr(component.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Privat kildelager kan ikke være en lenke.')
    raw_root = raw_root.resolve()
    roots = tuple(folder.resolve(strict=True) for folder in plan.folders)
    if any(raw_root == folder or raw_root.is_relative_to(folder) or folder.is_relative_to(raw_root) for folder in roots):
        raise ValueError('Privat kildelager må ligge utenfor de valgte kildemappene.')
    raw_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    batch = ImportBatch.objects.create(actor=actor)
    results, cancelled = [], False
    try:
        for report_plan in plan.reports:
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
                progress(f'{len(results)} av {len(plan.reports)} prøver behandlet.')
    finally:
        batch.status = ('CANCELLED' if cancelled else 'PARTIAL' if any(r.status == 'failed' for r in results) else 'COMPLETED')
        batch.finished_at = django_timezone.now()
        batch.save(update_fields=['status', 'finished_at'])
    return ImportResult(tuple(results), str(batch.pk))
