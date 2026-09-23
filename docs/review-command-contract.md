# Review command contract (v1)

This is the framework-neutral boundary for Tasks 24–28. Django will parse the
JSON request into `SaveDraftRequest` or `FinalizeRequest`, supply an authenticated
actor ID and report-level authorizer, and map `ReviewCommandError.http_status`
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
This contract does not yet implement database storage, CSRF, or HTTP routes.
