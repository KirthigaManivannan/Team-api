from app.services.validation_service import validate
from tests.helpers import INVOICE_FIELDS, INVOICE_ITEMS, INVOICE_TEXT


def _issues(report, field):
    return [i for i in report["issues"] if i["field"] == field]


def test_clean_invoice_is_valid():
    r = validate("Invoice", dict(INVOICE_FIELDS), [dict(x) for x in INVOICE_ITEMS], source_text=INVOICE_TEXT, confidence=0.9)
    assert r["status"] == "valid", r["issues"]
    assert r["missing_fields"] == [] and r["uncertain_fields"] == []


def test_missing_required_field_needs_review_and_stays_null():
    fields = {**INVOICE_FIELDS, "invoice_number": None}
    r = validate("Invoice", fields, INVOICE_ITEMS)
    assert "invoice_number" in r["missing_fields"] and r["status"] == "needs_review"
    assert fields["invoice_number"] is None  # not filled in


def test_missing_optional_field_is_info_only():
    r = validate("Invoice", {**INVOICE_FIELDS, "due_date": None, "payment_terms": None}, INVOICE_ITEMS)
    assert r["status"] == "valid"
    assert {"due_date", "payment_terms"} <= set(r["missing_fields"])


def test_bad_date_is_error_and_value_is_not_changed():
    fields = {**INVOICE_FIELDS, "invoice_date": "01/03/2024", "due_date": "2024-02-30"}
    r = validate("Invoice", fields, INVOICE_ITEMS)
    assert r["status"] == "invalid"
    assert _issues(r, "invoice_date")[0]["severity"] == "error" and _issues(r, "due_date")
    assert fields["invoice_date"] == "01/03/2024"


def test_numbers_must_be_numbers_and_not_negative():
    r = validate("Invoice", {**INVOICE_FIELDS, "total_amount": "495.00", "tax": -5}, INVOICE_ITEMS)
    assert _issues(r, "total_amount")[0]["severity"] == "error"
    assert "negative" in _issues(r, "tax")[0]["message"]
    r2 = validate("Invoice", {**INVOICE_FIELDS, "total_amount": True}, INVOICE_ITEMS)
    assert _issues(r2, "total_amount")


def test_quantity_checks():
    items = [{"description": "A", "quantity": -1, "unit_price": 1.0}, {"description": "B", "quantity": 0, "unit_price": 1.0},
             {"description": "C", "quantity": "two", "unit_price": 1.0}]
    r = validate("Invoice", INVOICE_FIELDS, items)
    assert _issues(r, "line_items[0].quantity")[0]["severity"] == "error"
    assert _issues(r, "line_items[1].quantity")[0]["severity"] == "warning"
    assert _issues(r, "line_items[2].quantity")[0]["severity"] == "error"


def test_currency_rules():
    assert _issues(validate("Invoice", {**INVOICE_FIELDS, "currency": "dollars"}, INVOICE_ITEMS), "currency")[0]["severity"] == "error"
    assert _issues(validate("Invoice", {**INVOICE_FIELDS, "currency": "ZZZ"}, INVOICE_ITEMS), "currency")[0]["severity"] == "warning"
    assert not _issues(validate("Invoice", INVOICE_FIELDS, INVOICE_ITEMS), "currency")


def test_arithmetic_mismatches_are_warnings():
    r = validate("Invoice", {**INVOICE_FIELDS, "total_amount": 500.0}, INVOICE_ITEMS)
    assert _issues(r, "total_amount") and r["status"] == "needs_review"
    items = [{"description": "A", "quantity": 3, "unit_price": 10.0, "line_total": 99.0}]
    assert _issues(validate("Invoice", INVOICE_FIELDS, items), "line_items[0].line_total")


def test_due_date_before_invoice_date_warns():
    r = validate("Invoice", {**INVOICE_FIELDS, "due_date": "2024-02-01"}, INVOICE_ITEMS)
    assert _issues(r, "due_date")[0]["severity"] == "warning"


def test_no_line_items_flagged():
    r = validate("Purchase Order", {"po_number": "1"}, [])
    assert "line_items" in r["missing_fields"]


def test_value_not_in_source_text_is_marked_uncertain():
    fields = {**INVOICE_FIELDS, "invoice_number": "INV-9999", "total_amount": 777.0}
    r = validate("Invoice", fields, INVOICE_ITEMS, source_text=INVOICE_TEXT)
    assert {"invoice_number", "total_amount"} <= set(r["uncertain_fields"])
    assert r["status"] == "needs_review"


def test_model_uncertain_fields_and_low_confidence():
    r = validate("Invoice", INVOICE_FIELDS, INVOICE_ITEMS, uncertain=["tax"], source_text=INVOICE_TEXT, confidence=0.3)
    assert "tax" in r["uncertain_fields"] and _issues(r, "document_type")


def test_other_document_and_delivery_note():
    r = validate("Other", {"title": "Memo", "summary": "Generated summary not in text"}, [], source_text="Memo about nothing")
    assert r["status"] == "valid" and "summary" not in r["uncertain_fields"]
    dn = validate("Delivery Note", {"delivery_note_number": "DN-1", "supplier_name": "S", "customer_name": "C", "delivery_date": "2024-05-05"},
                  [{"description": "Box", "quantity": 4}])
    assert dn["status"] == "valid"
