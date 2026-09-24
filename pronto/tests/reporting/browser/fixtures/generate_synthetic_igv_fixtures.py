"""Regenerate non-clinical chr22 BAM/reference fixtures with pysam 0.24.1."""

from pathlib import Path
import pysam


root = Path(__file__).resolve().parent
reference = root / "synthetic-chr22.fa"
reference.write_text(">chr22\n" + "A" * 200 + "\n", encoding="ascii")
pysam.faidx(str(reference))

bam = root / "synthetic-chr22.bam"
with pysam.AlignmentFile(str(bam), "wb", header={"HD": {"VN": "1.6", "SO": "coordinate"},
                                                  "SQ": [{"SN": "chr22", "LN": 200}]}) as output:
    read = pysam.AlignedSegment()
    read.query_name = "synthetic-read"
    read.query_sequence = "A" * 50
    read.flag = 0
    read.reference_id = 0
    read.reference_start = 79
    read.mapping_quality = 60
    read.cigar = ((0, 50),)
    read.query_qualities = pysam.qualitystring_to_array("I" * 50)
    output.write(read)
pysam.index(str(bam))
