def normalize_text(value):
    """Convert text to lowercase and remove extra spaces."""
    return " ".join(value.strip().casefold().split())


def compare_documents(payload):
    """Compare invoice details with purchase order details."""

    po = payload.purchase_order
    invoice = payload.invoice

    issues = []
    checks = {}

    # 1. Compare supplier names
    if normalize_text(po.fields.supplier_name) == normalize_text(
        invoice.fields.supplier_name
    ):
        checks["supplier_name"] = "Match"
    else:
        checks["supplier_name"] = "Mismatch"
        issues.append("Supplier name does not match.")

    # 2. Compare currency
    if po.fields.currency and invoice.fields.currency:
        if po.fields.currency.upper() == invoice.fields.currency.upper():
            checks["currency"] = "Match"
        else:
            checks["currency"] = "Mismatch"
            issues.append("Currency does not match.")
    else:
        checks["currency"] = "Needs Review"
        issues.append("Currency information is missing.")

    # 3. Compare total amount
    if abs(po.fields.total_amount - invoice.fields.total_amount) <= 0.01:
        checks["total_amount"] = "Match"
    else:
        checks["total_amount"] = "Mismatch"
        issues.append("Total amount does not match.")

    # 4. Compare line items by description
    line_item_results = []

    invoice_items = {
        normalize_text(item.description): item
        for item in invoice.line_items
    }

    for po_item in po.line_items:
        description = normalize_text(po_item.description)
        invoice_item = invoice_items.get(description)

        if invoice_item is None:
            line_item_results.append({
                "description": po_item.description,
                "status": "Mismatch",
                "message": "Item not found in invoice."
            })
            issues.append(
                f"Item '{po_item.description}' is missing in the invoice."
            )
            continue

        item_checks = {}

        item_checks["quantity"] = (
            "Match"
            if abs(po_item.quantity - invoice_item.quantity) <= 0.01
            else "Mismatch"
        )

        if po_item.unit_price is not None and invoice_item.unit_price is not None:
            item_checks["unit_price"] = (
                "Match"
                if abs(po_item.unit_price - invoice_item.unit_price) <= 0.01
                else "Mismatch"
            )

        if po_item.line_total is not None and invoice_item.line_total is not None:
            item_checks["line_total"] = (
                "Match"
                if abs(po_item.line_total - invoice_item.line_total) <= 0.01
                else "Mismatch"
            )

        item_status = (
            "Match"
            if all(value == "Match" for value in item_checks.values())
            else "Mismatch"
        )

        line_item_results.append({
            "description": po_item.description,
            "status": item_status,
            "checks": item_checks
        })

        if item_status == "Mismatch":
            issues.append(
                f"Line item '{po_item.description}' has different values."
            )

    checks["line_items"] = line_item_results

    # 5. Final result
    status = (
        "Mismatch"
        if any(value == "Mismatch" for value in checks.values()
               if isinstance(value, str))
        or any(item["status"] == "Mismatch" for item in line_item_results)
        else "Match"
    )

    return {
        "status": status,
        "checks": checks,
        "issues": issues
    }