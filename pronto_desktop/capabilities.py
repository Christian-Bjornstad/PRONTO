"""External tools used by existing PDF plot rendering."""
import shutil

PDF_TOOL_HELP = (
    "PDF-behandling krever Poppler med pdfinfo og pdftoppm. "
    "Installer Poppler og legg bin-mappen på PATH, og start Python FELLES / PRONTO på nytt. "
    "Se docs/desktop-app.md."
)


def capabilities() -> dict[str, bool]:
    result = {name: shutil.which(name) is not None for name in ("pdfinfo", "pdftoppm")}
    result["pdf"] = all(result.values())
    return result
