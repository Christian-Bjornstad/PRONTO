"""Render self-reported attribution independently from technical actor IDs."""
from html import escape


def render_attribution(review, snapshot: bool) -> str:
    entries = []
    if review:
        for label, value in (('Lagret av', review.last_saved_attribution), ('Ferdigstilt av', review.finalization_attribution)):
            if value:
                entries.append(f'{label}: {escape(value["declaredInitials"])} (selvoppgitte initialer)')
    return '<p id="review-attribution">' + (' · '.join(entries) or 'Initialer ikke registrert') + '</p>'


def initials_dialog() -> str:
    return ('<dialog id="initials-dialog" aria-labelledby="initials-action">'
        '<h2 id="initials-action">Oppgi initialer</h2><p>Selvoppgitte initialer loggføres med handlingen.</p>'
        '<label for="declared-initials">Dine initialer</label>'
        '<input id="declared-initials" autocomplete="off" maxlength="8" aria-describedby="initials-error">'
        '<p id="initials-error" role="alert"></p>'
        '<button type="button" id="initials-cancel">Avbryt</button>'
        '<button type="button" id="initials-confirm">Bekreft</button></dialog>')
