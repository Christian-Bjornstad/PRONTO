"""IGV launch coordinates are derived only from declared report locations."""

def test_grch37_variant_resolves_to_padded_locus():
    from pronto_report.igv.locus import locus_for_variant

    variant = {"referenceBuild": "GRCh37", "chromosome": "17", "position": 7577120}

    assert locus_for_variant(variant, "GRCh37") == "chr17:7577070-7577170"


def test_unknown_or_mismatched_build_has_no_locus():
    from pronto_report.igv.locus import locus_for_variant

    variant = {"referenceBuild": "UNKNOWN", "chromosome": "17", "position": 7577120}
    assert locus_for_variant(variant, "UNKNOWN") is None
    variant["referenceBuild"] = "GRCh38"
    assert locus_for_variant(variant, "GRCh37") is None


def test_string_location_is_supported_but_noncanonical_coordinates_are_not():
    from pronto_report.igv.locus import locus_for_variant

    assert locus_for_variant({"referenceBuild": "GRCh37", "genomicLocation": "5:20"}, "GRCh37") == "chr5:1-70"
    assert locus_for_variant({"referenceBuild": "GRCh37", "genomicLocation": "17:0"}, "GRCh37") is None
    assert locus_for_variant({"referenceBuild": "GRCh37", "genomicLocation": "25:100"}, "GRCh37") is None
    assert locus_for_variant({"referenceBuild": "GRCh37", "chromosome": "17", "position": True}, "GRCh37") is None
