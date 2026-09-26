# Initials at save, finalization and print

Status: approved; local-demo implementation verified 2026-09-26. See plan for evidence and scoped limitations.

## Intent and scope

Biologists should open the report without a PRONTO login screen and supply their
initials when saving, finalizing or requesting a printout. The same biologist may
save and finalize. Preserve the existing report review work and finalized reports.

The deployment boundary has not been specified. The first increment therefore
enables this experience only in an explicitly configured, loopback-only demo
with approved demonstration data. Existing installations keep their current
access controls by default. Clinical network deployment is not authorized by
this demo design and requires a separate access-control configuration decision.

## Chosen approach

Keep authorization separate from human attribution. A dedicated local demo
configuration grants a technical principal access to explicitly listed demo
reports. It does not create user accounts from entered initials or grant access
to every report. Ordinary deployments retain existing authenticated access.

Rejected alternatives:

- Removing authorization globally would expose report and alignment endpoints.
- Creating a user account for each set of initials would falsely imply verified
  identity and would confuse collisions between people sharing initials.

## User interaction

1. Opening an allowed local demo report needs no login page.
2. Save, Finalize and Generate MDT print each present a labelled initials dialog.
   Initials are required for each action, with no persistent browser storage.
3. Trim whitespace, uppercase, and accept 2–8 letters A–Z plus Æ, Ø and Å.
   Show validation errors next to the field; cancel performs no write or print.
   Apply the same validation on the server, not just in JavaScript.
4. Save records a new review revision and the initials atomically. Finalize uses
   the current saved revision, still requires explicit confirmation and locks
   subsequent edits. The same initials may perform both operations.
5. Printing requires a saved revision. If edits are pending, instruct the user to
   save first. Record PRINT_REQUESTED before opening the print dialog, and label
   the output with initials, revision, request time, and draft/final status.
   A failed audit request prevents this application print action and offers retry.
6. Final report attribution shows the initials supplied at finalization. Later
   print attribution is separate and must not overwrite the finalizer.

## Attribution and persistence

Keep the technical actor identity used for permission checks separate from
declaredInitials and an explicit SELF_REPORTED attribution marker. Never present
initials as a verified digital signature. Keep initials in report-specific audit
records, not general request logs, URLs or telemetry.

Add validated optional attribution fields to the review command and stored
review contracts without invalidating historical records. They become mandatory
for new actions in initials-required mode. Preserve the existing actor field and
authorization checks. Add nullable historical-compatible attribution fields to
ReviewAudit. Existing records without initials display “Initialer ikke registrert”.

Printing uses a separate audit event record because multiple print requests may
refer to one review revision and must not collide with the existing unique
revision audit constraint. Validate report access and revision server-side.
Give print requests idempotency identifiers so retrying an uncertain response
does not create duplicate events. Server time is authoritative.

Do not modify source ReportData to hold reviewer identity. Do not rewrite old
audit rows or unlock finalized demo reports. Initials share the review audit's
retention lifecycle; this increment adds no analytics or production retention
policy. Clinical retention and access policy remain a deployment prerequisite.

## Local demo trust boundary

Use an explicit demo startup path bound to 127.0.0.1, an isolated demo database,
and an allowlist of demo report IDs. Fail startup for a non-loopback bind or a
missing demo allowlist. Reject non-loopback requests and unexpected Host values;
do not trust forwarded headers to establish locality. Preserve CSRF protection,
CSP, no-store responses, and report-level authorization.

The technical principal is not a superuser. Do not extend the login-free scope
to alignment upload, preservation, deletion or private clinical assets. Existing
production settings must never enable this mode implicitly. Loopback is a demo
boundary, not protection from other local users or local malware.

## Limitations

- Initials are self-reported and may collide or be entered incorrectly.
- Browser print completion cannot be verified: PRINT_REQUESTED means the app
  requested a print dialog, not that paper or a PDF was produced.
- Browser-menu printing, screenshots and already downloaded HTML cannot be
  comprehensively audited. Do not claim that every possible copy is logged.
- Standalone offline reports cannot acknowledge a central audit write. Their
  print/export attribution must be labelled local-only; database-backed auditing
  is the scope of this increment.

## Verification

- Standard mode still rejects anonymous report and alignment access.
- Demo mode opens only allowlisted demo reports without a login screen; invalid
  host, non-loopback bind/request, missing allowlist and unlisted reports fail.
- Empty, overlong, malformed or HTML-bearing initials fail server validation;
  valid initials are normalized and rendered safely.
- Save/finalize persist revision and initials atomically, reject stale revisions,
  preserve source values, allow the same declarer and retain finalization locks.
- Repeated prints can reference one revision without changing it. Audit failure
  blocks application printing; retries are idempotent; cancel has no effect.
- Browser tests cover keyboard-accessible dialogs, save/reload attribution,
  finalization, dirty-print prevention, print labels and no localStorage identity.

## Next stage

User review of this written design, then an implementation plan covering the
contract/migration, demo-only access path, attribution dialogs and print audit,
with backend and browser regression tests. No public deployment in this step.
