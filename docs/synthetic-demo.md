# Synthetic patient cohort

`seed_demo_patients` appends entirely invented patients to an existing local
PRONTO demo. It does not read the supplied spreadsheets, clone patient data or
reuse their plots. Patient codes start with `SYN-`; source tables, notes, plots
and both PDF formats explicitly identify the simulation.

The default cohort contains 30 patients: 10 un-reviewed, 10 under-review and
10 reviewed. Existing reports retain their own status. Cases vary across eight
tumour labels, sample types, 0-20 small variants, 0-4 CNVs and 0-2 RNA events.
Review examples exercise Benign/VUS/Oncogenic, Include/Exclude, highlights,
neutral/green/orange/red QC, missing HRD, and TMB above 100 with the `[0-100+]`
display range. These scores and labels do not encode clinical thresholds or
treatment recommendations.

Some cases include a nine-panel illustrative CNV PDF (B3 above C1 in the first
view) and illustrative fusion/splice diagrams. The plots are generated from
scratch and marked synthetic. Histories contain 1-4 revisions; seeded saves
and finalizations use the normal review service and audits, with simulated
initials `SM`. FINAL remains locked; earlier versions remain read-only.

## Add patients and reopen

Use the project virtual environment and the normal local secret configuration:

```powershell
.venv/Scripts/python manage.py seed_demo_patients --database demo-integrated-20261001.demo.sqlite3 --count 30 --seed 20261001
.venv/Scripts/python manage.py resume_demo --database demo-integrated-20261001.demo.sqlite3 --all-reports --port 8770
```

Stop the local demo server before expanding its database, then reopen it.
`--all-reports` explicitly opts into the validated cohort; the original
single-report `--report` form remains strict. Only an existing isolated
`*.demo.sqlite3` with demo-prefixed reports, saved revisions and exact read
grants to its sole restricted demo user is accepted. No alignment write grants
are permitted and all browser access remains loopback-only.

The seed and patient number determine stable identifiers and generated inputs.
Rerunning the same seed/count preserves reports, assets and manually edited
reviews; increasing count adds only missing patients. A different seed adds a
new cohort. Counts are bounded to 1-200 per batch and 500 total demo reports.
ID collisions with unrelated data fail the whole transaction. No database,
generated plot or PDF is committed to Git.

The index paginates at 25 patients and shows both the displayed and total count.
The original local mixed-sample demonstration stays separate from these
patient-scoped synthetic inputs.
