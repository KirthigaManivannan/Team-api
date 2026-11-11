import os
import shutil
from io import BytesIO

import pytest
from PIL import Image

from app.errors import FileError
from app.services import file_service, ocr_service
from tests.helpers import make_image_bytes

def _tesseract_available():
    from app.config import get_settings

    cmd = get_settings().tesseract_cmd
    if cmd and os.path.exists(cmd):
        ocr_service.pytesseract.pytesseract.tesseract_cmd = cmd
        return True
    default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if shutil.which("tesseract") is None and os.path.exists(default):
        ocr_service.pytesseract.pytesseract.tesseract_cmd = default
        return True
    return shutil.which("tesseract") is not None


needs_tesseract = not _tesseract_available()


def test_preprocess_returns_greyscale_and_upscales_small_images():
    out = ocr_service.preprocess(Image.new("RGB", (200, 100), "white"))
    assert out.mode == "L" and out.size == (600, 300)  # upscaled 3x (the cap)


def test_image_ocr_reads_text():
    if needs_tesseract:
        pytest.skip("tesseract not installed")
    result = file_service.extract_text("scan.png", make_image_bytes("INVOICE 12345"))
    assert result["input_type"] == "image" and result["method"] == "ocr"
    assert "INVOICE" in result["text"].upper() and "12345" in result["text"]


def test_jpeg_is_accepted():
    if needs_tesseract:
        pytest.skip("tesseract not installed")
    result = file_service.extract_text("scan.JPG", make_image_bytes("ORDER 777", "JPEG"))
    assert "777" in result["text"]


def test_blank_image_gives_clear_error():
    if needs_tesseract:
        pytest.skip("tesseract not installed")
    buf = BytesIO()
    Image.new("RGB", (400, 200), "white").save(buf, "PNG")
    with pytest.raises(FileError) as e:
        file_service.extract_text("blank.png", buf.getvalue())
    assert e.value.status_code == 422


def test_digital_pdf_uses_text_layer_not_ocr():
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Purchase Order PO-98765 for ACME Supplies Ltd, total 1,250.00 EUR", fontsize=11)
    data = doc.tobytes()
    result = file_service.extract_text("po.pdf", data)
    assert result["input_type"] == "digital_pdf" and result["method"] == "pymupdf"
    assert "PO-98765" in result["text"]


def test_corrupt_pdf_is_rejected():
    pytest.importorskip("fitz")
    with pytest.raises(Exception) as e:
        file_service.extract_text("bad.pdf", b"%PDF-1.4 this is not really a pdf")
    assert getattr(e.value, "status_code", 0) == 422


def test_invalid_formats_and_limits():
    with pytest.raises(FileError) as e:
        file_service.extract_text("notes.txt", b"hello")
    assert e.value.status_code == 415
    with pytest.raises(FileError) as e:
        file_service.extract_text("fake.pdf", b"just text pretending to be a pdf")
    assert e.value.status_code == 415
    with pytest.raises(FileError) as e:
        file_service.extract_text("empty.png", b"")
    assert e.value.status_code == 400
    big = b"%PDF" + b"0" * (file_service.get_settings().max_upload_bytes + 1)
    with pytest.raises(FileError) as e:
        file_service.extract_text("big.pdf", big)
    assert e.value.status_code == 413


def test_temp_file_is_cleaned_up():
    import os

    with file_service.temp_file(b"abc", ".pdf") as path:
        assert os.path.exists(path)
        assert os.path.basename(path) == "upload.pdf"  # never the user's filename
    assert not os.path.exists(path)


def test_upload_api_rejects_bad_files():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    r = c.post("/document/upload", files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 415 and "Unsupported" in r.json()["detail"]
    if not needs_tesseract:
        ok = c.post("/document/upload", files={"file": ("a.png", make_image_bytes("INVOICE 12345"), "image/png")})
        assert ok.status_code == 200 and "12345" in ok.json()["text"]
