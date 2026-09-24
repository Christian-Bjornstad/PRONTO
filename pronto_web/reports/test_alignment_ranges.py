"""Byte-range parsing contract, independent of Django's database."""

import pytest

from io import BytesIO

from pronto_web.reports.alignment_ranges import RangeNotSatisfiable, iter_range, parse_single_range


def test_single_ranges():
    assert parse_single_range("bytes=2-5", 10) == (2, 5)
    assert parse_single_range("bytes=8-", 10) == (8, 9)
    assert parse_single_range("bytes=-3", 10) == (7, 9)
    assert parse_single_range("bytes=0-99", 10) == (0, 9)


@pytest.mark.parametrize("header", ["", "bytes=0-1,4-5", "bytes=10-", "bytes=5-2", "items=0-1", "bytes=-0", "bytes=abc", "bytes= 0-1"])
def test_invalid_ranges(header):
    with pytest.raises(RangeNotSatisfiable):
        parse_single_range(header, 10)


def test_truncated_file_fails_and_closes_descriptor():
    handle = BytesIO(b"01")
    with pytest.raises(OSError, match="changed during transfer"):
        b"".join(iter_range(handle, 0, 5, chunk_size=2))
    assert handle.closed
