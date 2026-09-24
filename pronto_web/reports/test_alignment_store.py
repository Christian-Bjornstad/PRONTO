"""Synthetic-only tests for private pair validation and publication."""

from hashlib import sha256
from pathlib import Path
import pytest


try:
    import pysam
except ImportError:  # Native Windows is view-only; Django discovery still imports this module.
    pysam = None


@pytest.fixture
def pairs(tmp_path):
    if pysam is None:
        pytest.skip("pysam validation is Linux-only")
    reference = tmp_path / "reference.fa"
    reference.write_text(">chr22\n" + "A" * 200 + "\n", encoding="ascii")
    pysam.faidx(str(reference))
    bam = tmp_path / "reads.bam"
    with pysam.AlignmentFile(str(bam), "wb", header={
        "HD": {"VN": "1.6", "SO": "coordinate"},
        "SQ": [{"SN": "chr22", "LN": 200}],
    }) as output:
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
    cram = tmp_path / "reads.cram"
    with pysam.AlignmentFile(str(bam), "rb") as source, pysam.AlignmentFile(
        str(cram), "wc", header=source.header, reference_filename=str(reference)
    ) as output:
        for read in source:
            output.write(read)
    pysam.index(str(cram))
    return reference, bam, Path(str(bam) + ".bai"), cram, Path(str(cram) + ".crai")


def test_validates_bam_and_cram_with_index_and_reference(pairs):
    from pronto_web.reports.alignment_store import validate_pair

    reference, bam, bai, cram, crai = pairs
    assert validate_pair(bam, bai, "bam", reference).has_index
    assert validate_pair(cram, crai, "cram", reference).has_index


def test_rejects_disguised_format_corrupt_index_and_reference_mismatch(pairs, tmp_path):
    from pronto_web.reports.alignment_store import InvalidAlignmentPair, validate_pair

    reference, bam, bai, _, _ = pairs
    fake = tmp_path / "fake.bam"
    fake.write_text("not a BAM")
    bad_index = tmp_path / "bad.bai"
    bad_index.write_text("not an index")
    wrong_reference = tmp_path / "wrong.fa"
    wrong_reference.write_text(">chr22\n" + "A" * 201 + "\n", encoding="ascii")
    pysam.faidx(str(wrong_reference))
    for data, index, fasta in (
        (fake, bai, reference), (bam, bad_index, reference),
        (bam, bai, wrong_reference),
    ):
        with pytest.raises(InvalidAlignmentPair):
            validate_pair(data, index, "bam", fasta)


def test_pair_publication_is_atomic_and_checksums_match(pairs, tmp_path, monkeypatch):
    from pronto_web.reports import alignment_store

    _, bam, bai, _, _ = pairs
    root = tmp_path / "private"
    root.mkdir()
    published = alignment_store.publish_pair(bam, bai, root)
    assert published.data_path.read_bytes() == bam.read_bytes()
    assert sha256(published.data_path.read_bytes()).hexdigest() == published.data_sha256
    assert sha256(published.index_path.read_bytes()).hexdigest() == published.index_sha256
    assert len(list(root.iterdir())) == 1

    original = alignment_store._copy_to_private_file
    count = 0

    def fail_second(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("simulated index failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(alignment_store, "_copy_to_private_file", fail_second)
    with pytest.raises(OSError, match="simulated index failure"):
        alignment_store.publish_pair(bam, bai, root)
    assert list(root.iterdir()) == [published.directory]


def test_remove_pair_refuses_paths_outside_its_managed_root(pairs, tmp_path):
    from dataclasses import replace
    from pronto_web.reports.alignment_store import UnsafeAlignmentPath, publish_pair, remove_pair

    _, bam, bai, _, _ = pairs
    root = tmp_path / "private"
    root.mkdir()
    published = publish_pair(bam, bai, root)
    with pytest.raises(UnsafeAlignmentPath):
        remove_pair(replace(published, data_path=bam))
    assert published.data_path.exists()
    remove_pair(published)
    assert not published.directory.exists()


def test_publish_rejects_quota_and_symlink_source(pairs, tmp_path):
    from pronto_web.reports.alignment_store import (
        StorageLimitError, UnsafeAlignmentPath, publish_pair,
    )

    _, bam, bai, _, _ = pairs
    root = tmp_path / "private"
    root.mkdir()
    with pytest.raises(StorageLimitError):
        publish_pair(bam, bai, root, max_data_bytes=bam.stat().st_size - 1)
    linked = tmp_path / "linked.bam"
    linked.symlink_to(bam)
    with pytest.raises(UnsafeAlignmentPath):
        publish_pair(linked, bai, root)
    assert list(root.iterdir()) == []


def test_publication_rolls_back_if_directory_sync_fails(pairs, tmp_path, monkeypatch):
    from pronto_web.reports import alignment_store

    _, bam, bai, _, _ = pairs
    root = tmp_path / "private"
    root.mkdir()
    original = alignment_store._fsync_directory

    def fail_after_rename(directory):
        if directory == root:
            raise OSError("simulated root sync failure")
        return original(directory)

    monkeypatch.setattr(alignment_store, "_fsync_directory", fail_after_rename)
    with pytest.raises(OSError, match="simulated root sync failure"):
        alignment_store.publish_pair(bam, bai, root)
    assert list(root.iterdir()) == []
