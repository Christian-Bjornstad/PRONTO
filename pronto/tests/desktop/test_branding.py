"""The shipped icon works in native windows, web pages and standalone reports."""
import base64
from io import BytesIO
import os
import re

import pytest
from PIL import Image

from pronto_report.branding import ASSET_ROOT, favicon_data_uri


def test_bundled_windows_icon_has_all_standard_sizes_and_transparent_edges():
    with Image.open(ASSET_ROOT / 'pronto.ico') as icon:
        assert icon.ico.sizes() >= {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}
        assert icon.getpixel((0, 0))[3] == 0
    with Image.open(BytesIO(base64.b64decode(favicon_data_uri().split(',', 1)[1]))) as favicon:
        assert favicon.format == 'PNG' and favicon.size == (64, 64)


def test_standalone_report_embeds_icon_without_external_request():
    from pronto.tests.reporting.test_pronto_output_adapter import build_report
    from pronto_report.renderers.html import render_html
    html = render_html(build_report())
    icon = re.search(r'<link rel="icon"[^>]+href="([^"]+)"', html)
    assert icon and icon[1] == favicon_data_uri()
    assert '<img src="' + favicon_data_uri() + '" width="28" height="28" alt="">' in html


def test_favicon_is_public_cacheable_and_rejects_mutations(client):
    response = client.get('/favicon.ico')
    assert response.status_code == 200
    assert response.content == (ASSET_ROOT / 'pronto.ico').read_bytes()
    assert response['Content-Type'] == 'image/vnd.microsoft.icon'
    assert response['X-Content-Type-Options'] == 'nosniff'
    assert response['Cache-Control'] == 'public, max-age=86400'
    assert client.get('/favicon.ico', HTTP_IF_NONE_MATCH=response['ETag']).status_code == 304
    assert client.post('/favicon.ico').status_code == 405


def test_login_displays_matching_public_brand(client):
    html = client.get('/accounts/login/').content.decode()
    assert '<link rel="icon" href="/favicon.ico">' in html
    assert '<img src="/favicon.ico" width="48" height="48" alt="">' in html


def test_native_application_uses_shipped_icon(request):
    pytest.importorskip('PyQt6')
    pytest.importorskip('pytestqt')
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    qapp = request.getfixturevalue('qapp')
    from PyQt6.QtWidgets import QWidget
    from pronto_desktop.branding import apply_application_branding, application_icon, icon_pixmap
    old = qapp.windowIcon()
    try:
        apply_application_branding(qapp)
        assert not application_icon().isNull()
        assert not icon_pixmap(40).isNull()
        widget = QWidget()
        assert not widget.windowIcon().isNull()
        widget.close()
    finally:
        qapp.setWindowIcon(old)
