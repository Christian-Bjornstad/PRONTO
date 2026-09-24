"""Conservative conversion of a declared report variant to an IGV locus."""

from __future__ import annotations

import re
from typing import Mapping


_LOCATION = re.compile(r"^(?:chr)?(\d{1,2}|X|Y|M|MT):(\d+)$")
_CHROMOSOMES = {str(number) for number in range(1, 23)} | {"X", "Y", "M", "MT"}


def locus_for_variant(variant: Mapping[str, object], sample_build: str) -> str | None:
    """Return a 100-bp window only for a matching, explicit human build."""
    if sample_build not in {"GRCh37", "GRCh38"} or variant.get("referenceBuild") != sample_build:
        return None

    chromosome = variant.get("chromosome")
    position = variant.get("position")
    if chromosome is None or position is None:
        match = _LOCATION.fullmatch(str(variant.get("genomicLocation", "")))
        if match is None:
            return None
        chromosome, position = match.group(1), int(match.group(2))

    name = str(chromosome).removeprefix("chr")
    if name not in _CHROMOSOMES or type(position) is not int or position < 1:
        return None
    if name == "MT":
        name = "M"
    return f"chr{name}:{max(1, position - 50)}-{position + 50}"
