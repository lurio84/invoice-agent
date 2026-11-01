"""PDF -> plain text, or page images when the PDF has no text layer (scans)."""
import base64
import io
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium


def pdf_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages).strip()


def pdf_images(path: Path, scale: float = 2.0) -> list[str]:
    """Each page as a base64 PNG."""
    out = []
    for page in pdfium.PdfDocument(str(path)):
        buf = io.BytesIO()
        page.render(scale=scale).to_pil().save(buf, "PNG")
        out.append(base64.b64encode(buf.getvalue()).decode())
    return out
