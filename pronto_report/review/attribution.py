"""Self-reported labels are not authenticated identities."""
import re


def normalize_initials(value: object) -> str:
    from pronto_report.review.contracts import ReviewCommandError

    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-zÆØÅæøå]{2,8}', value.strip()):
        raise ReviewCommandError('INVALID_INITIALS', 'Oppgi 2–8 bokstaver som initialer.', 422)
    return value.strip().upper()
