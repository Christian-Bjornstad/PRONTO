"""Strict single-range parsing and bounded file streaming for alignments."""

from __future__ import annotations

from typing import BinaryIO, Iterator
import re


class RangeNotSatisfiable(ValueError):
    """The request cannot be served as one bounded byte range."""


def parse_single_range(header: str, size: int) -> tuple[int, int]:
    if size < 1:
        raise RangeNotSatisfiable("empty resource")
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
    if match is None or not any(match.groups()):
        raise RangeNotSatisfiable("invalid or multiple ranges")
    first, last = match.groups()
    if not first:
        suffix = int(last)
        if suffix < 1:
            raise RangeNotSatisfiable("empty suffix")
        return max(0, size - suffix), size - 1
    start = int(first)
    end = int(last) if last else size - 1
    if start >= size or end < start:
        raise RangeNotSatisfiable("out of bounds")
    return start, min(end, size - 1)


def iter_range(file_handle: BinaryIO, start: int, end: int, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
    try:
        file_handle.seek(start)
        remaining = end - start + 1
        while remaining:
            block = file_handle.read(min(chunk_size, remaining))
            if not block:
                raise OSError("alignment changed during transfer")
            remaining -= len(block)
            yield block
    finally:
        file_handle.close()
