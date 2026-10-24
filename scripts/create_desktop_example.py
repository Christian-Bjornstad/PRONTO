"""Create a synthetic four-folder TSOPPI run in a new directory."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

RUN = '261024_A00000_0001_ASYNTHETIC'
SAMPLE = 'SYN0001-D01-P01-A01'
RNA = 'SYN0001-R03-P01-A01'


def _table(path, headers, rows, preamble=''):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as stream:
        stream.write(preamble)
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        writer.writerow(headers)
        writer.writerows(rows)


def _pdf(path, title):
    from reportlab.pdfgen.canvas import Canvas
    canvas = Canvas(str(path), pagesize=(600, 360))
    canvas.setFillColorRGB(.09, .16, .22)
    canvas.setFont('Helvetica-Bold', 19)
    canvas.drawString(32, 314, title)
    canvas.setFont('Helvetica', 12)
    canvas.drawString(32, 286, 'Synthetic test data - no clinical interpretation')
    canvas.setStrokeColorRGB(.08, .45, .46)
    for index, value in enumerate((.3, .55, .4, .7, .6, .4, .5, .3)):
        x = 54 + index * 64
        canvas.line(x, 74, x, 74 + value * 220)
    canvas.showPage()
    canvas.save()


def create_example(output):
    """Return four roots; output must not already exist. No patient files are read."""
    from PIL import Image, ImageDraw

    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    folders = tuple(output / (RUN + suffix) for suffix in (
        '', '_CNVs', '_report_preQC', '_report_preQC_newPRONTO_version'))
    for folder in folders:
        folder.mkdir()
    raw, cnv, old, new = folders
    dna_dir = raw / SAMPLE
    dna_dir.mkdir()
    _table(raw / 'InPreD_PRONTO_metadata_tsoppi.txt',
           ['Sample_id', 'Sequencing_run_id', 'Create_report', 'Study_id', 'Clinical_diagnosis'], [
               [SAMPLE, '251001_A00000_0001_AHISTORICAL', 'Y', 'SYNTHETIC0001', '-'],
               [SAMPLE, RUN, '-', 'SYNTHETIC0001', '-'], [RNA, RUN, '-', 'SYNTHETIC0001', '-']],
           '# Synthetic historical metadata. Current DNA row requires explicit selection.\n')
    _table(raw / f'{RUN}_variant_summary.tsv',
           ['sample_id', 'TMB', 'MSI', 'gene_amplifications', 'splice_variants', 'fusions'],
           [[SAMPLE + '_P', '1.2', '0.3', '-', '-', '-'], [RNA + '_P', '-', '-', '-', '-', '-']])
    headers = ['Sample_ID', 'Gene_symbol', 'Genomic_location', 'DNA_change',
               'Change_summary', 'Protein_change_short', 'AF_tumor_DNA', 'Depth_tumor_DNA']
    rows = [[SAMPLE, 'TESTGENE', '7:100001', 'A>G', 'Synthetic source row', '-', '0.25', '800']]
    preamble = (f'# [{SAMPLE}] Synthetic TSOPPI /hg19/TR\n'
                f'# [{SAMPLE}] ID of matched tumor RNA sample: {RNA}\n'
                '# ID of the matched normal DNA sample: NA\n')
    _table(dna_dir / f'{SAMPLE}_small_variant_table.tsv', headers, rows, preamble)
    _table(dna_dir / f'{SAMPLE}_sample_concordance.tsv',
           ['HomHet_count', 'HomHet_matches', 'HomHet_concordance', 'Hom_count', 'Hom_matches', 'Hom_concordance'],
           [['10', '10', '1.0', '10', '10', '1.0']],
           f'# Concordance between processed [tumor DNA: "{SAMPLE}"] and [tumor RNA: "{RNA}"] samples:\n')
    for ordering in ('FC', 'fraction'):
        _table(dna_dir / f'{SAMPLE}_merged_CNV_summary_{ordering}_sorted.tsv',
               ['Chromosome', 'Gene_Start', 'Gene_Symbol', 'High_Confidence_Gene', 'Amplification_Reported', 'Tumor_FC'],
               [['7', '100000', 'TESTGENE', 'TRUE', 'FALSE', '1.1']])
    _table(dna_dir / f'{RNA}_fusion_and_splice_variant_candidates.tsv',
           ['Provisional_Event_Type', 'Event_Type', 'Sample_ID', 'Gene_A', 'Gene_B', 'Provisional_Event_ID'],
           [['Fusion', '.', RNA, 'TESTGENEA', 'TESTGENEB', 'SYN-FUSION-1']])
    _pdf(dna_dir / f'{SAMPLE}_CNV_overview_plots.pdf', 'CNV overview')
    _pdf(dna_dir / f'{SAMPLE}_joint_mutational_signature.pdf', 'Mutation signatures')
    _pdf(dna_dir / f'{RNA}_RNA_profiles.pdf', 'RNA profiles')
    for sample in (SAMPLE, RNA):
        image = Image.new('RGB', (720, 260), '#f4f7fa')
        draw = ImageDraw.Draw(image)
        draw.text((24, 24), f'{sample} - SYNTHETIC QC', fill='#152a3a')
        for index, value in enumerate((100, 140, 110, 160, 130)):
            x = 40 + index * 130
            draw.rectangle((x, 230-value, x+66, 230), fill='#08787b')
        image.save(dna_dir / f'{sample}_sample_QC_plot.png')
        _pdf(dna_dir / f'{sample}_sample_QC_plot.pdf', 'QC (PDF alternative)')
    cancan = cnv / SAMPLE / f'{SAMPLE}_Cancan_1.1.7'
    cancan.mkdir(parents=True)
    for solution in ('main', 'alt01', 'alt02'):
        _table(cancan / f'{SAMPLE}_{solution}_gene_table.tsv',
               ['chr', 'start.pos.gene', 'end.pos.gene', 'gene.id', 'gene.name',
                'start.pos.segment', 'end.pos.segment', 'minor.cn', 'major.cn', 'total.cn', 'cn.clonal'],
               [['7', '100000', '101000', 'SYNGENE1', 'TESTGENE', '90000', '110000', '1', '1', '2', '2']],
               f'#Sampleid: {SAMPLE}\n#Purity: 0.5\n#Ploidy: 2.0\n')
        image = Image.new('RGB', (720, 300), '#f4f7fa')
        ImageDraw.Draw(image).text((24, 24), f'SYNTHETIC Cancan {solution}', fill='#152a3a')
        image.save(cancan / f'{SAMPLE}_{solution}_cancan_result.png')
        (cancan / f'{SAMPLE}_{solution}_purity.txt').write_text('0.5\n', encoding='utf-8')
        (cancan / f'{SAMPLE}_{solution}_ploidy.txt').write_text('2.0\n', encoding='utf-8')
    for report_root in (old, new):
        report_dir = report_root / SAMPLE
        report_dir.mkdir()
        _table(report_dir / f'{SAMPLE}_small_variant_table_forQC.tsv', headers, rows, preamble)
        extra = report_dir / 'extra_files'
        extra.mkdir()
        (extra / f'{SAMPLE}_sequence_summary.txt').write_text('Synthetic supporting source only.\n', encoding='utf-8')
    return folders


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory; never overwrites existing files.')
    args = parser.parse_args()
    try:
        folders = create_example(args.output)
    except (FileExistsError, OSError):
        parser.exit(1, 'Choose a new writable output directory. Existing files were not replaced.\n')
    print('Synthetic four-folder example. Use a separate test database.')
    print('Select the parent folder in Importer, then select the DNA sample before import.')
    for folder in folders:
        print(folder)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
