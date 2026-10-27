import json

import pytest


def test_known_export_header_and_quoted_preamble(tmp_path):
    from pronto_ingest.discovery import table_rows
    path = tmp_path / 'metadata.txt'
    joined = 'Version_string_TSOPPI_reported_on_mol-MDT  Molecular_pathology_comment  Sample_info_comment'
    path.write_text('"# quoted export comment"\t\t\nSample_id\tSequencing_run_id\tStudy_id\t' + joined +
                    '\nDNA\tRUN\tSTUDY\tv1\tcomment\tinfo\n', encoding='utf-8')
    row = table_rows(path)[0]
    assert row['Study_id'] == 'STUDY' and row['Sample_info_comment'] == 'info'
    assert row['Molecular_pathology_comment'] == 'comment'
    path.write_text('Sample_id\tSequencing_run_id\tStudy_id\t' + joined +
                    '\nDNA\tRUN\tSTUDY\tv1\n', encoding='utf-8')
    historical = table_rows(path)[0]
    assert historical['Molecular_pathology_comment'] == historical['Sample_info_comment'] == ''
    path.write_text('Sample_id\tSequencing_run_id\tStudy_id\t' + joined +
                    '\nDNA\tRUN\tSTUDY\tv1\tonly-one-extra\n', encoding='utf-8')
    with pytest.raises(ValueError):
        table_rows(path)
    path.write_text('Gene\tComment\n"#VALUE"\tkept\n', encoding='utf-8')
    assert table_rows(path) == [{'Gene': '#VALUE', 'Comment': 'kept'}]


def test_rna_none_with_the_matched_comment(tmp_path):
    from pronto_ingest.linkage import resolve_links
    path = tmp_path / 'variants.tsv'
    path.write_text('# [DNA] ID of the matched tumor RNA sample: NA\nGene_symbol\nTEST\n')
    assert resolve_links('DNA', {'variants': (path,)}) == {'DNA'}


def test_new_database_preparation_never_overwrites_existing(tmp_path, monkeypatch):
    from pronto_desktop.runtime import DesktopRuntime
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'profile'))
    runtime = DesktopRuntime(data_root=tmp_path / 'current')
    target = tmp_path / 'empty'
    runtime.prepare_empty_database(target)
    config = json.loads(runtime.config_path.read_text())
    assert config['new_database'] and config['data_root'] == str(target.resolve())
    assert not list(target.iterdir())
    (target / 'keep.txt').write_text('keep')
    with pytest.raises(ValueError):
        runtime.prepare_empty_database(target)
    assert (target / 'keep.txt').read_text() == 'keep'


def test_biomarker_workbook_header_and_exact_gene_markup(tmp_path, settings):
    from openpyxl import Workbook
    from pronto_report.review.biomarker_list import read_biomarker_list
    from pronto_report.review.gene_registry import gene_markup
    book = Workbook()
    sheet = book.active
    sheet.append(['Molekylær markør', 'Biomarkør_spesifikasjon', 'Inclusion status_Sept2026'])
    sheet.append(['BRAF', 'V600 mut', 'Aktiv'])
    sheet.append(['CDKN2A/B', 'deletion', 'Aktiv'])
    sheet.append(['Tumor mutation burden (TMB)', 'TMB >16', 'Aktiv'])
    path = tmp_path / 'markers.xlsx'
    book.save(path)
    data = read_biomarker_list(path)
    assert data['genes'] == ['BRAF', 'CDKN2A', 'CDKN2B']
    settings.PRONTO_BIOMARKER_GENES = frozenset(data['genes'])
    assert gene_markup('BRAF') == '<strong>BRAF</strong>'
    assert gene_markup('BRAF2') == 'BRAF2'
    assert gene_markup('<script>') == '&lt;script&gt;'


def test_patient_label_accepts_supplied_display_identifiers():
    from pronto.tests.reporting.test_pronto_output_adapter import build_report
    from pronto_report.serialization import serialize_report_data
    from pronto_report.validation import validate_report_data, ContractValidationError
    data = json.loads(serialize_report_data(build_report()))
    data['sample']['patientPseudonym'] = 'STUDY-A-1234/ SAMPLE99'
    assert validate_report_data(data).sample['patientPseudonym'] == 'STUDY-A-1234/ SAMPLE99'
    data['sample']['patientPseudonym'] = 'BAD\nID'
    with pytest.raises(ContractValidationError):
        validate_report_data(data)


def test_long_pdf_plots_are_rendered_in_bounded_batches(monkeypatch):
    from pronto_report.renderers import pdfium
    monkeypatch.setattr(pdfium, 'available', lambda: False)
    import pdf2image
    from PIL import Image
    from pronto_report.renderers.assets import _pdf_pages
    calls = []
    monkeypatch.setattr(pdf2image, 'pdfinfo_from_bytes', lambda payload: {'Pages': 57})

    def convert(payload, **options):
        calls.append((options['first_page'], options['last_page']))
        return [Image.new('RGB', (8, 8)) for _ in range(options['first_page'], options['last_page'] + 1)]

    monkeypatch.setattr(pdf2image, 'convert_from_bytes', convert)
    assert len(_pdf_pages(b'pdf')) == 57
    assert calls[0] == (1, 5) and calls[-1] == (56, 57)
    assert all(last - first < 5 for first, last in calls)
    monkeypatch.setattr(pdf2image, 'pdfinfo_from_bytes', lambda payload: {'Pages': 101})
    with pytest.raises(ValueError):
        _pdf_pages(b'pdf')
    assert len(calls) == 12
