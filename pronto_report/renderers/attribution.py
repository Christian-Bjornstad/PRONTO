"""Render self-reported attribution independently from technical actor IDs."""
from html import escape


def render_attribution(review, snapshot: bool) -> str:
    entries = []
    if review:
        for label, value in (('Saved by', review.last_saved_attribution), ('Finalized by', review.finalization_attribution)):
            if value:
                entries.append(f'{label}: {escape(value["declaredInitials"])} (self-reported initials)')
    return '<p id="review-attribution"' + ('>' if entries else ' hidden>') + ' · '.join(entries) + '</p>'


def initials_dialog() -> str:
    return ('<dialog id="initials-dialog" aria-labelledby="initials-action">'
        '<h2 id="initials-action">Enter initials</h2><p>Your initials are recorded with this action.</p>'
        '<label for="declared-initials">Your initials</label>'
        '<input id="declared-initials" autocomplete="off" maxlength="8" aria-describedby="initials-error">'
        '<p id="initials-error" role="alert"></p>'
        '<button type="button" id="initials-cancel">Cancel</button>'
        '<button type="button" id="initials-confirm">Confirm</button></dialog>')
