"""Serve explicitly configured public reference sequences on the app's origin."""
import os
import stat
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_safe

from .alignment_ranges import RangeNotSatisfiable, iter_range, parse_single_range


@require_safe
def reference_component(request, build: str, component: str):
    if not request.user.is_authenticated or not request.user.is_active:
        return HttpResponse(status=401)
    if build not in {'GRCh37', 'GRCh38'} or component not in {'fasta', 'index'}:
        return HttpResponse(status=404)
    pair = settings.PRONTO_IGV_REFERENCE_FILES.get(build, {})
    if not pair.get('fasta') or not pair.get('index'):
        return HttpResponse(status=404)
    handle = None
    try:
        path = Path(pair[component])
        if path.is_symlink():
            return HttpResponse(status=404)
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        handle = os.fdopen(descriptor, 'rb')
        metadata = os.fstat(handle.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 1:
            handle.close()
            return HttpResponse(status=404)
        size = metadata.st_size
    except OSError:
        if handle is not None:
            handle.close()
        return HttpResponse(status=404)
    try:
        header = request.headers.get('Range')
        if header:
            start, end = parse_single_range(header, size)
            status = 206
        else:
            if request.method != 'HEAD' and (component == 'fasta' or size > 8 * 1024 * 1024):
                raise RangeNotSatisfiable('range required')
            start, end, status = 0, size - 1, 200
    except ValueError:  # Includes malformed ranges and oversized integer fields.
        handle.close()
        response = HttpResponse(status=416)
        response['Content-Range'] = f'bytes */{size}'
    else:
        if request.method == 'HEAD':
            handle.close()
            response = HttpResponse(status=status, content_type='application/octet-stream')
        else:
            response = StreamingHttpResponse(iter_range(handle, start, end), status=status,
                                             content_type='application/octet-stream')
        response['Content-Length'] = str(end - start + 1)
        if status == 206:
            response['Content-Range'] = f'bytes {start}-{end}/{size}'
    response['Accept-Ranges'] = 'bytes'
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
