"""Resolve exact DNA/RNA claims from immutable source content, never ID prefixes."""
from pathlib import Path
import re

_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')
_CONCORDANCE = re.compile(
    r'^# Concordance between processed \[tumor DNA: "([^"\r\n]+)"\] '
    r'and \[tumor RNA: "([^"\r\n]+)"\] samples:\s*$')
_VARIANT = re.compile(r'^# \[([^\]\r\n]+)\].*?ID of matched tumor RNA sample:\s*(\S+)\s*$')
_EMPTY = {'NA', 'N/A', 'NONE', '-', ''}


def sample_list_links(sample_id, rows):
    dna = {row.get('sample_ID', '').strip() for row in rows
           if row.get('sample_type', '').casefold() in {'dna_tumor', 'dna_tumour'}}
    if dna != {sample_id}:
        raise ValueError('Prøvelisten må være avgrenset til én eksakt DNA-prøve.')
    rna = {row.get('sample_ID', '').strip() for row in rows
           if row.get('sample_type', '').casefold() in {'rna_tumor', 'rna_tumour'}}
    rna = {value for value in rna if value.upper() not in _EMPTY}
    if any(not _ID.fullmatch(value) for value in rna):
        raise ValueError('Ugyldig prøveidentitet i DNA/RNA-kobling.')
    return {sample_id, *rna}


def _comment_claims(path, sample_id):
    from .discovery import MAX_BYTES, MAX_ROWS, regular_file
    if not regular_file(path) or path.stat().st_size > MAX_BYTES:
        raise ValueError('Koblingskilden er for stor eller utilgjengelig.')
    claims = []
    with path.open(encoding='utf-8-sig') as stream:
        for index, line in enumerate(stream):
            if index > MAX_ROWS + 500 or len(line) > 1024 * 1024:
                raise ValueError('Koblingskilden overskrider radgrensen.')
            if not line.startswith('#'):
                continue
            line = line.rstrip('\r\n')
            match = _CONCORDANCE.fullmatch(line) or _VARIANT.fullmatch(line)
            if match:
                dna, rna = match.groups()
                if dna != sample_id or not _ID.fullmatch(dna):
                    raise ValueError('DNA/RNA-koblingen gjelder en annen DNA-prøve.')
                if rna.upper() in _EMPTY:
                    claims.append({sample_id})
                elif _ID.fullmatch(rna):
                    claims.append({sample_id, rna})
                else:
                    raise ValueError('Ugyldig RNA-identitet i DNA/RNA-kobling.')
            elif 'Concordance between processed [tumor DNA:' in line or 'ID of matched tumor RNA sample:' in line:
                raise ValueError('DNA/RNA-koblingen har ukjent format.')
    return claims


def resolve_links(sample_id: str, sources: dict[str, tuple[Path, ...]]) -> set[str]:
    """Require all available explicit claims to agree; a sample list has priority."""
    from .discovery import table_rows
    if not _ID.fullmatch(sample_id):
        raise ValueError('Ugyldig DNA-identitet.')
    claims = [sample_list_links(sample_id, table_rows(Path(path), header={'sample_type', 'sample_ID'}))
              for path in sources.get('sample_list', ())]
    for path in dict.fromkeys((*sources.get('linkage', ()), *sources.get('variants', ()))):
        claims.extend(_comment_claims(Path(path), sample_id))
    if not claims:
        raise ValueError('Mangler eksplisitt DNA/RNA-kobling.')
    if any(claim != claims[0] for claim in claims[1:]):
        raise ValueError('DNA/RNA-koblingene er ikke samstemte.')
    return claims[0]
