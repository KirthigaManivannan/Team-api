
from app.services.duplicate_service import check_and_register_invoice


def test_new_invoice_is_registered(tmp_path):
    db_path = tmp_path / "test_invoices.db"

    result = check_and_register_invoice(
        {
            "invoice_number": "INV-101",
            "supplier_name": "ABC Technologies",
            "invoice_date": "2026-11-12",
        },
        db_path=db_path,
    )

    assert result["duplicate"] is False
    assert result["message"] == "New invoice registered successfully."


def test_existing_invoice_is_detected_as_duplicate(tmp_path):
    db_path = tmp_path / "test_invoices.db"

    invoice = {
        "invoice_number": "INV-102",
        "supplier_name": "XYZ Solutions",
        "invoice_date": "2026-11-12",
    }

    check_and_register_invoice(invoice, db_path=db_path)

    result = check_and_register_invoice(invoice, db_path=db_path)

    assert result["duplicate"] is True
    assert result["message"] == "This invoice already exists."


def test_different_invoice_is_not_duplicate(tmp_path):
    db_path = tmp_path / "test_invoices.db"

    check_and_register_invoice(
        {
            "invoice_number": "INV-103",
            "supplier_name": "ABC Technologies",
            "invoice_date": "2026-11-12",
        },
        db_path=db_path,
    )

    result = check_and_register_invoice(
        {
            "invoice_number": "INV-104",
            "supplier_name": "ABC Technologies",
            "invoice_date": "2026-11-12",
        },
        db_path=db_path,
    )

    assert result["duplicate"] is False
