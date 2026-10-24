"""Public, fixed artwork with no database access or user-controlled paths."""
from functools import lru_cache
from hashlib import sha256

from django.http import HttpResponse, HttpResponseNotModified
from django.views.decorators.http import require_safe

from pronto_report.branding import ASSET_ROOT


@lru_cache(maxsize=1)
def _favicon():
    payload = (ASSET_ROOT / 'pronto.ico').read_bytes()
    return payload, '"' + sha256(payload).hexdigest() + '"'


@require_safe
def favicon(request):
    payload, etag = _favicon()
    response = (HttpResponseNotModified() if request.headers.get('If-None-Match') == etag
                else HttpResponse(payload, content_type='image/vnd.microsoft.icon'))
    response['ETag'] = etag
    response['Cache-Control'] = 'public, max-age=86400'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
