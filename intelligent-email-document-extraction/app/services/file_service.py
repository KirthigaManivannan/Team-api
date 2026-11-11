"""Upload validation and routing of a file to the right text extractor."""
import os
import tempfile
from contextlib import contextmanager


from app.config import get_settings
from app.errors import FileError
from app.services import ocr_service, pdf_service

ALLOWED_EXTENSIONS = {".pdf": "pdf", ".png": "image", ".jpg": "image", ".jpeg": "image"}


def sniff(data: bytes):
    """Identify a file by its first bytes, not its name."""
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff"):
        return "image"
    return None


def read_upload(upload) -> bytes:
    """Read an UploadFile, refusing anything over the size limit."""
    limit = get_settings().max_upload_bytes
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise FileError(f"File is too large. The limit is {get_settings().max_upload_mb} MB.", 413)
    return data


def validate_upload(filename: str, data: bytes) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise FileError("Unsupported file type. Upload a PDF, PNG or JPG/JPEG file.", 415)
    if not data:
        raise FileError("The file is empty.", 400)
    if len(data) > get_settings().max_upload_bytes:
        raise FileError(f"File is too large. The limit is {get_settings().max_upload_mb} MB.", 413)
    kind = sniff(data)
    if kind != ALLOWED_EXTENSIONS[ext]:
        raise FileError("The file contents do not match its extension, or the file is not a valid PDF/PNG/JPG.", 415)
    return kind


@contextmanager
def temp_file(data: bytes, suffix: str):
    """Write to a private temp dir under a random name (never the user's filename); always cleaned up."""
    with tempfile.TemporaryDirectory(prefix="extract_", ignore_cleanup_errors=True) as folder:
        path = os.path.join(folder, "upload" + suffix)
        with open(path, "wb") as fh:
            fh.write(data)
        yield path


def extract_text(filename: str, data: bytes) -> dict:
    safe_name = os.path.basename(filename or "upload")
    kind = validate_upload(safe_name, data)

    if kind == "pdf":
        with temp_file(data, ".pdf") as path:
            result = pdf_service.extract_pdf(path)
    else:
        result = {
            "input_type": "image",
            "method": "ocr",
            "pages": 1,
            "text": ocr_service.ocr_bytes(data),
            "warnings": [],
        }

    if not result["text"].strip():
        raise FileError("No readable text was found in this file. Try a clearer scan or a higher-resolution image.", 422)
    result["filename"] = safe_name
    return result
