"""Load only declared, hash-verified local images for HTML reports."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pronto_report.models import ReportData


_MAX_ATTACHMENT_BYTES = 12 * 1024 * 1024
_MAX_PDF_PAGES = 20


def _attachment_path(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name:
        raise ValueError("Invalid attachment path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Invalid attachment path")
    return path


def _pdf_pages(payload: bytes) -> tuple[tuple[str, bytes], ...]:
    try:
        from pdf2image import convert_from_bytes, pdfinfo_from_bytes

        page_count = int(pdfinfo_from_bytes(payload)["Pages"])
        if not 1 <= page_count <= _MAX_PDF_PAGES:
            raise ValueError("PDF plot exceeds page limit")
        pages = convert_from_bytes(payload, dpi=110, thread_count=1)
    except (ImportError, KeyError, OSError, RuntimeError, ValueError) as error:
        raise ValueError("Unable to render declared PDF plot") from error
    images = []
    for page in pages:
        buffer = BytesIO()
        page.convert("RGB").save(buffer, format="JPEG", quality=82)
        images.append(("image/jpeg", buffer.getvalue()))
    return tuple(images)


def load_plot_images(report: ReportData, root: Path) -> dict[str, tuple[tuple[str, bytes], ...]]:
    """Resolve declared assets under root, verify hashes, and rasterize PDF pages."""
    source_root = Path(root).resolve()
    images = {}
    for attachment in report.attachments:
        media_type = str(attachment["mediaType"])
        if media_type not in {"image/png", "image/jpeg", "application/pdf"}:
            continue
        path = _attachment_path(source_root, str(attachment["name"]))
        if path.stat().st_size > _MAX_ATTACHMENT_BYTES:
            raise ValueError("Declared attachment exceeds size limit")
        payload = path.read_bytes()
        if sha256(payload).hexdigest() != attachment["sha256"]:
            raise ValueError("Declared attachment hash mismatch")
        asset_id = str(attachment["assetId"])
        images[asset_id] = (
            _pdf_pages(payload) if media_type == "application/pdf" else ((media_type, payload),)
        )
    return images
