from pathlib import Path
import shutil

import pytest

from pronto_ingest.discovery import discover_folders, assign_source

SAMPLE = 'IPD2225-D01-P01-A08'
FIXTURE = Path(__file__).parents[3] / 'test_data/ous/251114_A02134_0115_BHCJCKDRX7_TSO_500_LocalApp_postprocessing_results'


@pytest.fixture
def five_folders(tmp_path):
    folders = tuple(tmp_path / f'part-{i}' for i in range(5))
    for folder in folders:
        folder.mkdir()
    shutil.copy(FIXTURE / 'InPreD_PRONTO_metadata.txt', folders[0])
    for path in FIXTURE.glob('*_variant_summary.tsv'):
        shutil.copy(path, folders[1])
    target = folders[2] / 'nested' / SAMPLE
    target.mkdir(parents=True)
    for name in [f'{SAMPLE}_small_variant_table_forQC.tsv', 'sample_list.tsv']:
        shutil.copy(FIXTURE / SAMPLE / name, target)
    return folders


def test_discovers_recursive_five_folder_run(five_folders):
    plan = discover_folders(five_folders)
    report = next(r for r in plan.reports if r.sample_id == SAMPLE)
    assert report.ready
    assert set(report.files) >= {'metadata', 'summary', 'variants', 'sample_list'}
    assert report.run_id == '251114_A02134_0115_BHCJCKDRX7'


def test_requires_five_separate_nonoverlapping_folders(five_folders):
    with pytest.raises(ValueError):
        discover_folders(five_folders[:4])
    with pytest.raises(ValueError):
        discover_folders((*five_folders[:4], five_folders[0]))
    nested = five_folders[0] / 'child'
    nested.mkdir()
    with pytest.raises(ValueError):
        discover_folders((*five_folders[:4], nested))


def test_ambiguous_required_input_needs_explicit_selection(five_folders):
    source = next(five_folders[2].rglob('*forQC.tsv'))
    copy = five_folders[4] / source.name
    shutil.copy(source, copy)
    plan = discover_folders(five_folders)
    report = next(r for r in plan.reports if r.sample_id == SAMPLE)
    assert not report.ready
    chosen = assign_source(plan, report.key, 'variants', source)
    assert next(r for r in chosen.reports if r.sample_id == SAMPLE).ready


def test_generic_cnv_needs_assignment_and_unknown_file_not_attachable(five_folders):
    source = five_folders[4] / 'CNV_summary_table.csv'
    source.write_text('Gene_Symbol;Chromosome;Gene_Start\nMET;7;1\n')
    plan = discover_folders(five_folders)
    assert any(c.path == source and c.role == 'cnv_table' for c in plan.unassigned)
    report = next(r for r in plan.reports if r.sample_id == SAMPLE)
    chosen = assign_source(plan, report.key, 'cnv_table', source)
    assert next(r for r in chosen.reports if r.sample_id == SAMPLE).files['cnv_table'] == (source,)
    with pytest.raises(ValueError):
        assign_source(plan, report.key, 'cnv_table', Path(__file__))


def test_scan_cancels_and_does_not_read_bam(five_folders):
    (five_folders[0] / 'large.bam').write_bytes(b'not a table')
    from pronto_ingest.contracts import ImportCancelled
    with pytest.raises(ImportCancelled):
        discover_folders(five_folders, cancel=lambda: True)


@pytest.mark.django_db
def test_import_archive_permissions_and_repeat_are_stable(five_folders, tmp_path, django_user_model):
    from pronto_ingest.importer import import_plan
    from pronto_web.reports.models import ImportBatch, ImportSource, ReportRecord, ReportGrant, ReviewRevision
    actor = django_user_model.objects.create_user(username='importer')
    plan = discover_folders(five_folders)
    # Fixture metadata may contain other samples that have no source tables in this split layout.
    from dataclasses import replace
    plan = replace(plan, reports=tuple(r for r in plan.reports if r.sample_id == SAMPLE))
    raw_root = tmp_path / 'private'
    first = import_plan(plan, actor, raw_root)
    assert first.items[0].status == 'imported'
    record = ReportRecord.objects.get()
    assert ReportGrant.objects.get(report=record).user == actor
    assert ReviewRevision.objects.get(report=record).revision == 1
    assert ImportSource.objects.count() == 4
    assert all((raw_root / s.archive_key).is_file() for s in ImportSource.objects.all())
    second = import_plan(plan, actor, raw_root)
    assert second.items[0].status == 'already_imported'
    assert ReportRecord.objects.count() == 1
    assert ImportBatch.objects.count() == 2
    other = django_user_model.objects.create_user(username='outsider')
    denied = import_plan(plan, other, raw_root)
    assert denied.items[0].status == 'failed'
    assert ReportGrant.objects.count() == 1


@pytest.mark.django_db
def test_changed_source_conflicts_instead_of_overwriting(five_folders, tmp_path, django_user_model):
    from dataclasses import replace
    from pronto_ingest.importer import import_plan
    from pronto_web.reports.models import ReportRecord
    actor = django_user_model.objects.create_user(username='importer')
    plan = discover_folders(five_folders)
    plan = replace(plan, reports=tuple(r for r in plan.reports if r.sample_id == SAMPLE))
    assert import_plan(plan, actor, tmp_path / 'raw').items[0].status == 'imported'
    original = ReportRecord.objects.get().report_data
    variant = next(five_folders[2].rglob('*forQC.tsv'))
    variant.write_bytes(variant.read_bytes() + b'\n')
    result = import_plan(plan, actor, tmp_path / 'raw')
    assert result.items[0].status == 'failed'
    assert ReportRecord.objects.get().report_data == original


def test_unknown_and_corrupt_files_are_visible_without_bam_read(five_folders):
    bam = five_folders[0] / 'reads.bam'
    bam.write_bytes(b'not opened as a table')
    broken = five_folders[0] / 'broken.xlsx'
    broken.write_bytes(b'bad zip')
    plan = discover_folders(five_folders)
    assert any(c.path == bam and c.role == 'unknown' for c in plan.unassigned)
    assert any('leses' in warning for warning in plan.warnings)


def test_duplicate_optional_tables_need_selection(five_folders):
    text = f'Gene_Symbol;Sample_ID;Chromosome;Gene_Start\nMET;{SAMPLE};7;1\n'
    for index in (3, 4):
        (five_folders[index] / 'cnv.csv').write_text(text)
    plan = discover_folders(five_folders)
    report = next(r for r in plan.reports if r.sample_id == SAMPLE)
    assert not report.ready
    assert any('cnv_table' in issue for issue in report.issues)
    assert next(r for r in assign_source(plan, report.key, 'cnv_table', five_folders[3] / 'cnv.csv').reports if r.sample_id == SAMPLE).ready


@pytest.mark.django_db
def test_wrong_sample_variant_filename_cannot_be_manually_attached(five_folders, tmp_path, django_user_model):
    from pronto_ingest.importer import import_plan
    from pronto_web.reports.models import ReportRecord
    actor = django_user_model.objects.create_user(username='importer')
    wrong = five_folders[4] / 'OTHER_small_variant_table_forQC.tsv'
    shutil.copy(next(five_folders[2].rglob('*forQC.tsv')), wrong)
    plan = discover_folders(five_folders)
    report = next(r for r in plan.reports if r.sample_id == SAMPLE)
    plan = assign_source(plan, report.key, 'variants', wrong)
    result = import_plan(plan, actor, tmp_path / 'raw')
    assert result.items[0].status == 'failed'
    assert not ReportRecord.objects.exists()


@pytest.mark.django_db
def test_wrong_run_summary_filename_cannot_be_manually_attached(five_folders, tmp_path, django_user_model):
    from pronto_ingest.importer import import_plan
    from pronto_web.reports.models import ReportRecord
    actor = django_user_model.objects.create_user(username='importer')
    wrong = five_folders[4] / 'OTHER_variant_summary.tsv'
    shutil.copy(next(five_folders[1].glob('*variant_summary.tsv')), wrong)
    plan = discover_folders(five_folders)
    report = next(r for r in plan.reports if r.sample_id == SAMPLE)
    plan = assign_source(plan, report.key, 'summary', wrong)
    result = import_plan(plan, actor, tmp_path / 'raw')
    assert result.items[0].status == 'failed'
    assert not ReportRecord.objects.exists()


@pytest.mark.django_db
def test_transaction_failure_leaves_no_report_or_archive(five_folders, tmp_path, django_user_model, monkeypatch):
    from pronto_ingest.importer import import_plan
    from pronto_web.reports.models import ReportRecord, ReviewRevision, ImportSource, ImportItem
    actor = django_user_model.objects.create_user(username='importer')
    def fail(*args, **kwargs):
        raise RuntimeError('private-source-path/patient-value')
    monkeypatch.setattr(ReviewRevision.objects, 'create', fail)
    result = import_plan(discover_folders(five_folders), actor, tmp_path / 'raw')
    assert result.items[0].status == 'failed'
    assert 'private-source' not in result.items[0].message
    assert not ReportRecord.objects.exists()
    assert not ImportSource.objects.exists()
    assert ImportItem.objects.get().status == 'failed'
    assert not list((tmp_path / 'raw').iterdir())


@pytest.mark.django_db
def test_cancellation_leaves_no_report_or_archive(five_folders, tmp_path, django_user_model):
    from pronto_ingest.importer import import_plan
    from pronto_web.reports.models import ReportRecord, ImportBatch
    actor = django_user_model.objects.create_user(username='importer')
    result = import_plan(discover_folders(five_folders), actor, tmp_path / 'raw', cancel=lambda: True)
    assert result.items[0].status == 'cancelled'
    assert not ReportRecord.objects.exists()
    assert ImportBatch.objects.get().status == 'CANCELLED'
    assert not list((tmp_path / 'raw').iterdir())


@pytest.mark.django_db
def test_optional_tables_filter_exact_patient_but_archive_complete_original(five_folders, tmp_path, django_user_model):
    from pronto_ingest.importer import import_plan
    from pronto_web.reports.models import ReportRecord, ImportSource
    actor = django_user_model.objects.create_user(username='importer')
    cnv = five_folders[3] / 'cnv.csv'
    cnv.write_text(f'Gene_Symbol;Sample_ID;Chromosome;Gene_Start\nMET;{SAMPLE};7;1\nPRIVATE_OTHER;OTHER;8;2\n')
    rna = five_folders[4] / 'rna.tsv'
    rna.write_text('Provisional_Event_Type\tSample_ID\tGene_A\tGene_B\tProvisional_Event_ID\n'
                   'Fusion\tIPD2225-R03-P01-A08\tMET\tALK\tF1\n'
                   'Fusion\tOTHER-RNA\tPRIVATE_OTHER\tGENE\tF2\n')
    result = import_plan(discover_folders(five_folders), actor, tmp_path / 'raw')
    assert result.items[0].status == 'imported'
    document = ReportRecord.objects.get().report_data
    assert 'PRIVATE_OTHER' not in str(document)
    assert len(next(t for t in document['sourceTables'] if t['kind'] == 'CNV')['rows']) == 1
    assert len(next(t for t in document['sourceTables'] if t['kind'] == 'RNA')['rows']) == 1
    source = ImportSource.objects.get(role='cnv_table')
    assert 'PRIVATE_OTHER' in (tmp_path / 'raw' / source.archive_key).read_text()
    assert not any(str(folder) in str(document) for folder in five_folders)


@pytest.mark.django_db
def test_unknown_existing_report_provenance_is_never_overwritten(five_folders, tmp_path, django_user_model):
    from pronto_ingest.importer import import_plan
    from pronto_web.reports.models import ReportRecord, ReportGrant
    actor = django_user_model.objects.create_user(username='importer')
    plan = discover_folders(five_folders)
    record = ReportRecord.objects.create(report_id=plan.reports[0].key, report_data={'old': True})
    ReportGrant.objects.create(report=record, user=actor)
    result = import_plan(plan, actor, tmp_path / 'raw')
    assert result.items[0].status == 'failed'
    record.refresh_from_db()
    assert record.report_data == {'old': True}


@pytest.mark.django_db
def test_stale_actor_state_is_refetched(five_folders, tmp_path, django_user_model):
    from pronto_ingest.importer import import_plan
    actor = django_user_model.objects.create_user(username='importer')
    django_user_model.objects.filter(pk=actor.pk).update(is_active=False)
    with pytest.raises(ValueError):
        import_plan(discover_folders(five_folders), actor, tmp_path / 'raw')


def test_source_table_csv_uses_header_delimiter_and_preserves_quoted_values(tmp_path):
    from pronto_report.adapters.source_tables import read_source_table
    path = tmp_path / 'cnv.csv'
    path.write_text('Gene_Symbol,Sample_ID,Comment\nMET,S1,"comma, and semicolon; preserved"\n')
    table = read_source_table(path, kind='CNV')
    assert table['headers'] == ['Gene_Symbol', 'Sample_ID', 'Comment']
    assert table['rows'][0]['values'] == ['MET', 'S1', 'comma, and semicolon; preserved']


def test_discovery_ignores_disabled_rna_metadata_and_links_rna_qc(five_folders):
    rna = five_folders[3] / 'IPD2225-R03-P01-A08_sample_QC_plot.png'
    rna.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic')
    plan = discover_folders(five_folders)
    assert len(plan.reports) == 1
    assert rna in plan.reports[0].files['qc_plot']


@pytest.mark.django_db
def test_changed_since_scan_requires_rescan(five_folders, tmp_path, django_user_model):
    from pronto_ingest.importer import import_plan
    from pronto_web.reports.models import ReportRecord
    actor = django_user_model.objects.create_user(username='importer')
    plan = discover_folders(five_folders)
    source = next(five_folders[2].rglob('*forQC.tsv'))
    source.write_bytes(source.read_bytes() + b'\n')
    result = import_plan(plan, actor, tmp_path / 'raw')
    assert result.items[0].status == 'failed'
    assert 'siden mappekontrollen' in result.items[0].message
    assert not ReportRecord.objects.exists()


@pytest.mark.django_db
def test_plots_preserve_original_name_and_archived_source_basename(five_folders, tmp_path, django_user_model):
    from pronto_ingest.importer import import_plan
    from pronto_web.reports.models import ReportRecord, ImportSource, ReportAsset
    actor = django_user_model.objects.create_user(username='importer')
    source = FIXTURE / SAMPLE / f'{SAMPLE}_CNV_overview_plots.pdf'
    shutil.copy(source, five_folders[3])
    result = import_plan(discover_folders(five_folders), actor, tmp_path / 'raw')
    assert result.items[0].status == 'imported'
    assert ReportRecord.objects.get().report_data['attachments'][0]['name'] == source.name
    assert ImportSource.objects.get(role='cnv_plot').original_name == source.name
    assert bytes(ReportAsset.objects.get().content) == source.read_bytes()


@pytest.mark.django_db
def test_plan_path_traversal_cannot_read_outside_selected_folders(five_folders, tmp_path, django_user_model):
    from dataclasses import replace
    from pronto_ingest.importer import import_plan
    from pronto_web.reports.models import ReportRecord
    actor = django_user_model.objects.create_user(username='importer')
    plan = discover_folders(five_folders)
    outside = tmp_path / 'outside'
    outside.mkdir()
    shutil.copy(next(five_folders[2].rglob('*forQC.tsv')), outside / 'table.tsv')
    source = five_folders[0] / '..' / 'outside' / 'table.tsv'
    files = dict(plan.reports[0].files, variants=(source,))
    plan = replace(plan, reports=(replace(plan.reports[0], files=files),))
    result = import_plan(plan, actor, tmp_path / 'raw')
    assert result.items[0].status == 'failed'
    assert not ReportRecord.objects.exists()


@pytest.mark.django_db
def test_empty_plan_is_not_a_successful_import(five_folders, tmp_path, django_user_model):
    from dataclasses import replace
    from pronto_ingest.importer import import_plan
    from pronto_web.reports.models import ImportBatch
    actor = django_user_model.objects.create_user(username='importer')
    plan = replace(discover_folders(five_folders), reports=())
    with pytest.raises(ValueError):
        import_plan(plan, actor, tmp_path / 'raw')
    assert not ImportBatch.objects.exists()


@pytest.mark.django_db
def test_archive_inside_selected_tree_is_rejected_without_creating_directory(five_folders, django_user_model):
    from pronto_ingest.importer import import_plan
    actor = django_user_model.objects.create_user(username='importer')
    archive = five_folders[0] / 'must-not-create'
    with pytest.raises(ValueError):
        import_plan(discover_folders(five_folders), actor, archive)
    assert not archive.exists()


@pytest.mark.parametrize('commented', [False, True])
def test_sample_list_header_can_be_commented_or_plain(five_folders, commented):
    path = next(five_folders[2].rglob('sample_list.tsv'))
    text = path.read_text().lstrip('#')
    path.write_text(('#' if commented else '') + text)
    assert discover_folders(five_folders).reports[0].ready


@pytest.mark.django_db
@pytest.mark.parametrize('suffix,payload', [('.png', b'\x89PNG\r\n\x1a\ninvalid'), ('.pdf', b'%PDF-1.7\ninvalid')])
def test_corrupt_plot_after_magic_is_not_committed(five_folders, tmp_path, django_user_model, suffix, payload):
    from pronto_ingest.importer import import_plan
    from pronto_web.reports.models import ReportRecord
    actor = django_user_model.objects.create_user(username='importer')
    name = f'{SAMPLE}_sample_QC_plot.png' if suffix == '.png' else f'{SAMPLE}_CNV_overview_plots.pdf'
    (five_folders[3] / name).write_bytes(payload)
    result = import_plan(discover_folders(five_folders), actor, tmp_path / 'raw')
    assert result.items[0].status == 'failed'
    assert not ReportRecord.objects.exists()


@pytest.mark.django_db
def test_plot_over_renderer_limit_is_not_committed(five_folders, tmp_path, django_user_model):
    from pronto_ingest.importer import import_plan
    from pronto_web.reports.models import ReportRecord
    from pronto_report.renderers.assets import _MAX_ATTACHMENT_BYTES
    actor = django_user_model.objects.create_user(username='importer')
    (five_folders[3] / f'{SAMPLE}_sample_QC_plot.png').write_bytes(b'\x89PNG\r\n\x1a\n' + b'x' * _MAX_ATTACHMENT_BYTES)
    result = import_plan(discover_folders(five_folders), actor, tmp_path / 'raw')
    assert result.items[0].status == 'failed'
    assert not ReportRecord.objects.exists()


def test_bad_optional_table_preserves_core_discovery(five_folders):
    (five_folders[3] / 'cnv.csv').write_text(f'Gene_Symbol;Sample_ID;Chromosome\nMET;{SAMPLE};7;extra\n')
    plan = discover_folders(five_folders)
    assert plan.reports[0].ready
    assert any('leses' in warning for warning in plan.warnings)


@pytest.mark.django_db
def test_aggregate_plot_limit_fails_before_staging(five_folders, tmp_path, django_user_model, monkeypatch):
    import pronto_ingest.importer as importer
    from pronto_web.reports.models import ReportRecord
    actor = django_user_model.objects.create_user(username='importer')
    shutil.copy(FIXTURE / SAMPLE / f'{SAMPLE}_CNV_overview_plots.pdf', five_folders[3])
    monkeypatch.setattr(importer, 'MAX_ASSET_BYTES', 1)
    result = importer.import_plan(discover_folders(five_folders), actor, tmp_path / 'raw')
    assert result.items[0].status == 'failed'
    assert not ReportRecord.objects.exists()
    assert not list((tmp_path / 'raw').iterdir())
