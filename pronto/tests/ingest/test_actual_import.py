"""Synthetic work-run layout; no private workstation inputs are used."""
from dataclasses import replace
from pathlib import Path

import pytest

from pronto_ingest.discovery import discover_folders, set_report_selected
from pronto_ingest.importer import import_plan

DNA = 'SYNTHETIC-D01-P01-A01'
RNA = 'SYNTHETIC-R03-P01-A01'
RUN = '261001_A00001_0001_AABCDEFGHI'
OLD_RUN = '250101_A00001_0001_AABCDEFGHI'


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


@pytest.fixture
def actual_sources(tmp_path):
    roots = {key: tmp_path / 'sources' / (RUN + suffix) for key, suffix in (
        ('raw', ''), ('cnv', '_CNVs'), ('legacy', '_report_preQC'),
        ('new', '_report_preQC_newPRONTO_version'))}
    for root in roots.values():
        (root / DNA).mkdir(parents=True)
    write(roots['raw'] / 'InPreD_PRONTO_metadata_tsoppi.txt',
          'Sample_id\tSequencing_run_id\tStudy_id\tCreate_report\tClinical_diagnosis\n'
          f'{DNA}\t{OLD_RUN}\tOLD-SYNTHETIC\tY\tHistorical\n'
          f'{DNA}\t{RUN}\tSYNTHETIC\t-\tSynthetic diagnosis\n'
          f'{RNA}\t{RUN}\tSYNTHETIC\tY\tSynthetic diagnosis\n')
    write(roots['raw'] / f'{RUN}_variant_summary.tsv',
          f'sample_id\tTMB\tMSI\n{DNA}_P\t3\t0\n{RNA}_P\t0\t0\n')
    variants = ('# Synthetic tool/version/hg19/TR\n'
                'Sample_ID\tGene_symbol\tGenomic_location\tDNA_change\tChange_summary\n'
                f'{DNA}\tTEST\t1:123\tA>G\tSynthetic change\n')
    write(roots['raw'] / DNA / f'{DNA}_small_variant_table.tsv',
          f'# [{DNA}] ID of matched tumor RNA sample: {RNA}\n' + variants)
    for version in ('new', 'legacy'):
        write(roots[version] / DNA / f'{DNA}_small_variant_table_forQC.tsv', variants)
    write(roots['raw'] / DNA / f'{DNA}_sample_concordance.tsv',
          f'# Concordance between processed [tumor DNA: "{DNA}"] and [tumor RNA: "{RNA}"] samples:\n'
          'HomHet_count\tHomHet_matches\n100\t100\n')
    write(roots['raw'] / DNA / f'{DNA}_merged_CNV_summary_FC_sorted.tsv',
          'Chromosome\tGene_Start\tGene_Symbol\tTumor_FC\n1\t1\tTEST\t2\n')
    write(roots['raw'] / DNA / f'{RNA}_fusion_and_splice_variant_candidates.tsv',
          f'Provisional_Event_Type\tEvent_Type\tSample_ID\tGene_A\nFusion\t.\t{RNA}\tTEST\n')
    write(roots['new'] / DNA / 'extra_files' / f'{DNA}_Main_Findings.txt', 'Synthetic source note')
    return roots


def selected_plan(roots, **options):
    plan = discover_folders(tuple(roots.values()), **options)
    assert len(plan.reports) == 1
    assert plan.reports[0].ready, plan.reports[0].issues
    return set_report_selected(plan, plan.reports[0].key, True)


def missing_study_plan(roots):
    path = roots['raw'] / 'InPreD_PRONTO_metadata_tsoppi.txt'
    path.write_text(path.read_text().replace(f'{DNA}\t{RUN}\tSYNTHETIC\t', f'{DNA}\t{RUN}\t\t'))
    return discover_folders(tuple(roots.values()))


def test_manual_study_id_only_resolves_that_missing_field(actual_sources):
    from pronto_ingest.metadata import set_manual_study_id
    plan = missing_study_plan(actual_sources)
    report = plan.reports[0]
    plan = replace(plan, reports=(replace(report, issues=(*report.issues, 'variants: mangler')),))
    fixed = set_manual_study_id(plan, report.key, 'STUDY-A / 123')
    assert fixed.reports[0].study_id_override == 'STUDY-A / 123'
    assert fixed.reports[0].issues == ('variants: mangler',)
    assert not fixed.reports[0].ready
    reset = set_manual_study_id(fixed, report.key, '')
    assert 'metadata: Study_id mangler' in reset.reports[0].issues
    for invalid in ('NA', '-', 'BAD\nVALUE', 'A' * 129):
        with pytest.raises(ValueError):
            set_manual_study_id(plan, report.key, invalid)


def test_manual_study_id_refuses_existing_value_and_missing_row(actual_sources):
    from pronto_ingest.metadata import set_manual_study_id
    plan = discover_folders(tuple(actual_sources.values()))
    with pytest.raises(ValueError):
        set_manual_study_id(plan, plan.reports[0].key, 'CHANGED')
    report = replace(plan.reports[0], sample_id='OTHER')
    with pytest.raises(ValueError):
        set_manual_study_id(replace(plan, reports=(report,)), report.key, 'NEW')


def test_rescan_preserves_manual_id_only_for_unchanged_metadata(actual_sources):
    from pronto_ingest.metadata import set_manual_study_id, preserve_manual_study_ids
    plan = missing_study_plan(actual_sources)
    fixed = set_manual_study_id(plan, plan.reports[0].key, 'MANUAL')
    fresh = discover_folders(tuple(actual_sources.values()))
    kept = preserve_manual_study_ids(fixed, fresh)
    assert kept.reports[0].study_id_override == 'MANUAL' and kept.reports[0].ready
    path = fresh.reports[0].files['metadata'][0]
    path.write_text(path.read_text() + '# changed source\n')
    changed = preserve_manual_study_ids(fixed, discover_folders(tuple(actual_sources.values())))
    assert not changed.reports[0].study_id_override
    assert not changed.reports[0].ready
    assert any('nullstilt' in warning for warning in changed.warnings)


@pytest.mark.django_db
def test_manual_study_id_is_archived_and_reimport_is_stable(actual_sources, tmp_path, django_user_model):
    import json
    from hashlib import sha256
    from pronto_ingest.metadata import set_manual_study_id
    from pronto_web.reports.models import ImportSource, ReportRecord
    plan = missing_study_plan(actual_sources)
    source = plan.reports[0].files['metadata'][0]
    original = source.read_bytes()
    plan = set_manual_study_id(plan, plan.reports[0].key, 'MANUAL-STUDY / 123')
    plan = set_report_selected(plan, plan.reports[0].key, True)
    actor = django_user_model.objects.create_user(username='manual-operator')
    archive = tmp_path / 'archive'
    result = import_plan(plan, actor, archive)
    assert result.items[0].status == 'imported', result
    document = ReportRecord.objects.get().report_data
    assert document['sample']['patientPseudonym'] == 'MANUAL-STUDY / 123'
    assert any(item['code'] == 'MANUAL_STUDY_ID' for item in document['diagnostics'])
    audit_source = ImportSource.objects.get(role='metadata_override')
    payload = (archive / audit_source.archive_key).read_bytes()
    assert sha256(payload).hexdigest() == audit_source.sha256
    assert json.loads(payload)['manualValue'] == 'MANUAL-STUDY / 123'
    assert json.loads(payload)['originalValue'] == ''
    assert any(item['sha256'] == audit_source.sha256 for item in document['provenance']['sourceFiles'])
    assert source.read_bytes() == original
    assert [item.status for item in import_plan(plan, actor, archive).items] == ['already_imported']
    other = set_manual_study_id(plan, plan.reports[0].key, 'DIFFERENT')
    other = set_report_selected(other, other.reports[0].key, True)
    assert import_plan(other, actor, archive).items[0].status == 'failed'
    assert ReportRecord.objects.get().report_data == document


@pytest.mark.django_db
def test_actual_run_archives_originals_and_uses_exact_historical_metadata_row(actual_sources, tmp_path, django_user_model):
    from pronto_web.reports.models import ImportBatch, ImportSource, ReportRecord, ReviewRevision
    actor = django_user_model.objects.create_user(username='operator')
    plan = selected_plan(actual_sources)
    originals = {p: p.read_bytes() for r in plan.reports for paths in r.files.values() for p in paths}
    archive = tmp_path / 'archive'
    result = import_plan(plan, actor, archive)
    assert [item.status for item in result.items] == ['imported'], result
    document = ReportRecord.objects.get().report_data
    assert document['sample']['patientPseudonym'] == 'SYNTHETIC'
    assert document['sample']['referenceBuild'] == 'GRCh37'
    assert document['run']['runId'] == RUN
    assert ImportBatch.objects.get().folder_count == 4
    assert not ImportSource.objects.filter(role='sample_list').exists()
    assert ImportSource.objects.filter(role='linkage').count() == 2
    assert ImportSource.objects.filter(role='supporting').count() == 1
    metadata = ImportSource.objects.get(role='metadata')
    assert b'OLD-SYNTHETIC' in (archive / metadata.archive_key).read_bytes()
    assert all(p.read_bytes() == content for p, content in originals.items())
    assert not list(archive.rglob('canonical'))
    assert ReviewRevision.objects.get().review_data['status'] == 'DRAFT'
    assert all(not row['sourceApproved'] for table in document['sourceTables'] for row in table['rows'])
    assert any(d['code'] == 'EXPLICIT_REPORT_SELECTION' for d in document['diagnostics'])
    assert [item.status for item in import_plan(plan, actor, archive).items] == ['already_imported']


@pytest.mark.django_db
def test_unselected_and_unconfirmed_actual_metadata_never_import(actual_sources, tmp_path, django_user_model):
    from pronto_web.reports.models import ImportBatch, ReportRecord
    actor = django_user_model.objects.create_user(username='operator')
    plan = discover_folders(tuple(actual_sources.values()))
    with pytest.raises(ValueError):
        import_plan(plan, actor, tmp_path / 'archive')
    assert not ImportBatch.objects.exists()
    forged = replace(plan, reports=(replace(plan.reports[0], selected=True),))
    result = import_plan(forged, actor, tmp_path / 'archive')
    assert result.items[0].status == 'failed'
    assert not ReportRecord.objects.exists()


@pytest.mark.django_db
def test_archived_linkage_is_revalidated_before_commit(actual_sources, tmp_path, django_user_model, monkeypatch):
    import pronto_ingest.importer as importer
    from pronto_web.reports.models import ReportRecord
    actor = django_user_model.objects.create_user(username='operator')
    plan = selected_plan(actual_sources)
    original_copy = importer._copy
    def corrupt_claim(source, target, cancel=None):
        result = original_copy(source, target, cancel)
        if target.name.startswith('linkage-') and 'concordance' in source.name:
            target.write_text(target.read_text().replace(RNA, 'SYNTHETIC-OTHER-RNA'))
        return result
    monkeypatch.setattr(importer, '_copy', corrupt_claim)
    result = import_plan(plan, actor, tmp_path / 'archive')
    assert result.items[0].status == 'failed'
    assert not ReportRecord.objects.exists()
    assert not list((tmp_path / 'archive').iterdir())


@pytest.mark.django_db
def test_missing_change_summary_has_clear_safe_failure(actual_sources, tmp_path, django_user_model):
    actor = django_user_model.objects.create_user(username='operator')
    path = actual_sources['new'] / DNA / f'{DNA}_small_variant_table_forQC.tsv'
    path.write_text(path.read_text().replace('\tChange_summary', '').replace('\tSynthetic change', ''))
    result = import_plan(selected_plan(actual_sources), actor, tmp_path / 'archive')
    assert result.items[0].status == 'failed'
    assert 'Change_summary' in result.items[0].message
    assert str(path) not in result.items[0].message


@pytest.mark.django_db
def test_cancan_selected_solution_preserves_all_columns_and_is_unreviewed(actual_sources, tmp_path, django_user_model):
    from PIL import Image
    from pronto_web.reports.models import ImportSource, ReportAsset, ReportRecord
    actor = django_user_model.objects.create_user(username='operator')
    folder = actual_sources['cnv'] / DNA / f'{DNA}_Cancan_1.1.7'
    for solution, count in [('main', '2'), ('alt01', '3')]:
        write(folder / f'{DNA}_{solution}_gene_table.tsv',
              f'# Sampleid: {DNA}\n# Purity: 0.7\n# Ploidy: {count}\n'
              'chr\tstart.pos.gene\tend.pos.gene\tgene.id\tgene.name\tminor.cn\tmajor.cn\ttotal.cn\tcn.clonal\n'
              f'1\t1\t2\tID1\tTEST\t1\t1\t{count}\t{count}\n')
        Image.new('RGB', (8, 8), 'white').save(folder / f'{DNA}_{solution}_cancan_result.png')
    plan = selected_plan(actual_sources, cnv_source='cancan', cnv_solution='alt01')
    result = import_plan(plan, actor, tmp_path / 'archive')
    assert result.items[0].status == 'imported', result
    document = ReportRecord.objects.get().report_data
    table = next(t for t in document['sourceTables'] if t['kind'] == 'CNV')
    assert 'gene.name' in table['headers'] and 'Gene_Symbol' not in table['headers']
    assert table['rows'][0]['values'][7] == '3'
    assert not table['rows'][0]['sourceApproved']
    assert any('Ploidy: 3' in line for line in table['preamble'])
    assert ImportSource.objects.filter(role='cancan_table').count() == 1
    assert document['attachments'][0]['name'] == f'{DNA}_alt01_cancan_result.png'
    assert ReportAsset.objects.count() == 1
    assert any(d['code'] == 'IMPORT_CONFIGURATION' and 'alt01' in d['message'] for d in document['diagnostics'])


def test_signature_and_rna_profile_plot_roles_are_distinct():
    from pronto_report.renderers.review_v3 import plot_kind
    assert plot_kind({'name': 'opaque.pdf', 'description': 'Mutasjonssignatur'}) == 'signatures'
    assert plot_kind({'name': 'opaque.pdf', 'description': 'RNA-profil'}) == 'rna'
    assert plot_kind({'name': f'{DNA}_joint_mutational_signature.pdf'}) == 'signatures'
    assert plot_kind({'name': f'{RNA}_RNA_profiles.pdf'}) == 'rna'


@pytest.mark.parametrize('modern_review', [False, True])
def test_signature_and_rna_profiles_render_in_separate_sections(modern_review):
    from pronto.tests.reporting.test_html_review_state import draft_review
    from pronto.tests.reporting.test_html_surfaces import ONE_PIXEL_PNG
    from pronto.tests.reporting.test_pronto_output_adapter import build_report
    from pronto_report.migration import migrate_review_state_to_v3
    from pronto_report.renderers.html import render_html
    report = replace(build_report(), attachments=(
        {'assetId': 'signature', 'name': f'{DNA}_joint_mutational_signature.pdf', 'description': 'Mutasjonssignatur',
         'mediaType': 'application/pdf', 'sha256': 'a' * 64},
        {'assetId': 'rna-profile', 'name': f'{RNA}_RNA_profiles.pdf', 'description': 'RNA-profil',
         'mediaType': 'application/pdf', 'sha256': 'b' * 64}))
    review = migrate_review_state_to_v3(draft_review(report)) if modern_review else None
    html = render_html(report, review, plot_images={key: (('image/png', ONE_PIXEL_PNG),) for key in ('signature', 'rna-profile')})
    key = html.split('id="panel-key-findings"', 1)[1].split('<section class="report-panel"', 1)[0]
    rna = html.split('id="panel-rna-review"', 1)[1].split('<section class="report-panel"', 1)[0]
    assert 'joint_mutational_signature' in key
    assert '_RNA_profiles.pdf' in rna
    assert 'joint_mutational_signature' not in rna
    assert '_RNA_profiles.pdf' not in key


def test_cancan_display_and_saved_export_keep_gene_and_copy_number_without_fold_change(tmp_path):
    import json
    from pronto.tests.reporting.test_html_review_state import draft_review
    from pronto.tests.reporting.test_pronto_output_adapter import build_report
    from pronto_report.adapters.cancan import read_cancan_table
    from pronto_report.migration import migrate_review_state_to_v3
    from pronto_report.renderers.report_pdf import project_report_export
    from pronto_report.renderers.review_v4 import cnv_row
    from pronto_report.serialization import serialize_report_data, serialize_review_state
    from pronto_report.validation import validate_report_data, validate_review_state
    path = write(tmp_path / 'synthetic.tsv', f'# Sampleid: {DNA}\nchr\tgene.name\ttotal.cn\n7\tSYNTHETIC-GENE\t3\n')
    table = read_cancan_table(path, sample_id=DNA)
    document = json.loads(serialize_report_data(build_report()))
    document['sourceTables'].append(table)
    report = validate_report_data(document)
    review_document = json.loads(serialize_review_state(migrate_review_state_to_v3(draft_review(report))))
    review_document['findingReviews'] = [{'findingId': table['rows'][0]['findingId'],
                                         'reportingDecision': 'INCLUDE', 'reportHighlight': True}]
    review = validate_review_state(review_document, report=report)
    fields = project_report_export(report, review)['cnv'][0]['fields']
    assert fields['Gene_Symbol'] == 'SYNTHETIC-GENE'
    assert fields['Chromosome'] == '7'
    assert fields['Tumor_CN'] == '3'
    assert 'Tumor_FC' not in fields
    markup = cnv_row(table, table['rows'][0], {}, True)
    assert 'data-source-label="SYNTHETIC-GENE' in markup
    assert 'gene.name' in table['headers'] and 'Gene_Symbol' not in table['headers']


@pytest.mark.parametrize('claim', ['', '# Sampleid: WRONG\n'])
def test_cancan_requires_exact_sample_declaration(tmp_path, claim):
    from pronto_report.adapters.cancan import read_cancan_table
    path = write(tmp_path / 'synthetic.tsv', claim + 'chr\tgene.name\ttotal.cn\n1\tTEST\t2\n')
    with pytest.raises(ValueError):
        read_cancan_table(path, sample_id=DNA)


@pytest.mark.django_db
def test_manual_cnv_from_previous_run_cannot_be_imported_into_current_run(actual_sources, tmp_path, django_user_model):
    from pronto_ingest.discovery import assign_source
    from pronto_web.reports.models import ReportRecord
    actor = django_user_model.objects.create_user(username='operator')
    source = actual_sources['raw'] / DNA / f'{DNA}_merged_CNV_summary_FC_sorted.tsv'
    previous = source.parents[2] / OLD_RUN / DNA / source.name
    write(previous, source.read_text())
    plan = discover_folders((source.parents[2],))
    report = plan.reports[0]
    plan = assign_source(plan, report.key, 'cnv_table', previous)
    plan = set_report_selected(plan, report.key, True)
    result = import_plan(plan, actor, tmp_path / 'archive')
    assert result.items[0].status == 'failed'
    assert not ReportRecord.objects.exists()


@pytest.mark.django_db
def test_rna_row_with_conflicting_identity_columns_is_not_imported(actual_sources, tmp_path, django_user_model):
    from pronto_web.reports.models import ReportRecord
    actor = django_user_model.objects.create_user(username='operator')
    path = actual_sources['raw'] / DNA / f'{RNA}_fusion_and_splice_variant_candidates.tsv'
    write(path, 'Provisional_Event_Type\tSample_ID\tsample_id\tGene_A\n'
          f'Fusion\t{RNA}\tOTHER-RNA\tTEST\n')
    plan = discover_folders(tuple(actual_sources.values()))
    assert not plan.reports[0].ready
    assert any('rna_table' in issue for issue in plan.reports[0].issues)
    # Import also rejects the row if a caller bypasses the discovery warning.
    report = replace(plan.reports[0], issues=(), selected=True, selection_confirmed=True)
    result = import_plan(replace(plan, reports=(report,)), actor, tmp_path / 'archive')
    assert result.items[0].status == 'failed'
    assert not ReportRecord.objects.exists()


@pytest.mark.parametrize('family,role', [('_TSO_500_LocalApp_postprocessing_results', 'cnv_table'),
                                      ('-Report-preQC-NewPRONTO-Version', 'variants')])
def test_import_scope_accepts_known_run_folder_aliases(tmp_path, family, role):
    from pronto_ingest.contracts import ReportPlan
    from pronto_ingest.importer import _validate_run_scope
    plan = ReportPlan(DNA, RUN, profile='tsoppi-run-v1', report_version='new')
    _validate_run_scope(tmp_path / (RUN + family) / DNA / 'synthetic.tsv', role, plan)


@pytest.mark.parametrize('name,role', [(f'{DNA}-MAIN-gene-table-v2.TSV', 'cancan_table'),
                                     (f'{DNA}-main-Cancan-result-v2.PNG', 'cnv_plot')])
def test_import_filename_accepts_role_aliases_with_exact_sample(tmp_path, name, role):
    from pronto_ingest.contracts import ReportPlan
    from pronto_ingest.importer import _filename_identity
    plan = ReportPlan(DNA, RUN, profile='tsoppi-run-v1', report_version='new', cnv_source='cancan')
    _filename_identity(tmp_path / DNA / name, role, plan, {DNA, RNA})


@pytest.mark.django_db
def test_aliases_import_automatically_without_manual_file_assignment(actual_sources, tmp_path, django_user_model):
    from pronto_web.reports.models import ImportSource, ReportRecord
    actor = django_user_model.objects.create_user(username='operator')
    raw = actual_sources['raw']
    (raw / 'InPreD_PRONTO_metadata_tsoppi.txt').rename(raw / 'Clinical_metadata.txt')
    (raw / f'{RUN}_variant_summary.tsv').rename(raw / 'variant-summary.txt')
    variant = actual_sources['new'] / DNA / f'{DNA}_small_variant_table_forQC.tsv'
    variant.rename(variant.with_name(f'{DNA}-small-variant-table-forQC-v2.TXT'))
    plan = selected_plan(actual_sources)
    result = import_plan(plan, actor, tmp_path / 'archive')
    assert result.items[0].status == 'imported', result
    assert ReportRecord.objects.get().report_data['sample']['sampleId'] == DNA
    assert ImportSource.objects.get(role='variants').original_name.endswith('forQC-v2.TXT')


@pytest.mark.django_db
def test_csv_primary_alias_keeps_original_table_and_hash(actual_sources, tmp_path, django_user_model):
    from hashlib import sha256
    from pronto_web.reports.models import ReportRecord
    actor = django_user_model.objects.create_user(username='operator')
    path = actual_sources['new'] / DNA / f'{DNA}_small_variant_table_forQC.tsv'
    target = path.with_name(f'{DNA}_small_variant_table_forQC_v2.csv')
    write(target, path.read_text().replace('\t', ';'))
    path.unlink()
    result = import_plan(selected_plan(actual_sources), actor, tmp_path / 'archive')
    assert result.items[0].status == 'imported', result
    table = ReportRecord.objects.get().report_data['sourceTables'][0]
    assert table['fileName'] == target.name
    assert table['sha256'] == sha256(target.read_bytes()).hexdigest()
    assert table['headers'] == ['Sample_ID', 'Gene_symbol', 'Genomic_location', 'DNA_change', 'Change_summary']
    assert table['rows'][0]['values'][-1] == 'Synthetic change'


@pytest.mark.parametrize('name,role', [('OTHER-small-variant-table-forQC-v2.TXT', 'variants'),
                                     ('OTHER-merged-CNV-summary-FC-sorted-v2.TSV', 'cnv_table'),
                                     ('OTHER-sample-QC-plot-v2.PNG', 'qc_plot'),
                                     ('OTHER-fusion-and-splice-variant-candidates-withQC-v2.xlsx', 'rna_table')])
def test_manual_alias_with_explicit_foreign_sample_is_rejected(tmp_path, name, role):
    from pronto_ingest.contracts import ReportPlan
    from pronto_ingest.importer import _filename_identity, ImportProblem
    plan = ReportPlan(DNA, RUN, profile='tsoppi-run-v1', report_version='new')
    with pytest.raises(ImportProblem):
        _filename_identity(tmp_path / DNA / name, role, plan, {DNA, RNA})


@pytest.mark.django_db
def test_generic_analysis_summary_name_uses_content_and_run_scope(actual_sources, tmp_path, django_user_model):
    actor = django_user_model.objects.create_user(username='operator')
    source = actual_sources['raw'] / f'{RUN}_variant_summary.tsv'
    source.rename(source.with_name('analysis_variant_summary.tsv'))
    result = import_plan(selected_plan(actual_sources), actor, tmp_path / 'archive')
    assert result.items[0].status == 'imported', result


def test_nested_foreign_run_cannot_hide_inside_current_run(tmp_path):
    from pronto_ingest.contracts import ReportPlan
    from pronto_ingest.importer import _validate_run_scope, ImportProblem
    plan = ReportPlan(DNA, RUN, profile='tsoppi-run-v1', report_version='new')
    source = tmp_path / RUN / DNA / OLD_RUN / DNA / 'synthetic.tsv'
    with pytest.raises(ImportProblem):
        _validate_run_scope(source, 'cnv_table', plan)


@pytest.mark.django_db
def test_quoted_multiline_primary_cell_survives_canonicalisation(actual_sources, tmp_path, django_user_model):
    import csv
    from pronto_web.reports.models import ReportRecord
    actor = django_user_model.objects.create_user(username='operator')
    path = actual_sources['new'] / DNA / f'{DNA}_small_variant_table_forQC.tsv'
    target = path.with_suffix('.csv')
    expected = 'First line\n#clinical content\nLast line'
    with target.open('w', encoding='utf-8', newline='') as stream:
        stream.write('# Synthetic /hg19/TR\n')
        writer = csv.writer(stream, delimiter=';')
        writer.writerow(['Sample_ID', 'Gene_symbol', 'Genomic_location', 'DNA_change', 'Change_summary'])
        writer.writerow([DNA, 'TEST', '1:123', 'A>G', expected])
    path.unlink()
    result = import_plan(selected_plan(actual_sources), actor, tmp_path / 'archive')
    assert result.items[0].status == 'imported', result
    document = ReportRecord.objects.get().report_data
    assert document['variants'][0]['source']['rawValue'] == expected
    assert document['sourceTables'][0]['rows'][0]['values'][-1] == expected
