from pathlib import Path

import pytest

from pronto_ingest.discovery import discover_folders


RUN = '261001_A00001_0001_AABCDEFGHI'
OLD_RUN = '250101_A00001_0001_AABCDEFGHI'
DNA = 'TEST-D01-P01-A01'
RNA = 'TEST-R03-P01-A01'
OTHER = 'OTHER-D01-P01-A01'


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


@pytest.fixture
def actual_run(tmp_path):
    roots = {key: tmp_path / (RUN + suffix) for key, suffix in (
        ('raw', ''), ('cnv', '_CNVs'), ('legacy', '_report_preQC'),
        ('new', '_report_preQC_newPRONTO_version'))}
    for folder in roots.values():
        (folder / DNA).mkdir(parents=True)
    write(roots['raw'] / 'InPreD_PRONTO_metadata_tsoppi.txt',
          'Sample_id\tSequencing_run_id\tStudy_id\tCreate_report\n'
          f'{OTHER}\t{OLD_RUN}\tTEST\tY\n{DNA}\t{RUN}\tTEST\t-\n{RNA}\t{RUN}\tTEST\tY\n')
    write(roots['raw'] / f'{RUN}_variant_summary.tsv',
          f'sample_id\tTMB\tMSI\n{DNA}_P\t3\t0\n{RNA}_P\t0\t0\n')
    variants = 'Gene_symbol\tGenomic_location\tDNA_change\nTEST\t1:123\tc.1A>G\n'
    write(roots['raw'] / DNA / f'{DNA}_small_variant_table.tsv',
          f'# [{DNA}] ID of matched tumor RNA sample: {RNA}\n' + variants)
    for version in ('new', 'legacy'):
        write(roots[version] / DNA / f'{DNA}_small_variant_table_forQC.tsv', variants)
        write(roots[version] / DNA / f'{DNA}_CNV_overview_plots.pdf', '%PDF-1.7\nsynthetic')
    write(roots['raw'] / DNA / f'{DNA}_sample_concordance.tsv',
          f'# Concordance between processed [tumor DNA: "{DNA}"] and [tumor RNA: "{RNA}"] samples:\n'
          'Metric\tValue\nConcordance\t1\n')
    cnv_text = 'Chromosome\tGene_Start\tGene_Symbol\tTumor_FC\n1\t1\tTEST\t2\n'
    for priority in ('FC', 'fraction'):
        write(roots['raw'] / DNA / f'{DNA}_merged_CNV_summary_{priority}_sorted.tsv', cnv_text)
    write(roots['raw'] / DNA / f'{RNA}_fusion_and_splice_variant_candidates.tsv',
          f'Provisional_Event_Type\tSample_ID\tGene_A\nFusion\t{RNA}\tTEST\n')
    for sample in (DNA, RNA):
        for suffix in ('png', 'pdf'):
            write(roots['raw'] / DNA / f'{sample}_sample_QC_plot.{suffix}', 'synthetic')
    write(roots['raw'] / DNA / f'{DNA}_joint_mutational_signature.pdf', '%PDF-1.7\nsynthetic')
    write(roots['raw'] / DNA / f'{RNA}_RNA_profiles.pdf', '%PDF-1.7\nsynthetic')
    return roots


def test_actual_parent_scopes_metadata_selects_one_version_and_explicit_links(actual_run):
    plan = discover_folders((actual_run['raw'].parent,))
    assert plan.profile == 'tsoppi-run-v1'
    assert plan.run_ids == (RUN,)
    assert len(plan.reports) == 1
    report = plan.reports[0]
    assert report.sample_id == DNA
    assert report.ready
    assert report.metadata_flag == '-'
    assert not report.selected and not report.selection_confirmed
    assert report.report_version == 'new'
    assert report.files['variants'] == (actual_run['new'] / DNA / f'{DNA}_small_variant_table_forQC.tsv',)
    assert report.files['cnv_table'][0].name.endswith('_FC_sorted.tsv')
    assert len(report.files['cnv_plot']) == 1
    assert all(path.suffix == '.png' for path in report.files['qc_plot'])
    assert len(report.files['qc_plot']) == 2
    assert len(report.files['linkage']) == 2
    assert report.files['signature_plot'][0].name == f'{DNA}_joint_mutational_signature.pdf'
    assert report.files['rna_profile_plot'][0].name == f'{RNA}_RNA_profiles.pdf'


def test_four_selected_folders_and_explicit_legacy_version(actual_run):
    plan = discover_folders(tuple(actual_run.values()), report_version='legacy')
    assert plan.reports[0].ready
    assert plan.reports[0].report_version == 'legacy'
    assert plan.reports[0].files['variants'][0].is_relative_to(actual_run['legacy'])


def test_missing_chosen_version_never_falls_back_per_sample(actual_run):
    (actual_run['new'] / DNA / f'{DNA}_small_variant_table_forQC.tsv').unlink()
    report = discover_folders(tuple(actual_run.values())).reports[0]
    assert report.report_version == 'new'
    assert not report.ready
    assert not report.files.get('variants')


def test_conflicting_linkage_blocks_discovery_and_resolver(actual_run):
    from pronto_ingest.linkage import resolve_links
    path = actual_run['raw'] / DNA / 'sample_list.tsv'
    write(path, f'sample_type\tsample_ID\ndna_tumor\t{DNA}\nrna_tumor\tOTHER-RNA\n')
    report = discover_folders(tuple(actual_run.values())).reports[0]
    assert not report.ready
    assert any('kobling' in issue.lower() for issue in report.issues)
    with pytest.raises(ValueError):
        resolve_links(DNA, report.files)


def test_unset_selection_requires_explicit_confirmation_and_negative_cannot_be_selected(actual_run):
    from pronto_ingest.discovery import set_report_selected
    plan = discover_folders(tuple(actual_run.values()))
    chosen = set_report_selected(plan, plan.reports[0].key, True)
    assert chosen.reports[0].selected and chosen.reports[0].selection_confirmed
    metadata = actual_run['raw'] / 'InPreD_PRONTO_metadata_tsoppi.txt'
    metadata.write_text(metadata.read_text().replace(f'{DNA}\t{RUN}\tTEST\t-', f'{DNA}\t{RUN}\tTEST\tNO'))
    plan = discover_folders(tuple(actual_run.values()))
    assert not plan.reports[0].selected
    with pytest.raises(ValueError):
        set_report_selected(plan, plan.reports[0].key, True)


def test_cancan_chooses_only_requested_solution(actual_run):
    folder = actual_run['cnv'] / DNA / f'{DNA}_Cancan_1.1.7'
    for solution in ('main', 'alt01', 'alt02'):
        write(folder / f'{DNA}_{solution}_gene_table.tsv',
              f'# Sample id: {DNA}\nchr\tgene.name\ttotal.cn\n1\tTEST\t2\n')
        write(folder / f'{DNA}_{solution}_cancan_result.png', 'synthetic')
    plan = discover_folders(tuple(actual_run.values()), cnv_source='cancan', cnv_solution='alt01')
    report = plan.reports[0]
    assert len(report.files['cancan_table']) == 1
    assert report.files['cancan_table'][0].name == f'{DNA}_alt01_gene_table.tsv'
    assert 'cnv_table' not in report.files
    assert report.files['cnv_plot'][0].name == f'{DNA}_alt01_cancan_result.png'


def test_supporting_text_only_from_selected_version_and_known_names(actual_run):
    for version in ('new', 'legacy'):
        write(actual_run[version] / DNA / 'extra_files' / f'{DNA}_Main_Findings.txt', 'source text')
    write(actual_run['new'] / DNA / 'extra_files' / 'unrelated.txt', 'unrelated')
    report = discover_folders(tuple(actual_run.values())).reports[0]
    assert report.files['supporting'] == (actual_run['new'] / DNA / 'extra_files' / f'{DNA}_Main_Findings.txt',)


@pytest.mark.parametrize('value', ['invalid', '../new'])
def test_unknown_report_version_is_rejected(actual_run, value):
    with pytest.raises(ValueError):
        discover_folders(tuple(actual_run.values()), report_version=value)


def test_explicit_raw_version_uses_raw_variants_and_profile_fallback(actual_run):
    (actual_run['raw'] / DNA / f'{DNA}_merged_CNV_summary_FC_sorted.tsv').unlink()
    report = discover_folders(tuple(actual_run.values()), report_version='raw').reports[0]
    assert report.ready
    assert report.report_version == 'raw'
    assert report.files['variants'][0].name == f'{DNA}_small_variant_table.tsv'
    assert report.files['cnv_table'][0].name.endswith('_fraction_sorted.tsv')


def test_missing_new_directory_chooses_legacy_for_entire_run(actual_run):
    import shutil
    shutil.rmtree(actual_run['new'])
    folders = tuple(folder for folder in actual_run.values() if folder.exists())
    report = discover_folders(folders).reports[0]
    assert report.ready and report.report_version == 'legacy'


def test_rna_never_becomes_report_even_with_own_directory(actual_run):
    (actual_run['raw'] / RNA).mkdir()
    plan = discover_folders(tuple(actual_run.values()))
    assert [report.sample_id for report in plan.reports] == [DNA]


def test_historical_metadata_cannot_attach_to_current_run_directory(actual_run):
    (actual_run['raw'] / OTHER).mkdir()
    plan = discover_folders(tuple(actual_run.values()))
    assert [report.sample_id for report in plan.reports] == [DNA]


def test_concordance_is_sufficient_without_raw_variant_linkage(actual_run):
    (actual_run['raw'] / DNA / f'{DNA}_small_variant_table.tsv').unlink()
    report = discover_folders(tuple(actual_run.values())).reports[0]
    assert report.ready
    assert report.files['linkage'] == (actual_run['raw'] / DNA / f'{DNA}_sample_concordance.tsv',)


def test_na_linkage_does_not_guess_rna_from_filename_or_parent(actual_run):
    for name in (f'{DNA}_small_variant_table.tsv', f'{DNA}_sample_concordance.tsv'):
        path = actual_run['raw'] / DNA / name
        path.write_text(path.read_text().replace(RNA, 'NA'))
    report = discover_folders(tuple(actual_run.values())).reports[0]
    assert report.ready
    assert 'rna_table' not in report.files and 'rna_profile_plot' not in report.files
    assert len(report.files['qc_plot']) == 1


def test_linkage_snapshot_content_is_revalidated_under_generic_archive_names(actual_run, tmp_path):
    from pronto_ingest.linkage import resolve_links
    import shutil
    archived = tmp_path / 'snapshot.bin'
    shutil.copy(actual_run['raw'] / DNA / f'{DNA}_sample_concordance.tsv', archived)
    assert resolve_links(DNA, {'linkage': (archived,)}) == {DNA, RNA}
    archived.write_text(archived.read_text().replace(DNA, OTHER))
    with pytest.raises(ValueError):
        resolve_links(DNA, {'linkage': (archived,)})


def test_no_explicit_linkage_is_not_ready(actual_run):
    for name in (f'{DNA}_small_variant_table.tsv', f'{DNA}_sample_concordance.tsv'):
        (actual_run['raw'] / DNA / name).unlink()
    report = discover_folders(tuple(actual_run.values())).reports[0]
    assert not report.ready
    assert any('kobling' in issue.lower() for issue in report.issues)


def test_generic_cnv_in_different_dna_parent_is_not_auto_bound(actual_run):
    own = actual_run['raw'] / DNA / f'{DNA}_merged_CNV_summary_FC_sorted.tsv'
    other = actual_run['raw'] / OTHER / own.name
    other.parent.mkdir()
    own.rename(other)
    (actual_run['raw'] / DNA / f'{DNA}_merged_CNV_summary_fraction_sorted.tsv').unlink()
    report = discover_folders(tuple(actual_run.values())).reports[0]
    assert 'cnv_table' not in report.files


def test_corrupt_unselected_candidate_does_not_discard_valid_sample(actual_run):
    write(actual_run['cnv'] / DNA / 'broken.xlsx', 'invalid ZIP')
    report = discover_folders(tuple(actual_run.values())).reports[0]
    assert report.ready


def test_arbitrary_four_folders_do_not_enable_actual_profile(tmp_path):
    folders = tuple(tmp_path / f'part-{i}' for i in range(4))
    for folder in folders:
        folder.mkdir()
    assert discover_folders(folders).profile == 'legacy'


@pytest.mark.parametrize('option,value', [('cnv_source', 'guess'), ('cnv_solution', 'alt99')])
def test_unknown_cnv_setting_is_rejected(actual_run, option, value):
    with pytest.raises(ValueError):
        discover_folders(tuple(actual_run.values()), **{option: value})


def test_conflicting_metadata_flag_stays_blocked_after_manual_source_choice(actual_run):
    from pronto_ingest.discovery import assign_source, set_report_selected
    metadata = actual_run['raw'] / 'InPreD_PRONTO_metadata_tsoppi.txt'
    with metadata.open('a') as stream:
        stream.write(f'{DNA}\t{RUN}\tTEST\tNO\n')
    plan = discover_folders(tuple(actual_run.values()))
    report = plan.reports[0]
    plan = assign_source(plan, report.key, 'variants', report.files['variants'][0])
    assert not plan.reports[0].ready
    with pytest.raises(ValueError):
        set_report_selected(plan, report.key, True)


def test_explicitly_linked_rna_without_r03_token_never_becomes_report(actual_run):
    explicit_rna = 'UNUSUAL-RNA-ID'
    for path in actual_run['raw'].rglob('*.tsv'):
        path.write_text(path.read_text().replace(RNA, explicit_rna))
    metadata = actual_run['raw'] / 'InPreD_PRONTO_metadata_tsoppi.txt'
    metadata.write_text(metadata.read_text().replace(RNA, explicit_rna))
    (actual_run['raw'] / explicit_rna).mkdir()
    assert [report.sample_id for report in discover_folders(tuple(actual_run.values())).reports] == [DNA]
