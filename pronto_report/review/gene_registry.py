"""Membership in the supplied September 2026 molecular marker list."""
import json
from pathlib import Path

REGISTRY = json.loads((Path(__file__).with_name('genes-september-2026.json')).read_text(encoding='utf-8'))


def gene_in_list(gene):
    from django.conf import settings
    registry = getattr(settings, 'PRONTO_BIOMARKER_GENES', None) if settings.configured else None
    return str(gene or '').strip().upper() in (registry if registry is not None else REGISTRY['genes'])


def gene_markup(gene):
    from html import escape
    value = escape(str(gene or ''))
    return '<strong>' + value + '</strong>' if gene_in_list(gene) else value
