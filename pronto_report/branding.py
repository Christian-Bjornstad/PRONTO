"""Bundled PRONTO artwork shared by desktop and self-contained reports."""
import base64
from functools import lru_cache
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parent / 'static' / 'branding'


@lru_cache(maxsize=1)
def favicon_data_uri():
    return 'data:image/png;base64,' + base64.b64encode((ASSET_ROOT / 'favicon.png').read_bytes()).decode('ascii')
