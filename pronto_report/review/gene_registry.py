"""Membership in the supplied September 2026 molecular marker list."""
import json
from pathlib import Path

REGISTRY = json.loads((Path(__file__).with_name('genes-september-2026.json')).read_text(encoding='utf-8'))


def gene_in_list(gene):
    return str(gene or '').strip().upper() in REGISTRY['genes']
