"""Plain immutable contracts shared by the desktop UI and import worker."""
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_ROLES = ('metadata', 'summary', 'variants', 'sample_list')
ROLES = (*REQUIRED_ROLES, 'cnv_table', 'rna_table', 'cnv_plot', 'qc_plot', 'other_plot',
         'linkage', 'cancan_table', 'signature_plot', 'rna_profile_plot', 'supporting')


class ImportCancelled(Exception):
    """The user cancelled before the current sample committed."""


@dataclass(frozen=True)
class SourceCandidate:
    path: Path
    role: str
    sample_id: str = ''
    run_id: str = ''


@dataclass(frozen=True)
class ReportPlan:
    sample_id: str
    run_id: str
    files: dict[str, tuple[Path, ...]] = field(default_factory=dict)
    issues: tuple[str, ...] = ()
    profile: str = 'legacy'
    metadata_flag: str = ''
    selected: bool = True
    selection_confirmed: bool = False
    cnv_source: str = 'merged'
    cnv_solution: str = 'main'
    report_version: str = ''
    study_id_override: str = ''
    study_id_missing: bool = False

    @property
    def key(self):
        from pronto_report.identity import make_report_id
        return make_report_id(self.sample_id, self.run_id)

    @property
    def ready(self):
        if self.profile == 'tsoppi-run-v1':
            return (not self.issues
                    and all(len(self.files.get(role, ())) == 1 for role in REQUIRED_ROLES[:3])
                    and (len(self.files.get('sample_list', ())) == 1 or bool(self.files.get('linkage'))))
        return not self.issues and all(len(self.files.get(role, ())) == 1 for role in REQUIRED_ROLES)


@dataclass(frozen=True)
class DiscoveryPlan:
    folders: tuple[Path, ...]
    reports: tuple[ReportPlan, ...]
    unassigned: tuple[SourceCandidate, ...] = ()
    warnings: tuple[str, ...] = ()
    source_signatures: dict[Path, tuple[int, int]] = field(default_factory=dict)
    profile: str = 'legacy'
    run_ids: tuple[str, ...] = ()
    report_version: str = ''
    cnv_source: str = 'merged'
    cnv_solution: str = 'main'


@dataclass(frozen=True)
class ImportItemResult:
    report_id: str
    sample_id: str
    status: str
    message: str


@dataclass(frozen=True)
class ImportResult:
    items: tuple[ImportItemResult, ...]
    batch_id: str = ''


def check_cancel(cancel):
    if cancel and cancel():
        raise ImportCancelled('Avbrutt av bruker.')
