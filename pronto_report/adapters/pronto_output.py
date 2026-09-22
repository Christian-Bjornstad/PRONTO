"""Adapt an existing PRONTO/TSOPPI output directory into ReportData v1."""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Any, Callable

from pronto_report.identity import (
    VariantIdentityInput,
    assign_variant_identities,
    make_report_id,
)
from pronto_report.models import ReportData
from pronto_report.validation import validate_report_data


class AdapterError(ValueError):
    """A safe adapter failure that does not expose file contents."""


_MISSING_VALUES = {"", "-", ".", "NA", "N/A"}
_BUILD_NAMES = {"hg19": "GRCh37", "grch37": "GRCh37", "hg38": "GRCh38", "grch38": "GRCh38"}
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
MAX_SOURCE_BYTES = 100 * 1024 * 1024
MAX_SOURCE_ROWS = 10_000


def _is_missing(value: str | None) -> bool:
    return value is None or value.strip().upper() in _MISSING_VALUES


def _rows(path: Path) -> list[dict[str, str]]:
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise AdapterError("Source file exceeds the allowed size")
    with path.open(encoding="utf-8-sig", newline="") as source_file:
        data_lines = (line for line in source_file if not line.startswith("#"))
        reader = csv.DictReader(data_lines, delimiter="\t")
        rows = []
        for row in reader:
            if len(rows) >= MAX_SOURCE_ROWS:
                raise AdapterError("Source table exceeds the allowed row count")
            rows.append(row)
        return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_name(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _single(paths: list[Path], description: str) -> Path:
    if len(paths) != 1:
        raise AdapterError(f"Expected exactly one {description}")
    return paths[0]


def _reference_build(variant_path: Path) -> str | None:
    pattern = re.compile(r"/(hg19|hg38|GRCh37|GRCh38)/", re.IGNORECASE)
    with variant_path.open(encoding="utf-8-sig") as variant_file:
        for line in variant_file:
            if not line.startswith("#"):
                break
            match = pattern.search(line)
            if match:
                return _BUILD_NAMES[match.group(1).casefold()]
    return None


def _number(value: str) -> float:
    return float(value.strip().replace(",", "."))


def _integer(value: str) -> int:
    return int(value.strip())


def _source(
    file_name: str,
    *,
    field: str,
    raw_value: str,
    record: int | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "fileName": file_name,
        "field": field,
        "rawValue": raw_value,
    }
    if record is not None:
        result["record"] = record
    return result


def _annotation(
    row: dict[str, str],
    column: str,
    key: str,
    *,
    file_name: str,
    record: int,
    parser: Callable[[str], Any] | None = None,
) -> dict[str, Any] | None:
    raw_value = row.get(column, "")
    if _is_missing(raw_value):
        return None
    try:
        value = parser(raw_value) if parser else raw_value
    except ValueError:
        value = raw_value
    return {
        "key": key,
        "value": value,
        "source": _source(
            file_name, field=column, raw_value=raw_value, record=record
        ),
    }


def _diagnostic(code: str, path: str, message: str) -> dict[str, str]:
    return {"severity": "WARNING", "code": code, "path": path, "message": message}


def _biomarker(
    row: dict[str, str],
    column: str,
    metric_id: str,
    label: str,
    unit: str,
    *,
    file_name: str,
    record: int,
) -> dict[str, Any] | None:
    raw_value = row.get(column, "")
    if _is_missing(raw_value):
        return None
    match = re.match(r"^([0-9]+(?:\.[0-9]+)?)", raw_value.strip())
    if not match:
        return None
    return {
        "metricId": metric_id,
        "label": label,
        "value": float(match.group(1)),
        "unit": unit,
        "source": _source(
            file_name, field=column, raw_value=raw_value, record=record
        ),
    }


def _source_file(path: Path, root: Path, media_type: str) -> dict[str, Any]:
    return {
        "name": _relative_name(path, root),
        "sha256": _sha256(path),
        "mediaType": media_type,
        "sizeBytes": path.stat().st_size,
    }


def _attachment(path: Path, root: Path) -> dict[str, str]:
    relative_name = _relative_name(path, root)
    content_hash = _sha256(path)
    identity_hash = hashlib.sha256(
        f"{relative_name}:{content_hash}".encode("utf-8")
    ).hexdigest()[:24]
    media_type = "image/png" if path.suffix.casefold() == ".png" else "application/pdf"
    return {
        "assetId": f"asset_{identity_hash}",
        "name": relative_name,
        "mediaType": media_type,
        "sha256": content_hash,
        "description": "Source QC plot" if media_type == "image/png" else "Source CNV overview",
    }


def adapt_pronto_output(
    fixture_root: str | Path,
    *,
    sample_id: str,
    generated_at: str,
    generator_version: str,
) -> ReportData:
    """Build validated ReportData from one existing PRONTO output sample."""
    if not _IDENTIFIER.fullmatch(sample_id):
        raise AdapterError("Sample identifier is invalid")
    root = Path(fixture_root).resolve(strict=True)
    metadata_path = root / "InPreD_PRONTO_metadata.txt"
    summary_path = _single(list(root.glob("*_variant_summary.tsv")), "variant summary")
    sample_directory = root / sample_id
    variant_candidates = list(sample_directory.glob("*_small_variant_table_forQC.tsv"))
    if not variant_candidates:
        variant_candidates = list(sample_directory.glob("*_small_variant_table.tsv"))
    variant_path = _single(variant_candidates, "small variant table")
    sample_list_path = sample_directory / "sample_list.tsv"

    required_paths = [metadata_path, summary_path, variant_path, sample_list_path]
    if any(not path.is_file() for path in required_paths):
        raise AdapterError("Required PRONTO source file is missing")

    metadata_rows = _rows(metadata_path)
    metadata = next(
        (row for row in metadata_rows if row.get("Sample_id") == sample_id), None
    )
    if metadata is None:
        raise AdapterError("Requested sample is absent from metadata")

    run_id = metadata.get("Sequencing_run_id", "")
    patient_pseudonym = metadata.get("Study_id", "")
    if _is_missing(run_id) or _is_missing(patient_pseudonym):
        raise AdapterError("Required report identity metadata is missing")

    reference_build = _reference_build(variant_path)
    diagnostics: list[dict[str, str]] = []
    if reference_build is None:
        reference_build = "UNKNOWN"
        diagnostics.append(
            _diagnostic(
                "MISSING_REFERENCE_BUILD",
                "sample.referenceBuild",
                "Reference build was not declared by the source",
            )
        )

    sample: dict[str, str] = {
        "sampleId": sample_id,
        "patientPseudonym": patient_pseudonym,
        "referenceBuild": reference_build,
    }
    diagnosis = metadata.get("Clinical_diagnosis", "")
    if _is_missing(diagnosis):
        diagnostics.append(
            _diagnostic(
                "MISSING_CLINICAL_DIAGNOSIS",
                "sample.tumourType",
                "Clinical diagnosis was not supplied by the source",
            )
        )
    else:
        sample["tumourType"] = diagnosis

    summary_rows = _rows(summary_path)
    summary_sample_ids = {sample_id, f"{sample_id}_P"}
    summary_index, summary = next(
        (
            (index, row)
            for index, row in enumerate(summary_rows, start=1)
            if row.get("sample_id") in summary_sample_ids
        ),
        (None, None),
    )
    if summary is None or summary_index is None:
        raise AdapterError("Requested sample is absent from variant summary")

    summary_name = _relative_name(summary_path, root)
    biomarkers = [
        item
        for item in (
            _biomarker(
                summary,
                "TMB",
                "tmb",
                "Tumour mutational burden",
                "mut/Mb",
                file_name=summary_name,
                record=summary_index,
            ),
            _biomarker(
                summary,
                "MSI",
                "msi",
                "Unstable microsatellite sites",
                "%",
                file_name=summary_name,
                record=summary_index,
            ),
        )
        if item is not None
    ]

    variant_rows = _rows(variant_path)
    variant_name = _relative_name(variant_path, root)
    identity_inputs = []
    parsed_coordinates = []
    for row in variant_rows:
        location_match = re.match(r"^([^:]+):(\d+)$", row.get("Genomic_location", ""))
        allele_match = re.match(r"^(.+)>(.+)$", row.get("DNA_change", ""))
        chromosome = location_match.group(1) if location_match else None
        position = int(location_match.group(2)) if location_match else None
        reference = allele_match.group(1) if allele_match else None
        alternate = allele_match.group(2) if allele_match else None
        parsed_coordinates.append((chromosome, position, reference, alternate))
        identity_inputs.append(
            VariantIdentityInput(
                sample_id=sample_id,
                reference_build=reference_build,
                chromosome=chromosome,
                position=position,
                reference=reference,
                alternate=alternate,
                gene=row.get("Gene_symbol"),
                genomic_location=row.get("Genomic_location"),
                dna_change=row.get("DNA_change"),
            )
        )

    identities = assign_variant_identities(identity_inputs)
    variants = []
    annotation_columns = [
        ("Ensembl_transcript_ID", "ensemblTranscript", None),
        ("RefSeq_mRNA", "refSeqMrna", None),
        ("cDNA_change", "cdnaChange", None),
        ("Exon_number", "exonNumber", None),
        ("Coding_status", "codingStatus", None),
        ("Depth_tumor_DNA", "depthTumourDna", _integer),
        ("ClinVar_variation_ID", "clinvarVariationId", None),
        ("Tier", "tier", None),
        ("CPSR_ACMG_class", "cpsrAcmgClass", None),
        ("CPSR_ClinVar_class", "cpsrClinvarClass", None),
        ("TSO500_LocalApp_class", "tso500LocalAppClass", None),
        ("Inclusion_criteria", "inclusionCriteria", None),
        ("Filters", "filters", None),
    ]
    for index, (row, coordinates, identity) in enumerate(
        zip(variant_rows, parsed_coordinates, identities), start=1
    ):
        chromosome, position, reference, alternate = coordinates
        annotations = [
            annotation
            for column, key, parser in annotation_columns
            if (
                annotation := _annotation(
                    row,
                    column,
                    key,
                    file_name=variant_name,
                    record=index,
                    parser=parser,
                )
            )
            is not None
        ]
        variant: dict[str, Any] = {
            "variantId": identity.variant_id,
            "occurrenceId": identity.occurrence_id,
            "sampleId": sample_id,
            "referenceBuild": reference_build,
            "gene": row["Gene_symbol"],
            "genomicLocation": row["Genomic_location"],
            "dnaChange": row["DNA_change"],
            "annotations": annotations,
            "source": _source(
                variant_name,
                field="row",
                raw_value=row["Change_summary"],
                record=index,
            ),
        }
        if all(value is not None for value in coordinates):
            variant.update(
                {
                    "chromosome": chromosome,
                    "position": position,
                    "reference": reference,
                    "alternate": alternate,
                }
            )
        protein_change = row.get("Protein_change_short", "")
        if not _is_missing(protein_change):
            variant["proteinChange"] = protein_change
        allele_frequency = row.get("AF_tumor_DNA", "")
        if not _is_missing(allele_frequency):
            try:
                variant["alleleFrequency"] = _number(allele_frequency)
            except ValueError:
                diagnostics.append(
                    _diagnostic(
                        "INVALID_ALLELE_FREQUENCY",
                        f"variants[{index - 1}].alleleFrequency",
                        "Allele frequency could not be parsed from the source",
                    )
                )
        variants.append(variant)
        diagnostics.extend(
            {
                "severity": diagnostic.severity,
                "code": diagnostic.code,
                "path": diagnostic.path,
                "message": diagnostic.message,
            }
            for diagnostic in identity.diagnostics
        )

    diagnostics.append(
        _diagnostic(
            "MISSING_STRUCTURED_QC",
            "qcMetrics",
            "No structured sequencing QC metrics were present in the source",
        )
    )

    cnv_path = sample_directory / f"{sample_id}_CNV_overview_plots.pdf"
    attachment_paths = ([cnv_path] if cnv_path.is_file() else []) + sorted(
        sample_directory.glob("*_sample_QC_plot.png")
    )
    attachments = [_attachment(path, root) for path in attachment_paths]

    source_files = [
        _source_file(metadata_path, root, "text/tab-separated-values"),
        _source_file(summary_path, root, "text/tab-separated-values"),
        _source_file(variant_path, root, "text/tab-separated-values"),
        _source_file(sample_list_path, root, "text/tab-separated-values"),
    ]
    document = {
        "schemaVersion": "1.0",
        "reportId": make_report_id(sample_id, run_id),
        "sample": sample,
        "run": {"runId": run_id},
        "provenance": {
            "generatedAt": generated_at,
            "generator": {
                "name": "pronto-report-adapter",
                "version": generator_version,
            },
            "sourceFiles": source_files,
        },
        "biomarkers": biomarkers,
        "qcMetrics": [],
        "variants": variants,
        "attachments": attachments,
        "diagnostics": diagnostics,
    }
    return validate_report_data(document)
