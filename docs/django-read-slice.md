# Authenticated Django report access

Django wraps the validated PRONTO contracts without replacing the legacy PPTX
workflow. Report input is stored as `ReportRecord`, historical reviews as
`ReviewRevision`, the active editable copy as `WorkingDraft`, and source plots
as `ReportAsset`. A per-user `ReportGrant` is required for each report.

For an authenticated local setup, use the [startup guide](oppstart-nb.md).
The launcher creates the local configuration, runs migrations and starts the
loopback server. A separate deployment must supply `PRONTO_DJANGO_SECRET_KEY`
outside source control and configure its database, HTTPS and application server.

`/accounts/login/` uses Django session authentication and CSRF protection.
`/reports/` lists only granted reports. A report request checks its grant before
reading JSON or asset bytes, validates the stored ReportData/ReviewState and
identifiers, verifies source attachment hashes, then renders the report. Source
plots are embedded after authorization. Report/list responses use
`Cache-Control: no-store`.

Historical snapshots open through `?revision=N`; editing and upload controls are
not attached to that view. Current draft editing, signing and PDF actions are
separate authenticated commands described in the
[working-draft API](review-command-contract.md#working-draft-api-v2).
A report grant permits reading/reviewing but does not grant the separate
alignment-preservation permission. See [IGV operations](igv-alignment-operations.md).

Run `python manage.py test pronto_web.reports` with the test settings for
request/access tests. Tests use approved or synthetic data in isolated databases;
they do not import data into the running local database.
