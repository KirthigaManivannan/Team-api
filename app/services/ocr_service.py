"""Image preprocessing and OCR with Tesseract."""
import os
import shutil
from io import BytesIO

import pytesseract
from PIL import Image, ImageFilter, ImageOps

from app.config import get_settings
from app.errors import OCRError

Image.MAX_IMAGE_PIXELS = 50_000_000  # guard against decompression bombs


def preprocess(img: Image.Image) -> Image.Image:
    """Greyscale, fix rotation, upscale small images, stretch contrast, sharpen."""
    img = ImageOps.exif_transpose(img)
    img = img.convert("L")
    longest = max(img.size)
    if longest < 1500:
        scale = min(3.0, 1500 / longest)
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    img = ImageOps.autocontrast(img, cutoff=1)
    return img.filter(ImageFilter.SHARPEN)


def _find_tesseract(configured: str) -> str | None:
    """Use the configured path only if it exists; otherwise look on PATH and in the usual Windows folders."""
    if configured and os.path.isfile(configured):
        return configured
    on_path = shutil.which("tesseract")
    if on_path:
        return on_path
    for candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


def ocr_image(img: Image.Image) -> str:
    settings = get_settings()
    path = _find_tesseract(settings.tesseract_cmd)
    if path:
        pytesseract.pytesseract.tesseract_cmd = path
    try:
        return pytesseract.image_to_string(preprocess(img), lang=settings.ocr_lang).strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise OCRError(
            "Tesseract OCR is not installed or not found. Install it and set TESSERACT_CMD if needed.",
            status_code=500,
        ) from exc
    except pytesseract.TesseractError as exc:
        raise OCRError("OCR failed on this image.") from exc


def ocr_bytes(data: bytes) -> str:
    try:
        img = Image.open(BytesIO(data))
        img.load()
    except Exception as exc:  # unreadable, truncated or too large
        raise OCRError("This image could not be read. It may be corrupt or too large.") from exc
    return ocr_image(img)