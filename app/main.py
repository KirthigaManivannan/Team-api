
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.errors import AppError
from app.routers import document, email, extraction

ROOT = Path(__file__).resolve().parent.parent

# Read the version from version.txt.
# If the file does not exist during local testing, use "dev".
VERSION_FILE = Path(__file__).parent / "version.txt"
VERSION = VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else "dev"

app = FastAPI(
    title="Intelligent Email & Document Extraction System",
    version=VERSION
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "version": VERSION}


app.include_router(email.router)
app.include_router(document.router)
app.include_router(extraction.router)

# Serve the web UI last so API routes take priority.
frontend_dir = ROOT / "frontend"

if frontend_dir.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=frontend_dir, html=True),
        name="frontend"
    )
