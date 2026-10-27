"""In-process PDF rendering; PDFium calls and native object lifetimes are serialized."""
from io import BytesIO
import importlib
import math
import threading

_LOCK = threading.RLock()


def available():
    with _LOCK:
        try:
            importlib.import_module('pypdfium2')
            return True
        except (ImportError, OSError, RuntimeError):
            return False


def render_pages(payload, *, max_pages=100, max_pixels=200_000_000):
    if len(payload)>12*1024*1024:
        raise ValueError('PDF plot exceeds attachment size limit')
    # PDFium is not thread safe, including access to different documents.
    # https://pypdfium2.readthedocs.io/en/stable/python_api.html#incompatibility-with-threading
    with _LOCK:
        pdfium=importlib.import_module('pypdfium2')
        document=None
        try:
            document=pdfium.PdfDocument(payload)
            if not 1<=len(document)<=max_pages:
                raise ValueError('PDF plot exceeds page limit')
            images=[];pixels=0;scale=110/72
            for index in range(len(document)):
                page=None;bitmap=None;image=None;rgb=None
                try:
                    page=document[index]
                    width,height=page.get_size()
                    if not all(math.isfinite(value) and value>0 for value in (width,height)):
                        raise ValueError('Invalid PDF page size')
                    page_pixels=math.ceil(width*scale)*math.ceil(height*scale)
                    pixels+=page_pixels
                    if page_pixels>32_000_000 or pixels>max_pixels:
                        raise ValueError('PDF plot exceeds raster size limit')
                    bitmap=page.render(scale=scale)
                    image=bitmap.to_pil()
                    rgb=image.convert('RGB')
                    output=BytesIO();rgb.save(output,format='JPEG',quality=82)
                    images.append(('image/jpeg',output.getvalue()))
                finally:
                    if rgb is not None: rgb.close()
                    if image is not None: image.close()
                    if bitmap is not None: bitmap.close()
                    if page is not None: page.close()
            return tuple(images)
        except (ImportError, OSError, RuntimeError, ValueError, OverflowError) as error:
            raise ValueError('Unable to render declared PDF plot') from error
        finally:
            if document is not None: document.close()
