"""Oslo wall-clock labels for display; persisted ISO timestamps stay unchanged."""

from datetime import datetime
from zoneinfo import ZoneInfo


OSLO = ZoneInfo('Europe/Oslo')


def oslo_time(value: str | None) -> str:
    if not value:
        return ''
    try:
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
        # A date or unzoned legacy value is not an unambiguous instant.
        if instant.tzinfo is None:
            return value
        return instant.astimezone(OSLO).strftime('%d.%m.%Y %H:%M:%S %Z')
    except (ValueError, OverflowError):
        return value
