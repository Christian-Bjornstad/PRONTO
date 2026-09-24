# Authenticated Django read slice

Task 25 adds a minimal Django 5.2 LTS adapter around the validated PRONTO
contracts. It does not replace the existing PPTX workflow or add save/finalize
HTTP endpoints. Tests seed an approved non-sensitive report, a review revision,
an asset, and a per-user grant; the application does not auto-import or expose
any production report.

## Local setup

Install `requirements.txt`. Set `PRONTO_DJANGO_SECRET_KEY` to a unique secret
outside source control, then run `python manage.py migrate` and
`python manage.py runserver`. An optional `PRONTO_DJANGO_DB` selects the local
SQLite file. Database files are gitignored. Create users and populate
`ReportRecord`, `ReviewRevision`, `ReportAsset`, and `ReportGrant` only with
approved, validated data. `python manage.py test pronto_web.reports` provides
a complete non-sensitive example without persisting it outside the test DB.

Open `/accounts/login/` and then `/reports/`. Login uses Django's session and
CSRF handling. The list only includes granted reports. A report request checks
the grant before reading the stored JSON or asset bytes, validates ReportData
and the latest ReviewState, checks stored IDs/revisions, verifies attachment
hashes, and renders the existing read-only, self-contained PRONTO page. Plots
are embedded after authorization; no separate file-serving URL exists. Report
and list responses use `Cache-Control: no-store`.

The settings intentionally bind to localhost/testserver and require an
external secret. SQLite, local password management, backups, retention,
HTTPS/proxy configuration, operational logging, and deployment authorization
still need review before any real patient data is used. The next slices add
transactional revision/audit writes and explicit **Lagre**/finalization UI.
