"""Explicit local HTTP settings. The launcher binds exclusively to loopback."""
from .settings import *

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
PRONTO_DEMO_ENABLED = False
PRONTO_REQUIRE_INITIALS = False

# Public references stay outside Git/static files and are served after login.
PRONTO_IGV_REFERENCE_FILES = dict(PRONTO_IGV_REFERENCE_FILES)
PRONTO_IGV_REFERENCES = {build: dict(pair) for build, pair in PRONTO_IGV_REFERENCES.items()}
for build in ('GRCh37', 'GRCh38'):
    fasta = BASE_DIR / '.local-web' / 'references' / f'{build}.fa'
    index = fasta.with_suffix('.fa.fai')
    if fasta.is_file() and index.is_file() and not fasta.is_symlink() and not index.is_symlink():
        PRONTO_IGV_REFERENCE_FILES.setdefault(build, {'fasta': str(fasta), 'index': str(index)})
    if build in PRONTO_IGV_REFERENCE_FILES and not any(PRONTO_IGV_REFERENCES[build].values()):
        PRONTO_IGV_REFERENCES[build] = {
            'fastaURL': f'/igv/references/{build}/fasta/',
            'indexURL': f'/igv/references/{build}/index/',
        }
