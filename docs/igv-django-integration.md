# Django report and IGV integration

This integration branch joins the authenticated, editable review report with
the IGV alignment viewer. An authorized reader sees both the reference-style
interactive report and the IGV panel on one page. Draft review writes use the
explicit **Lagre** and **Ferdigstill** controls; alignment files remain
ephemeral unless a separately authorized user explicitly confirms preservation.
`ReportGrant` permits viewing/reviewing a report, while `ReportWriteGrant` is
required for preserving alignment files. Neither permission is inferred from
the other.

The two independently developed `0002` migrations are retained unchanged.
`0003_merge_review_alignment` joins their graph without a data operation.
This preserves both branches' review history and lets new databases apply
both schema additions. Check the migration plan and test it against a copy of
the deployment database before any production rollout.

The live HTML keeps the source facts immutable, shows saved corrections as
review provenance, and enables same-origin requests for IGV and Django review
commands. Standalone HTML exports keep their network-denying CSP and cannot
contact the server. The IGV-specific CSP allowances (including runtime
styles and wasm) are restricted to web-IGV pages.

This branch is a review artifact, not approval for patient use. Production
database concurrency, private storage policy, backups/retention, HTTPS,
authentication operations, and clinical-user visual review remain separate
release gates. See `docs/igv-alignment-operations.md` and
`docs/django-draft-save.md`.
