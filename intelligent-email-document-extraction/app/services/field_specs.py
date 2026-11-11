"""What to extract for each document type. Plain Python so it is easy to read and test."""


def F(key, label, type_="string", required=False):
    return {"key": key, "label": label, "type": type_, "required": required}


DOC_TYPES = ["Purchase Order", "Invoice", "Sales Order", "Delivery Note", "Other"]

SPECS = {
    "Purchase Order": {
        "fields": [
            F("po_number", "PO number", "string", True),
            F("supplier_name", "Supplier name", "string", True),
            F("buyer_name", "Buyer name", "string", True),
            F("order_date", "Order date", "date", True),
            F("delivery_date", "Delivery date", "date"),
            F("currency", "Currency", "currency"),
            F("tax", "Tax", "number"),
            F("total_amount", "Total amount", "number", True),
            F("payment_terms", "Payment terms"),
        ],
        "items": [
            F("description", "Description", "string", True),
            F("quantity", "Quantity", "number", True),
            F("unit_price", "Unit price", "number"),
            F("line_total", "Line total", "number"),
        ],
    },
    "Invoice": {
        "fields": [
            F("invoice_number", "Invoice number", "string", True),
            F("supplier_name", "Supplier name", "string", True),
            F("customer_name", "Customer name", "string", True),
            F("invoice_date", "Invoice date", "date", True),
            F("due_date", "Due date", "date"),
            F("currency", "Currency", "currency"),
            F("subtotal", "Subtotal", "number"),
            F("tax", "Tax", "number"),
            F("total_amount", "Total amount", "number", True),
            F("payment_terms", "Payment terms"),
        ],
        "items": [
            F("description", "Description", "string", True),
            F("quantity", "Quantity", "number", True),
            F("unit_price", "Unit price", "number"),
            F("line_total", "Line total", "number"),
        ],
    },
    "Sales Order": {
        "fields": [
            F("sales_order_number", "Sales order number", "string", True),
            F("customer_name", "Customer name", "string", True),
            F("order_date", "Order date", "date", True),
            F("delivery_date", "Delivery date", "date"),
            F("currency", "Currency", "currency"),
            F("total_amount", "Total amount", "number", True),
        ],
        "items": [
            F("description", "Description", "string", True),
            F("quantity", "Quantity", "number", True),
            F("unit_price", "Unit price", "number"),
            F("line_total", "Line total", "number"),
        ],
    },
    "Delivery Note": {
        "fields": [
            F("delivery_note_number", "Delivery note number", "string", True),
            F("supplier_name", "Supplier name", "string", True),
            F("customer_name", "Customer name", "string", True),
            F("delivery_date", "Delivery date", "date", True),
            F("related_po_number", "Related PO number", "string"),
        ],
        "items": [
            F("description", "Delivered item", "string", True),
            F("quantity", "Quantity", "number", True),
        ],
    },
    "Other": {
        "fields": [
            F("suggested_category", "Suggested category", "string"),
            F("title", "Title"),
            F("reference_number", "Reference number"),
            F("document_date", "Document date", "date"),
            F("sender_name", "Sender"),
            F("recipient_name", "Recipient"),
            F("currency", "Currency", "currency"),
            F("total_amount", "Total amount", "number"),
            F("summary", "Summary"),
        ],
        "items": [],
    },
}

# Values the model writes itself (not copied from the document), so they are not checked against the source text.
GENERATED_KEYS = {"summary", "suggested_category"}

KNOWN_CURRENCIES = {
    "USD", "EUR", "GBP", "INR", "JPY", "CNY", "AUD", "CAD", "CHF", "SGD", "HKD", "NZD", "SEK", "NOK",
    "DKK", "AED", "SAR", "ZAR", "BRL", "MXN", "KRW", "THB", "MYR", "IDR", "PHP", "TRY", "PLN", "CZK",
}


def spec_for(doc_type: str) -> dict:
    return SPECS.get(doc_type, SPECS["Other"])
