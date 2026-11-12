import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
from pathlib import Path
import shutil

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.errors import AppError
from app.routers import document, email, extraction, duplicate, matching, payment, export, gmail

from app.services.gmail_scheduler import (
    start_gmail_scheduler,
    stop_gmail_scheduler,
)
ROOT = Path(__file__).resolve().parent.parent

# Read the version from version.txt.
# If the file does not exist during local testing, use "dev".
VERSION_FILE = Path(__file__).parent / "version.txt"
VERSION = VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else "dev"

app = FastAPI(
    title="Intelligent Email & Document Extraction System",
    version=VERSION
)
@app.on_event("startup")
def start_background_tasks():
    start_gmail_scheduler()


@app.on_event("shutdown")
def stop_background_tasks():
    stop_gmail_scheduler()

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )
@app.middleware("http")
async def revalidate_frontend_files(request: Request, call_next):
    """Ask browsers to re-check the UI files, so a new deploy is never hidden by a cached script.js."""
    response = await call_next(request)
    if request.method == "GET" and request.url.path in ("/", "/index.html", "/script.js", "/style.css"):
        response.headers["Cache-Control"] = "no-cache"
    return response

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "version": VERSION}
@app.get("/health/ocr", tags=["health"])
def check_ocr():
    import pytesseract

    from app.config import get_settings

    settings = get_settings()

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    executable = shutil.which("tesseract")

    try:
        version = str(pytesseract.get_tesseract_version())
        return {
            "tesseract_found": True,
            "executable": executable,
            "version": version
        }
    except Exception as exc:
        return {
            "tesseract_found": False,
            "executable": executable,
            "error": str(exc)
        }


app.include_router(email.router)
app.include_router(document.router)
app.include_router(extraction.router)
app.include_router(duplicate.router)
app.include_router(matching.router)
app.include_router(payment.router)
app.include_router(export.router)
app.include_router(gmail.router)

# Serve the web UI last so API routes take priority.
frontend_dir = ROOT / "frontend"

if frontend_dir.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=frontend_dir, html=True),
        name="frontend"
    )
