"""Explicitly fill a missing Study_id without modifying the source metadata."""
from dataclasses import replace

MISSING_STUDY_ID = 'metadata: Study_id mangler'
MISSING_VALUES = {'', '-', '.', 'NA'}


def normalize_study_id(value):
    if not isinstance(value, str) or len(value) > 128 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Study_id må være tekst på én linje med høyst 128 tegn.')
    value = value.strip()
    if value and value.upper() in MISSING_VALUES:
        raise ValueError('Oppgi riktig Study_id, ikke en plassholder.')
    return value


def source_metadata_row(report, paths=None):
    from .discovery import table_rows
    paths = report.files.get('metadata', ()) if paths is None else paths
    if len(paths) != 1:
        raise ValueError('Velg én metadatafil før Study_id fylles inn.')
    rows = table_rows(paths[0], header={'Sample_id', 'Sequencing_run_id', 'Study_id'})
    exact = [row for row in rows if row.get('Sample_id') == report.sample_id
             and row.get('Sequencing_run_id') == report.run_id]
    if len(exact) != 1:
        raise ValueError('Metadata må ha én entydig rad for denne prøven og kjøringen.')
    return exact[0]


def effective_metadata(report, original):
    row = dict(original)
    if report.study_id_override:
        value = normalize_study_id(report.study_id_override)
        if not value:
            raise ValueError('Study_id kan ikke være tomt.')
        if row.get('Study_id', '').strip().upper() not in MISSING_VALUES:
            raise ValueError('Study_id finnes allerede i metadatafilen. Kontroller kildegrunnlaget før det endres.')
        row['Study_id'] = value
    return row


def set_manual_study_id(plan, report_key, value):
    value = normalize_study_id(value)
    report = next((report for report in plan.reports if report.key == report_key), None)
    if report is None:
        raise ValueError('Velg en prøve.')
    original = source_metadata_row(report)
    if original.get('Study_id', '').strip().upper() not in MISSING_VALUES:
        raise ValueError('Study_id finnes allerede i metadatafilen. Kontroller kildegrunnlaget før det endres.')
    issues = tuple(issue for issue in report.issues if issue != MISSING_STUDY_ID)
    if not value:
        issues += (MISSING_STUDY_ID,)
    updated = replace(report, study_id_override=value, issues=issues, selected=False, selection_confirmed=False)
    return replace(plan, reports=tuple(updated if candidate.key == report_key else candidate for candidate in plan.reports))


def preserve_manual_study_ids(previous, current):
    """Keep session edits only while the same metadata source is unchanged."""
    if previous is None:
        return current
    old = {report.key: report for report in previous.reports if report.study_id_override}
    reset = False
    for key, report in old.items():
        candidate = next((item for item in current.reports if item.key == key), None)
        paths = report.files.get('metadata', ())
        unchanged = candidate is not None and paths == candidate.files.get('metadata', ()) and all(
            previous.source_signatures.get(path) is not None
            and previous.source_signatures[path] == current.source_signatures.get(path) for path in paths)
        if unchanged:
            current = set_manual_study_id(current, key, report.study_id_override)
        else:
            reset = True
    if reset:
        current = replace(current, warnings=(*current.warnings,
            'Manuelt Study_id ble nullstilt fordi metadatafilen eller prøveutvalget er endret.'))
    return current
