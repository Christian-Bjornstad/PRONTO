from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pytest
from PIL import Image
from reportlab.pdfgen.canvas import Canvas


def pdf_bytes(pages=1, size=(240, 180)):
    output=BytesIO();canvas=Canvas(output,pagesize=size)
    for index in range(pages):
        canvas.setFillColorRGB(0.1,0.4,0.7)
        canvas.rect(20,20,100,60,fill=1)
        canvas.drawString(24,100,f'Plot page {index+1}')
        canvas.showPage()
    canvas.save()
    return output.getvalue()


def test_pdf_import_and_render_without_poppler(monkeypatch):
    import shutil
    from pronto_desktop.capabilities import capabilities
    from pronto_report.renderers.assets import _pdf_pages
    from pronto_ingest.importer import _validate_plot
    monkeypatch.setattr(shutil,'which',lambda name: None)
    assert capabilities()['pdf']
    assert capabilities()['pdfium']
    payload=pdf_bytes(3)
    _validate_plot(payload,'application/pdf')
    images=_pdf_pages(payload)
    assert len(images)==3
    for media,content in images:
        assert media=='image/jpeg'
        with Image.open(BytesIO(content)) as image:
            assert image.width>300 and image.height>200
            assert any(low<high for low,high in image.getextrema())


def test_native_pdf_rejects_bad_files_and_excessive_pages_before_render():
    from pronto_report.renderers.assets import _pdf_pages
    for payload in (b'not a PDF',pdf_bytes(101),pdf_bytes(size=(100000,100000))):
        with pytest.raises(ValueError):
            _pdf_pages(payload)


def test_native_pdf_concurrent_requests_return_all_pages():
    from pronto_report.renderers.assets import _pdf_pages
    payload=pdf_bytes(7)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(_pdf_pages,[payload]*3))
    assert [len(result) for result in results]==[7,7,7]


def test_long_native_pdf_keeps_every_page():
    from pronto_report.renderers.assets import _pdf_pages
    assert len(_pdf_pages(pdf_bytes(57,size=(50,50))))==57


def test_installer_accepts_native_pdf_backend_without_poppler(tmp_path, monkeypatch):
    import shutil
    import install_python_felles
    from pathlib import Path
    root=Path(__file__).resolve().parents[3]
    monkeypatch.setattr(shutil,'which',lambda name: None)
    assert install_python_felles.install(project_dir=root,user_site=tmp_path,
        pip_main=lambda args: 0,importer=lambda name: None)==0
