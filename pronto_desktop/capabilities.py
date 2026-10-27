"""Native Python PDF support, with optional legacy Poppler fallback."""
import shutil

PDF_TOOL_HELP = (
    "PDF-leseren mangler eller kunne ikke lastes. "
    "Kjør PRONTO_INSTALL.cmd for å installere pypdfium2 i Python FELLES, og start Python FELLES / PRONTO på nytt. "
    "Se docs/desktop-app.md."
)


def capabilities() -> dict[str, bool]:
    result = {name: shutil.which(name) is not None for name in ("pdfinfo", "pdftoppm")}
    from pronto_report.renderers.pdfium import available
    poppler=all(result.values())
    result['pdfium']=available()
    result["pdf"] = result['pdfium'] or poppler
    return result
