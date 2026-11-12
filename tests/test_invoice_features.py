import csv
import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_duplicate_invoice_detection(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "INVOICE_DB_PATH",
        str(tmp_path / "test_invoices.db")
    )

    invoice = {
        "invoice_number": "INV001",
        "supplier_name": "ABC Technologies",
        "invoice_date": "2026-11-12",
    }

    first_response = client.post(
        "/invoices/check-duplicate",
        json=invoice
    )

    assert first_response.status_code == 200
    assert first_response.json()["duplicate"] is False

    second_response = client.post(
        "/invoices/check-duplicate",
        json=invoice
    )

    assert second_response.status_code == 200
    assert second_response.json()["duplicate"] is True


def test_csv_export(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "INVOICE_DB_PATH",
        str(tmp_path / "test_invoices.db")
    )

    invoice = {
        "invoice_number": "INV002",
        "supplier_name": "XYZ Solutions",
        "invoice_date": "2026-11-10",
    }

    client.post("/invoices/check-duplicate", json=invoice)

    response = client.get("/invoices/export")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]

    rows = list(csv.DictReader(io.StringIO(response.text)))

    assert len(rows) == 1
    assert rows[0]["invoice_number"] == "INV002"
    assert rows[0]["supplier_name"] == "XYZ Solutions"