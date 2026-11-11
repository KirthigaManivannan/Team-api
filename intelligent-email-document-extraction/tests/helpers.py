"""Shared test helpers (sample data and fake LLM responses)."""
import json
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

INVOICE_TEXT = """ACME Supplies Ltd
INVOICE
Invoice number: INV-2024-0042
Invoice date: 2024-03-01
Due date: 2024-03-31
Customer: Globex Corporation
Description  Qty  Unit price  Total
Widget A  10  25.00  250.00
Widget B  2  100.00  200.00
Subtotal 450.00
Tax 45.00
Total amount: 495.00 USD
Payment terms: Net 30
"""

INVOICE_FIELDS = {
    "invoice_number": "INV-2024-0042", "supplier_name": "ACME Supplies Ltd", "customer_name": "Globex Corporation",
    "invoice_date": "2024-03-01", "due_date": "2024-03-31", "currency": "USD", "subtotal": 450.0, "tax": 45.0,
    "total_amount": 495.0, "payment_terms": "Net 30",
}
INVOICE_ITEMS = [
    {"description": "Widget A", "quantity": 10, "unit_price": 25.0, "line_total": 250.0},
    {"description": "Widget B", "quantity": 2, "unit_price": 100.0, "line_total": 200.0},
]


class FakeResponse:
    def __init__(self, content=None, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"choices": [{"message": {"content": content}}]}

    def json(self):
        return self._payload


def llm_reply(obj):
    return FakeResponse(content=json.dumps(obj))


def make_image_bytes(text="INVOICE 12345", fmt="PNG"):
    img = Image.new("RGB", (900, 220), "white")
    ImageDraw.Draw(img).text((30, 60), text, fill="black", font=ImageFont.load_default(size=72))
    buf = BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()
