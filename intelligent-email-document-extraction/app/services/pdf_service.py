"""Digital PDFs use PyMuPDF text extraction; pages without a text layer fall back to OCR."""
from app.config import get_settings
from app.errors import PDFError
from app.services import ocr_service


def extract_pdf(path: str) -> dict:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise PDFError("PyMuPDF is not installed on the server.", status_code=500) from exc

    settings = get_settings()
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        doc = fitz.open(stream=data, filetype="pdf")  # in memory: no file handle left open
    except Exception as exc:
        raise PDFError("This PDF could not be opened. It may be corrupt.") from exc

    warnings = []
    with doc:
        if doc.needs_pass:
            raise PDFError("This PDF is password-protected.")
        total_pages = len(doc)
        if total_pages == 0:
            raise PDFError("This PDF has no pages.")
        n = min(total_pages, settings.max_pdf_pages)
        if total_pages > n:
            warnings.append(f"Only the first {n} of {total_pages} pages were read.")

        texts, ocr_pages = [], 0
        for i in range(n):
            page = doc[i]
            text = page.get_text("text").strip()
            if len(text) < settings.min_pdf_text_chars:  # no usable text layer -> scanned page
                try:
                    png = page.get_pixmap(dpi=200).tobytes("png")
                except Exception as exc:
                    raise PDFError(f"Page {i + 1} could not be rendered.") from exc
                ocr_text = ocr_service.ocr_bytes(png)
                if len(ocr_text) > len(text):
                    text, ocr_pages = ocr_text, ocr_pages + 1
            texts.append(text)

    if ocr_pages == n:
        input_type, method = "scanned_pdf", "ocr"
    elif ocr_pages:
        input_type, method = "digital_pdf", "pymupdf+ocr"
        warnings.append(f"{ocr_pages} page(s) had no text layer and were read with OCR.")
    else:
        input_type, method = "digital_pdf", "pymupdf"

    return {
        "input_type": input_type,
        "method": method,
        "pages": n,
        "text": "\n\n".join(t for t in texts if t),
        "warnings": warnings,
    }
