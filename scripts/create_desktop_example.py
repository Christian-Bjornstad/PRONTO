"""Arrange the existing approved OUS fixture into five new example folders."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'test_data/ous/251114_A02134_0115_BHCJCKDRX7_TSO_500_LocalApp_postprocessing_results'
SAMPLE = 'IPD2225-D01-P01-A08'


def create_example(output):
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    names = ('01_metadata', '02_summary', '03_variants', '04_plots', '05_additional')
    folders = [output / name for name in names]
    for folder in folders:
        folder.mkdir()
    shutil.copy2(FIXTURE / 'InPreD_PRONTO_metadata.txt', folders[0])
    shutil.copy2(next(FIXTURE.glob('*_variant_summary.tsv')), folders[1])
    for path in (FIXTURE / SAMPLE).iterdir():
        if path.name.endswith('_small_variant_table_forQC.tsv') or path.name == 'sample_list.tsv':
            shutil.copy2(path, folders[2])
        elif path.suffix.lower() == '.png' or path.name.endswith('_CNV_overview_plots.pdf'):
            shutil.copy2(path, folders[3])
    return folders


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory; never overwrites an existing one.')
    args = parser.parse_args()
    try:
        folders = create_example(args.output)
    except (FileExistsError, OSError):
        parser.exit(1, 'Choose a new writable output directory. Existing files were not replaced.\n')
    print('Approved OUS test example only. Use a separate test database.')
    for folder in folders:
        print(folder)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
