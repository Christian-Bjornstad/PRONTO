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


def test_reviewed_rna_in_fusion_splice_folder_is_preferred(actual_run):
    qc=actual_run['raw'].parent / (RUN+'_report_withQC')
    source=write(qc/'Fusion_splice'/DNA/f'{RNA}_fusion_and_splice_variant_candidates_withQC.tsv',
                 f'Provisional_Event_Type\tSample_ID\tGene_A\nFusion\t{RNA}\tTEST\n')
    report=discover_folders((actual_run['raw'].parent,)).reports[0]
    assert report.ready
    assert report.report_version=='new'
    assert report.files['rna_table']==(source,)


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


@pytest.mark.parametrize('name', ['InPreD_PRONTO_metadata.txt', 'clinical-metadata-v2.txt'])
def test_metadata_filename_uses_headers_inside_declared_run(actual_run, name):
    original = actual_run['raw'] / 'InPreD_PRONTO_metadata_tsoppi.txt'
    original.rename(original.with_name(name))
    plan = discover_folders((actual_run['raw'].parent,))
    assert plan.profile == 'tsoppi-run-v1'
    assert len(plan.reports) == 1 and plan.reports[0].ready
    assert plan.reports[0].files['metadata'][0].name == name


def test_summary_can_have_generic_name_inside_exact_run(actual_run):
    original = actual_run['raw'] / f'{RUN}_variant_summary.tsv'
    original.rename(original.with_name('variant_summary.tsv'))
    plan = discover_folders((actual_run['raw'].parent,))
    assert plan.profile == 'tsoppi-run-v1'
    assert plan.reports[0].ready
    assert plan.reports[0].files['summary'][0].name == 'variant_summary.tsv'


def test_raw_tso_folder_and_case_separator_report_aliases(actual_run):
    parent = actual_run['raw'].parent
    actual_run['raw'].rename(parent / (RUN + '_TSO_500_LocalApp_postprocessing_results'))
    actual_run['new'].rename(parent / (RUN + '-REPORT-preQC-newPRONTO-version'))
    report = discover_folders((parent,)).reports[0]
    assert report.ready and report.report_version == 'new'


def test_known_file_role_aliases_accept_case_separators_and_version_suffix(actual_run):
    source = actual_run['new'] / DNA / f'{DNA}_small_variant_table_forQC.tsv'
    source.rename(source.with_name(f'{DNA}-SMALL-variant-table-for-QC-v2.TSV'))
    cnv = actual_run['raw'] / DNA / f'{DNA}_merged_CNV_summary_FC_sorted.tsv'
    cnv.rename(cnv.with_name(f'{DNA}_merged_cnv_summary_fc_sorted_v2.tsv'))
    plot = actual_run['raw'] / DNA / f'{RNA}_RNA_profiles.pdf'
    plot.rename(plot.with_name(f'{RNA}-rna-profiles-v2.PDF'))
    report = discover_folders((actual_run['raw'].parent,)).reports[0]
    assert report.ready
    assert report.files['variants'][0].name.endswith('-v2.TSV')
    assert report.files['cnv_table'][0].name.endswith('fc_sorted_v2.tsv')
    assert report.files['rna_profile_plot'][0].name.endswith('-v2.PDF')


def test_unprefixed_known_support_files_are_scoped_by_dna_directory(actual_run):
    source = write(actual_run['new'] / DNA / 'extra_files' / 'sequence_summary.txt', 'source only')
    report = discover_folders((actual_run['raw'].parent,)).reports[0]
    assert source in report.files['supporting']


def test_rna_withqc_workbook_is_found_from_exact_sample_rows(actual_run):
    from openpyxl import Workbook
    raw = actual_run['raw'] / DNA / f'{RNA}_fusion_and_splice_variant_candidates.tsv'
    raw.unlink()
    path = raw.with_name(f'{RNA}_fusion_and_splice_variant_candidates_withQC.xlsx')
    book = Workbook()
    book.active.append(['Provisional_Event_Type', 'Sample_ID', 'Gene_A'])
    book.active.append(['Fusion', RNA, 'TEST'])
    book.save(path)
    report = discover_folders((actual_run['raw'].parent,)).reports[0]
    assert report.ready and report.files['rna_table'] == (path,)


def test_summary_declaring_another_run_never_binds_by_matching_sample(actual_run):
    original = actual_run['raw'] / f'{RUN}_variant_summary.tsv'
    original.rename(original.with_name(f'{OLD_RUN}_variant_summary.tsv'))
    plan = discover_folders((actual_run['raw'].parent,))
    assert plan.profile == 'tsoppi-run-v1'
    assert not plan.reports[0].ready
    assert not plan.reports[0].files.get('summary')


def test_variant_alias_with_wrong_patient_rows_is_blocked(actual_run):
    path = actual_run['new'] / DNA / f'{DNA}_small_variant_table_forQC.tsv'
    write(path, f'Sample_ID\tGene_symbol\tGenomic_location\tDNA_change\n{OTHER}\tTEST\t1:1\tA>G\n')
    report = discover_folders((actual_run['raw'].parent,)).reports[0]
    assert not report.ready
    assert any('prøve-ID' in issue for issue in report.issues)


def test_two_different_forqc_aliases_remain_ambiguous(actual_run):
    path = actual_run['new'] / DNA / f'{DNA}_small_variant_table_forQC.tsv'
    write(path.with_name(f'{DNA}_small_variant_table_forQC_v2.tsv'), path.read_text() + 'OTHER\t1:2\tA>G\n')
    report = discover_folders((actual_run['raw'].parent,)).reports[0]
    assert not report.ready
    assert len(report.files['variants']) == 2


def test_foreign_variant_filename_is_not_a_generic_header_fallback(actual_run):
    path = actual_run['new'] / DNA / f'{DNA}_small_variant_table_forQC.tsv'
    path.unlink()
    write(path.with_name(f'{OTHER}_small_variant_table_forQC_v2.tsv'),
          f'Sample_ID\tGene_symbol\tGenomic_location\tDNA_change\n{DNA}\tTEST\t1:1\tA>G\n')
    report = discover_folders((actual_run['raw'].parent,)).reports[0]
    assert not report.ready and not report.files.get('variants')


def test_foreign_cnv_filename_is_not_a_generic_header_fallback(actual_run):
    for name in ('FC', 'fraction'):
        (actual_run['raw'] / DNA / f'{DNA}_merged_CNV_summary_{name}_sorted.tsv').unlink()
    write(actual_run['raw'] / DNA / f'{OTHER}_merged_CNV_summary_FC_sorted_v2.tsv',
          'Gene_Symbol\tChromosome\tGene_Start\nTEST\t1\t1\n')
    report = discover_folders((actual_run['raw'].parent,)).reports[0]
    assert 'cnv_table' not in report.files


def test_generic_variant_table_requires_exact_row_identity_and_not_clinical_subset(actual_run):
    original = actual_run['new'] / DNA / f'{DNA}_small_variant_table_forQC.tsv'
    original.unlink()
    generic = write(original.with_name('variants.csv'),
                    f'Sample_ID,Gene_symbol,Genomic_location,DNA_change\n{DNA},TEST,1:1,A>G\n')
    report = discover_folders((actual_run['raw'].parent,)).reports[0]
    assert report.ready and report.files['variants'] == (generic,)
    generic.rename(generic.with_name('variants_blacklisted.csv'))
    report = discover_folders((actual_run['raw'].parent,)).reports[0]
    assert not report.ready and 'variants' not in report.files


def test_sample_identifier_case_is_not_normalised_with_role_words(actual_run):
    source = actual_run['new'] / DNA / f'{DNA}_small_variant_table_forQC.tsv'
    # Use a different case in a temporary intermediate basename as Windows
    # itself treats case-only rename operations specially.
    temporary = source.with_name('renaming.tsv')
    source.rename(temporary)
    temporary.rename(source.with_name(f'{DNA.lower()}_small_variant_table_forQC.tsv'))
    report = discover_folders((actual_run['raw'].parent,)).reports[0]
    assert not report.ready and not report.files.get('variants')


def test_table_reader_preserves_comment_and_blank_lines_inside_quoted_csv_cells(tmp_path):
    from pronto_ingest.discovery import table_rows
    source = write(tmp_path / 'synthetic.csv',
                   '# leading comment with an unmatched " quote\n'
                   'Sample_ID,Gene_symbol,Change_summary\n'
                   f'{DNA},TEST,"line1\n# source annotation\n\nline4"\n'
                   '# another outside-record comment with " quote\n')
    source.write_bytes(source.read_text().encode('utf-8'))
    rows = table_rows(source, header={'Sample_ID', 'Gene_symbol', 'Change_summary'})
    assert rows == [{'Sample_ID': DNA, 'Gene_symbol': 'TEST',
                     'Change_summary': 'line1\n# source annotation\n\nline4'}]


def test_nested_foreign_run_is_not_an_automatic_cancan_source(actual_run):
    folder = actual_run['cnv'] / DNA / OLD_RUN / DNA
    write(folder / f'{DNA}_main_gene_table.tsv',
          f'# Sample id: {DNA}\nchr\tgene.name\ttotal.cn\n1\tTEST\t2\n')
    write(folder / f'{DNA}_main_cancan_result.png', 'synthetic')
    report = discover_folders((actual_run['raw'].parent,), cnv_source='cancan').reports[0]
    assert not report.ready
    assert not report.files.get('cancan_table') and not report.files.get('cnv_plot')


@pytest.mark.parametrize('selected_role', ['variants', 'cnv_table'])
def test_manual_mapping_cannot_clear_wrong_variant_row_identity(actual_run, selected_role):
    from pronto_ingest.discovery import assign_source
    source = actual_run['new'] / DNA / f'{DNA}_small_variant_table_forQC.tsv'
    write(source, f'Sample_ID\tGene_symbol\tGenomic_location\tDNA_change\n{OTHER}\tTEST\t1:1\tA>G\n')
    plan = discover_folders((actual_run['raw'].parent,))
    report = plan.reports[0]
    chosen = assign_source(plan, report.key, selected_role, report.files[selected_role][0])
    assert not chosen.reports[0].ready
    assert any('prøve-ID' in issue for issue in chosen.reports[0].issues)


def test_explicit_metadata_file_choice_recomputes_current_run_flag(actual_run):
    from pronto_ingest.discovery import assign_source
    original = actual_run['raw'] / 'InPreD_PRONTO_metadata_tsoppi.txt'
    positive = write(original.with_name('clinical_metadata_v2.txt'),
                     original.read_text().replace(f'{DNA}\t{RUN}\tTEST\t-', f'{DNA}\t{RUN}\tTEST\tY'))
    plan = discover_folders((actual_run['raw'].parent,))
    report = plan.reports[0]
    assert not report.ready
    chosen = assign_source(plan, report.key, 'metadata', positive)
    report = chosen.reports[0]
    assert report.ready and report.metadata_flag == 'Y' and report.selected


def test_choosing_negative_metadata_clears_explicit_sample_selection(actual_run):
    from pronto_ingest.discovery import assign_source, set_report_selected
    original = actual_run['raw'] / 'InPreD_PRONTO_metadata_tsoppi.txt'
    negative = write(original.with_name('clinical_metadata_v2.txt'),
                     original.read_text().replace(f'{DNA}\t{RUN}\tTEST\t-', f'{DNA}\t{RUN}\tTEST\tNO'))
    plan = discover_folders((actual_run['raw'].parent,))
    key = plan.reports[0].key
    plan = assign_source(plan, key, 'metadata', original)
    plan = set_report_selected(plan, key, True)
    plan = assign_source(plan, key, 'metadata', negative)
    report = plan.reports[0]
    assert report.metadata_flag == 'NO'
    assert not report.selected and not report.selection_confirmed
    with pytest.raises(ValueError):
        set_report_selected(plan, key, True)


def test_duplicate_current_metadata_rows_remain_blocked_after_mapping(actual_run):
    from pronto_ingest.discovery import assign_source
    original = actual_run['raw'] / 'InPreD_PRONTO_metadata_tsoppi.txt'
    with original.open('a') as stream:
        stream.write(f'{DNA}\t{RUN}\tTEST\t-\n')
    plan = discover_folders((actual_run['raw'].parent,))
    chosen = assign_source(plan, plan.reports[0].key, 'metadata', original)
    assert not chosen.reports[0].ready
    assert any('metadata' in issue.lower() for issue in chosen.reports[0].issues)


def test_legacy_plot_classification_still_accepts_established_substring_names(tmp_path):
    from pronto_ingest.discovery import _role
    assert _role(tmp_path / f'{DNA}_Cancan_plot.png') == 'cnv_plot'
    assert _role(tmp_path / f'{DNA}_sample_QC_plot_extra.pdf') == 'qc_plot'
    assert _role(tmp_path / f'{DNA}_domain_plot_extra.pdf') == 'other_plot'
