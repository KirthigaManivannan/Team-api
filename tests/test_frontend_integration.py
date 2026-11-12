"""Guards against the 'features exist in Swagger but not in the UI' problem."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
SCRIPT = Path(__file__).resolve().parent.parent / "frontend" / "script.js"


def test_script_calls_the_invoice_feature_endpoints():
    js = SCRIPT.read_text(encoding="utf-8")
    for path in ("/invoices/check-duplicate", "/payment/check-due-date", "/match/po-invoice"):
        assert path in js, f"frontend/script.js never calls {path}"


def test_page_has_csv_export_button():
    page = client.get("/")
    assert page.status_code == 200
    assert 'id="export-csv"' in page.text


def test_frontend_files_are_revalidated_by_browsers():
    for path in ("/", "/script.js", "/style.css"):
        r = client.get(path)
        assert r.status_code == 200
        assert r.headers.get("cache-control") == "no-cache"