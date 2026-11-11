# Intelligent Email & Document Extraction System

Paste an email or upload a PDF/image of a business document. The app reads the text, works out whether it is a
**Purchase Order, Invoice, Sales Order, Delivery Note or Other**, extracts the key fields into JSON, checks them,
and shows the result in a web page where you can fix values, copy the JSON or download it.

## How it works

1. **Input**: pasted email, `.eml` file, or PDF / PNG / JPG upload (max 10 MB each).
2. **Text extraction**
   - Email: subject, sender, recipient and body (HTML is converted to text). Attachments in an `.eml` are read too.
   - Digital PDF: text layer via **PyMuPDF** (no OCR).
   - Scanned PDF: pages without a text layer are rendered to images and read with **Tesseract OCR**.
   - Image: preprocessed (greyscale, upscale, contrast, sharpen) and read with Tesseract.
3. **Classification + extraction**: two calls to your chosen **OpenRouter** model. The document is sent as untrusted data, and the model is told to use `null` instead of guessing.
4. **Validation** (Python): required fields, ISO dates, numbers, quantities, currency codes, totals that don't add up, and values that cannot be found in the source text. Values are never changed; problems are reported as warnings or errors.
5. **Review**: edit values, copy or download JSON.

No database is used. Nothing is stored on the server (uploads are processed in a temporary folder that is deleted immediately).

## Project structure

```
app/                 FastAPI backend
  main.py            app, /health, serves the frontend
  config.py          settings from environment variables / .env
  routers/           email.py, document.py, extraction.py   (HTTP endpoints)
  services/          email, pdf, ocr, file, llm, validation, field_specs
  schemas/           Pydantic request/response models
frontend/            index.html, style.css, script.js
tests/               pytest tests (LLM is mocked)
.github/workflows/   ci.yml (pull requests), deploy.yml (push to main)
Dockerfile, requirements*.txt, .env.example
```

## Run it on Windows (PowerShell)

**Install once:** Python 3.12 (tick "Add python.exe to PATH") and Tesseract OCR from
<https://github.com/UB-Mannheim/tesseract/wiki> (default path `C:\Program Files\Tesseract-OCR`).
Add that folder to PATH, or set `TESSERACT_CMD` in `.env` (see below). Check with `tesseract --version`.

```powershell
cd intelligent-email-document-extraction
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements-dev.txt
Copy-Item .env.example .env
notepad .env                         # paste your OpenRouter key (see below)
python -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. API docs: <http://127.0.0.1:8000/docs>.

### OpenRouter API key

1. Create an account at <https://openrouter.ai> and open **Keys** → **Create Key**.
2. In `.env` set `OPENROUTER_API_KEY=your-key`.
3. Optionally set `OPENROUTER_MODEL` (any model id from openrouter.ai/models; default `openai/gpt-4o-mini`). Pick a model that reliably returns JSON. Free models may be rate-limited.

Without a key the app still starts; `/extract` returns a clear 503 message.

## Tests

```powershell
python -m pytest -v
```

Tests never call OpenRouter. OCR tests are skipped if Tesseract is missing; the PDF tests need PyMuPDF (installed by requirements).

## Docker

```powershell
docker build -t intelligent-extraction .
docker run --rm -p 8000:8000 --env-file .env intelligent-extraction
```

The container installs Tesseract, listens on `0.0.0.0` and uses `$PORT` (Railway) or 8000.

## GitHub Actions and Railway

1. Push the project to GitHub (`git init`, `git add .`, `git commit`, add remote, push). `.env` is git-ignored.
2. In Railway: create a project and a service, add variable `OPENROUTER_API_KEY` (and optionally `OPENROUTER_MODEL`) to the service, and generate a public domain.
3. Railway → project **Settings → Tokens** → create a **project token**.
4. GitHub repo → **Settings → Secrets and variables → Actions**:
   - Secret `RAILWAY_TOKEN`: the project token
   - Variables `RAILWAY_SERVICE` (service name), `RAILWAY_ENV` (e.g. `production`), `APP_URL` (e.g. `https://your-app.up.railway.app`)
5. `ci.yml` runs tests and a Docker build on pull requests to `main`. `deploy.yml` runs tests on push to `main`, deploys with the Railway CLI, then polls `/health`.

## API examples

```powershell
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/email/submit -H "Content-Type: application/json" `
  -d '{"subject":"PO 4500123","sender":"buyer@x.com","recipient":"orders@y.com","body":"Please ship 10 widgets"}'

curl -X POST http://127.0.0.1:8000/email/upload -F "file=@message.eml"
curl -X POST http://127.0.0.1:8000/document/upload -F "file=@invoice.pdf"

curl -X POST http://127.0.0.1:8000/extract -H "Content-Type: application/json" `
  -d '{"filename":"invoice.pdf","text":"INVOICE INV-1 ..."}'
```

Errors return `{"detail": "..."}` with 400/413/415 (bad upload), 422 (unreadable or empty), 502 (AI service failed or returned bad JSON) or 503 (no API key).

## Known limitations and ideas

- Dates are only accepted as `YYYY-MM-DD`; other formats are kept as written and flagged for review.
- Validation runs on the original extraction; edits in the browser are not re-validated (they are listed in `user_edited_fields`).
- OCR quality depends on scan quality; only English OCR data is installed by default (`OCR_LANG`).
- Long documents are truncated to `MAX_LLM_CHARS` (30,000) for the AI; PDFs to the first 10 pages.
- The `/extract` endpoint makes two paid LLM calls per document.
- No login or rate limiting; add them before exposing the app publicly.
- Future: automatic email forwarding via a dedicated mailbox, batch export (CSV), a database for history.

## CI/CD Pipeline

This project uses GitHub Actions for continuous integration.
Automated tests and Docker image builds run whenever a pull request is created against the main branch.