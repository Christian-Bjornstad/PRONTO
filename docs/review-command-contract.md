# Review command APIs

## Working-draft API (v2)

The current local workspace enables `PRONTO_WORKING_DRAFTS` and posts to
`/reports/<report-id>/working/`. Each command requires an authenticated active
user, a grant for that report, a CSRF token and `application/json` (maximum
1 MiB). Identity and timestamps are supplied by the server.

```json
{
  "schemaVersion": "2.0",
  "reportId": "report-id",
  "action": "SAVE",
  "baseRevision": 15,
  "expectedVersion": 1,
  "draft": { "schemaVersion": "4.0" }
}
```

The illustrative draft must be replaced with the full validated ReviewState v4.
Allowed actions are `SAVE`, `RESET`, `FINALIZE` and `REOPEN`. Both the revision
and working version must match the current server state. Unknown fields, wrong
types, non-finite JSON and invalid review state are rejected.

- SAVE replaces the active working draft and advances `workingVersion`.
- RESET saves a reset working draft; it does not alter source ReportData.
- FINALIZE requires a saved active draft, preserves a FINAL ReviewRevision and
  removes the working draft.
- REOPEN requires `sourceRevision` for the selected saved DRAFT/FINAL. Replacing
  an active draft also requires `replaceWorking: true`. The historical source
  remains unchanged; the new working draft receives a new revision number.

Commands and minimal `WorkingDraftEvent` records commit atomically. Successful
responses use HTTP 201 with `review` and `workingVersion`. Stale requests return
409; invalid requests/reviews return 422; oversized bodies return 413; missing
or ungranted reports return 404; unauthenticated commands return 401. Standard
CSRF failures return 403. The current workspace never trusts browser-supplied
reviewer identity.

PDF exports use their own audited endpoint. An active draft is frozen to an
immutable snapshot and the next editable revision advances. Retrying an export
returns its original snapshot, without providing a stale client with current
editing tokens. See [workspace behavior](report-review-workspace.md).

The API below remains for deployments with working drafts disabled. Do not mix
its revision/attribution rules with the v2 working-draft API.

## Legacy immutable revision API (v1)

This framework-neutral compatibility boundary parses the
JSON request into `SaveDraftRequest` or `FinalizeRequest`, supplies an authenticated
actor ID and report-level authorizer, and maps `ReviewCommandError.http_status`
and `as_dict()` to the HTTP response. The browser must not provide actor ID.

Both commands use this envelope (the draft is a complete, validated
`ReviewState` v2 at `baseRevision`):

```json
{
  "schemaVersion": "1.0",
  "reportId": "report-id",
  "baseRevision": 1,
  "draft": { "schemaVersion": "2.0" }
}
```

The `draft` above is illustrative, not a complete ReviewState. The actual
request must contain every field required by `review-state-v2.schema.json`.
Unknown envelope fields and wrong types are rejected. A successful response
contains `schemaVersion`, the new `review`, and an `audit` record with
`reportId`, `actorId`, `action`, `revision`, and `timestamp`. Errors use the same
command version and an `error` object with stable `code`, safe `message`, and
`currentRevision` for a revision conflict. The intended HTTP mappings are 403
for denied access, 404 for an absent saved review, 409 for stale/locked/dirty
state, and 422 for invalid commands or drafts.

Saving checks the supplied base revision against the latest stored revision,
validates the entire draft against the immutable report, then generates the
next revision, reviewer identity, and UTC timestamp on the server. New or
changed source corrections require the acting author and are server-time
stamped. Unknown variant IDs, duplicate decisions, unsupported correction
paths, and altered source values are rejected. Imported legacy note text stays
read-only.

Finalization requires an exact copy of the latest saved draft and the same
base revision. This prevents a page with unsaved edits from signing an older
snapshot. The same authorized biologist may save and finalize. Finalization
creates a new FINAL revision with finalizer/time; any later write is locked.

`ReviewRepository.commit` is the atomic boundary: compare the stored revision
and write the new review plus audit record in one transaction, or write
nothing. A Django implementation must enforce that invariant in the database;
the service's earlier read is not the concurrency guard. Repeating a successful
request with the old base revision returns a conflict rather than replaying it.
Database storage, CSRF and HTTP adapters are implemented separately in `pronto_web.reports`.
