"""Settings come from environment variables (optionally loaded from a local .env file)."""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str
    openrouter_model: str
    openrouter_base_url: str
    llm_timeout: int
    max_upload_mb: int
    max_pdf_pages: int
    min_pdf_text_chars: int
    max_llm_chars: int
    tesseract_cmd: str
    ocr_lang: str

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def get_settings() -> Settings:
    """Read settings fresh each call so tests (and .env edits) take effect."""
    env = os.environ.get
    return Settings(
        openrouter_api_key=env("OPENROUTER_API_KEY", "").strip(),
        openrouter_model=env("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip(),
        openrouter_base_url=env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/"),
        llm_timeout=int(env("LLM_TIMEOUT_SECONDS", "60")),
        max_upload_mb=int(env("MAX_UPLOAD_MB", "10")),
        max_pdf_pages=int(env("MAX_PDF_PAGES", "10")),
        min_pdf_text_chars=int(env("MIN_PDF_TEXT_CHARS", "50")),
        max_llm_chars=int(env("MAX_LLM_CHARS", "30000")),
        tesseract_cmd=env("TESSERACT_CMD", "").strip(),
        ocr_lang=env("OCR_LANG", "eng").strip() or "eng",
    )
