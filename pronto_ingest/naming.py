"""Recognise role names without normalising DNA, RNA or run identifiers."""
from pathlib import Path
import re

_RUN = re.compile(r'^(\d{6}_[A-Za-z0-9]+_\d{4}_[A-Za-z0-9]+)(.*)$')
_VERSION = re.compile(r'(?:version|v)\d+$')
SUPPORT_NAMES = ('AllReportVariants_AltProtein', 'AllReportVariants_CodingRegion', 'Main_Findings',
                 'preMTB_workingTable', 'preMTBTable_Appendix', 'sequence_summary', 'TMB_coding',
                 'TMB_DURR_coding', 'pathogenic_germline', 'TERT')


def normalise_role(value):
    """Only role words are case/separator insensitive; callers retain exact IDs."""
    return re.sub(r'[^a-z0-9]', '', value.casefold())


def _without_version(value):
    return _VERSION.sub('', normalise_role(value))


def classify_run_directory(name):
    """Return an exact declared run prefix and a known directory family."""
    match = _RUN.fullmatch(name)
    if not match:
        return None
    run, suffix = match.groups()
    families = {'': 'raw', 'tso500localapppostprocessingresults': 'raw',
                'cnvs': 'cnv', 'reportpreqc': 'legacy',
                'reportpreqcnewprontoversion': 'new', 'reportwithqc': 'qc'}
    version = families.get(normalise_role(suffix))
    return (run, version) if version is not None else None


def nearest_run_directory(path):
    """Return the closest declared run boundary, including its physical root."""
    for root in Path(path).parents:
        family = classify_run_directory(root.name)
        if family:
            return root, family[0], family[1]
    return None


def summary_run_id(name):
    """Recognise an explicitly declared run prefix in a summary filename."""
    match = _RUN.fullmatch(Path(name).stem)
    if match and _without_version(match.group(2)) == 'variantsummary':
        return match.group(1)
    return None


def file_matches(name, sample_id, role, *, solution='main'):
    """Known name aliases within an independently validated sample/run scope."""
    path = Path(name)
    extension = path.suffix.casefold()
    stem = path.stem
    if role == 'supporting':
        suffix = stem[len(sample_id):] if stem.startswith(sample_id) else stem
        return extension == '.txt' and _without_version(suffix) in {normalise_role(v) for v in SUPPORT_NAMES}
    if not stem.startswith(sample_id) or len(stem) <= len(sample_id):
        return False
    suffix = stem[len(sample_id):]
    if suffix[0] not in '_-. ':
        return False
    word = _without_version(suffix)
    terms = {
        'raw_variants': {'smallvarianttable'}, 'qc_variants': {'smallvarianttableforqc'},
        'variants': {'smallvarianttable', 'smallvarianttableforqc'},
        'linkage': {'sampleconcordance'},
        'cnv_fc': {'mergedcnvsummaryfcsorted'}, 'cnv_fraction': {'mergedcnvsummaryfractionsorted'},
        'cnv_plot': {'cnvoverviewplots'}, 'qc_plot': {'sampleqcplot'},
        'signature_plot': {'jointmutationalsignature'}, 'rna_profile_plot': {'rnaprofiles'},
        'rna_table': {'fusionandsplicevariantcandidates', 'fusionandsplicevariantcandidateswithqc'},
        'cancan_table': {normalise_role(solution + '_gene_table')},
        'cancan_plot': {normalise_role(solution + '_cancan_result')},
    }
    allowed = {'.png', '.pdf'} if role.endswith('_plot') else {'.tsv', '.txt', '.csv', '.xlsx'}
    if role in {'variants', 'raw_variants', 'qc_variants', 'linkage'}:
        allowed = {'.tsv', '.txt', '.csv'}
    return extension in allowed and word in terms.get(role, set())


def declared_file_sample(name, role, *, solution='main'):
    """Read an explicit sample prefix from a recognised file family."""
    families = {'cnv_table': ('cnv_fc', 'cnv_fraction'),
                'cnv_plot': ('cnv_plot', 'cancan_plot')}.get(role, (role,))
    stem = Path(name).stem
    for index, value in enumerate(stem):
        if index and value in '_-. ':
            sample = stem[:index]
            if any(file_matches(name, sample, family, solution=solution) for family in families):
                return sample
    return None


def conflicts_sample_name(name, sample_id, role):
    """A known family with a foreign ID cannot be a generic table fallback."""
    declared = declared_file_sample(name, role)
    return declared is not None and declared != sample_id


def variant_excluded(name):
    """Clinical subsets and excluded rows never substitute the primary table."""
    word = normalise_role(Path(name).stem)
    return any(term in word for term in ('blacklist', 'predisposition', 'whitelist'))


def plot_role(name):
    """Classify a plot family; exact sample binding is still required later."""
    if Path(name).suffix.casefold() not in {'.png', '.pdf'}:
        return ''
    word = _without_version(Path(name).stem)
    for term, role in (('cnvoverviewplots', 'cnv_plot'), ('cancanresult', 'cnv_plot'),
                       ('sampleqcplot', 'qc_plot'), ('domainplot', 'other_plot'),
                       ('jointmutationalsignature', 'signature_plot'), ('rnaprofiles', 'rna_profile_plot')):
        if word.endswith(term):
            return role
    # Preserve established generic-profile candidates. The versioned profile
    # still requires exact sample/role binding through file_matches.
    original = name.casefold()
    for term, role in (('cnv_overview_plots', 'cnv_plot'), ('cancan', 'cnv_plot'),
                       ('sample_qc_plot', 'qc_plot'), ('domain_plot', 'other_plot')):
        if term in original:
            return role
    return ''
