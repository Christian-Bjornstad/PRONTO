import pytest

import pronto_report.identity as identity_module
from pronto_report.identity import (
    IdentityInputError,
    VariantIdentityInput,
    assign_variant_identities,
)


def allele_input(**changes):
    values = {
        "sample_id": "sample-001",
        "reference_build": "GRCh38",
        "chromosome": "chr7",
        "position": 140453136,
        "reference": "A",
        "alternate": "T",
        "gene": "BRAF",
        "genomic_location": "chr7:140453136",
        "dna_change": "c.1799T>A",
    }
    values.update(changes)
    return VariantIdentityInput(**values)


def fallback_input(**changes):
    values = {
        "sample_id": "sample-001",
        "reference_build": "GRCh38",
        "gene": "TERT",
        "genomic_location": "chr5:1295228",
        "dna_change": "c.-124C>T",
    }
    values.update(changes)
    return VariantIdentityInput(**values)


def diagnostic_codes(result):
    return {diagnostic.code for diagnostic in result.diagnostics}


def test_same_normalized_alleles_produce_same_variant_id():
    first, second = assign_variant_identities(
        [
            allele_input(),
            allele_input(
                sample_id=" SAMPLE-001 ",
                reference_build="grch38",
                chromosome="7",
                reference="a",
                alternate="t",
            ),
        ]
    )

    assert first.variant_id == second.variant_id
    assert first.variant_id.startswith("variant_")
    assert first.strategy == "ALLELE"
    assert "FALLBACK_VARIANT_ID" not in diagnostic_codes(first)


def test_different_alleles_produce_different_variant_ids():
    first, second = assign_variant_identities(
        [allele_input(alternate="T"), allele_input(alternate="G")]
    )

    assert first.variant_id != second.variant_id


def test_fallback_identity_emits_warning():
    (result,) = assign_variant_identities([fallback_input()])

    assert result.strategy == "FALLBACK"
    assert "FALLBACK_VARIANT_ID" in diagnostic_codes(result)


def test_duplicate_tert_rows_remain_traceable_as_distinct_occurrences():
    first, second = assign_variant_identities([fallback_input(), fallback_input()])

    assert first.variant_id == second.variant_id
    assert first.occurrence_id != second.occurrence_id
    assert first.occurrence_id.endswith(".1")
    assert second.occurrence_id.endswith(".2")
    assert "DUPLICATE_VARIANT_ID" in diagnostic_codes(first)
    assert "DUPLICATE_VARIANT_ID" in diagnostic_codes(second)


def test_hash_collision_emits_diagnostic_and_preserves_both_rows(monkeypatch):
    monkeypatch.setattr(identity_module, "_digest", lambda canonical_key: "0" * 24)

    first, second = assign_variant_identities(
        [allele_input(alternate="T"), allele_input(alternate="G")]
    )

    assert first.variant_id == second.variant_id
    assert first.occurrence_id != second.occurrence_id
    assert "IDENTITY_HASH_COLLISION" in diagnostic_codes(first)
    assert "IDENTITY_HASH_COLLISION" in diagnostic_codes(second)


@pytest.mark.parametrize(
    "record",
    [
        VariantIdentityInput(sample_id="sample-001", reference_build="GRCh38"),
        fallback_input(gene=None),
        allele_input(position=0),
    ],
)
def test_incomplete_or_invalid_identity_is_rejected_without_echoing_values(record):
    with pytest.raises(IdentityInputError) as caught:
        assign_variant_identities([record])

    assert str(caught.value) == "Variant identity fields are incomplete or invalid"
