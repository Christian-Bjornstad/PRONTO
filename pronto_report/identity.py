"""Deterministic report variant identity without dropping source occurrences."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Literal


class IdentityInputError(ValueError):
    """Raised when neither preferred nor fallback identity is complete."""

    def __init__(self) -> None:
        super().__init__("Variant identity fields are incomplete or invalid")


@dataclass(frozen=True, slots=True)
class VariantIdentityInput:
    sample_id: str
    reference_build: str
    chromosome: str | None = None
    position: int | None = None
    reference: str | None = None
    alternate: str | None = None
    gene: str | None = None
    genomic_location: str | None = None
    dna_change: str | None = None


@dataclass(frozen=True, slots=True)
class IdentityDiagnostic:
    severity: Literal["WARNING"]
    code: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class VariantIdentity:
    variant_id: str
    occurrence_id: str
    strategy: Literal["ALLELE", "FALLBACK"]
    diagnostics: tuple[IdentityDiagnostic, ...]


def _text(value: str | None, *, case: str = "fold") -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        return None
    if case == "upper":
        return normalized.upper()
    if case == "preserve":
        return normalized
    return normalized.casefold()


def _chromosome(value: str | None) -> str | None:
    normalized = _text(value, case="upper")
    if normalized is None:
        return None
    if normalized.startswith("CHR"):
        normalized = normalized[3:]
    return "MT" if normalized == "M" else normalized


def _compact(value: str | None) -> str | None:
    normalized = _text(value)
    return None if normalized is None else "".join(normalized.split())


def _canonical_identity(
    record: VariantIdentityInput,
) -> tuple[str, Literal["ALLELE", "FALLBACK"]]:
    sample_id = _text(record.sample_id)
    reference_build = _text(record.reference_build)
    chromosome = _chromosome(record.chromosome)
    reference = _text(record.reference, case="upper")
    alternate = _text(record.alternate, case="upper")

    if not sample_id or not reference_build:
        raise IdentityInputError()

    allele_fields_supplied = any(
        value is not None
        for value in (
            record.chromosome,
            record.position,
            record.reference,
            record.alternate,
        )
    )
    has_allele_identity = (
        chromosome is not None
        and isinstance(record.position, int)
        and not isinstance(record.position, bool)
        and record.position > 0
        and reference is not None
        and alternate is not None
    )
    if has_allele_identity:
        parts = [
            sample_id,
            reference_build,
            chromosome,
            record.position,
            reference,
            alternate,
        ]
        strategy: Literal["ALLELE", "FALLBACK"] = "ALLELE"
    elif allele_fields_supplied:
        raise IdentityInputError()
    else:
        gene = _text(record.gene, case="upper")
        genomic_location = _compact(record.genomic_location)
        dna_change = _compact(record.dna_change)
        if not gene or not genomic_location or not dna_change:
            raise IdentityInputError()
        parts = [sample_id, gene, genomic_location, dna_change]
        strategy = "FALLBACK"

    canonical = json.dumps(
        {"strategy": strategy, "parts": parts},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return canonical, strategy


def _digest(canonical_key: str) -> str:
    return hashlib.sha256(canonical_key.encode("utf-8")).hexdigest()[:24]


def assign_variant_identities(
    records: Iterable[VariantIdentityInput],
) -> tuple[VariantIdentity, ...]:
    """Assign stable variant IDs and source-order occurrence IDs to every row."""
    prepared = []
    keys_by_variant_id: dict[str, set[str]] = defaultdict(set)
    for record in records:
        canonical_key, strategy = _canonical_identity(record)
        variant_id = f"variant_{_digest(canonical_key)}"
        prepared.append((variant_id, canonical_key, strategy))
        keys_by_variant_id[variant_id].add(canonical_key)

    totals = Counter(variant_id for variant_id, _, _ in prepared)
    ordinals: Counter[str] = Counter()
    results = []
    for index, (variant_id, _, strategy) in enumerate(prepared):
        ordinals[variant_id] += 1
        occurrence_id = f"{variant_id}.occurrence.{ordinals[variant_id]}"
        path = f"variants[{index}].variantId"
        diagnostics = []
        if strategy == "FALLBACK":
            diagnostics.append(
                IdentityDiagnostic(
                    severity="WARNING",
                    code="FALLBACK_VARIANT_ID",
                    path=path,
                    message="Variant identity uses the fallback field set",
                )
            )
        if totals[variant_id] > 1:
            diagnostics.append(
                IdentityDiagnostic(
                    severity="WARNING",
                    code="DUPLICATE_VARIANT_ID",
                    path=path,
                    message="Multiple source occurrences share this variant identity",
                )
            )
        if len(keys_by_variant_id[variant_id]) > 1:
            diagnostics.append(
                IdentityDiagnostic(
                    severity="WARNING",
                    code="IDENTITY_HASH_COLLISION",
                    path=path,
                    message="Distinct normalized variants produced the same identity hash",
                )
            )
        results.append(
            VariantIdentity(
                variant_id=variant_id,
                occurrence_id=occurrence_id,
                strategy=strategy,
                diagnostics=tuple(diagnostics),
            )
        )
    return tuple(results)
