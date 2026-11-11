"""Checks extracted values. Never changes them: problems are reported for the user to review."""
import math
import re
from datetime import date

from app.services.field_specs import GENERATED_KEYS, KNOWN_CURRENCIES, spec_for

NON_NEGATIVE = {"total_amount", "subtotal", "tax", "unit_price", "line_total"}
DATE_PAIRS = [("order_date", "delivery_date"), ("invoice_date", "due_date")]
TOLERANCE = 0.011


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _parse_date(v):
    if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()):
        try:
            return date.fromisoformat(v.strip())
        except ValueError:
            return None
    return None


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def ungrounded(fields: dict, line_items: list, text: str, specs: dict) -> list[str]:
    """Keys whose value cannot be found in the source text (possible invention)."""
    norm_text = _norm(text)
    numbers = set()
    for m in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        try:
            numbers.add(float(m.replace(",", "")))
        except ValueError:
            pass

    def found(value, type_):
        if type_ == "string" and isinstance(value, str):
            return _norm(value) in norm_text
        if type_ == "number" and _is_num(value):
            return any(abs(value - n) < 1e-6 for n in numbers)
        return True  # dates/currency/other types are not text-matched

    out = []
    for f in specs["fields"]:
        v = fields.get(f["key"])
        if v is not None and f["key"] not in GENERATED_KEYS and not found(v, f["type"]):
            out.append(f["key"])
    for i, row in enumerate(line_items):
        for f in specs["items"]:
            v = row.get(f["key"])
            if f["type"] == "number" and v is not None and not found(v, "number"):
                out.append(f"line_items[{i}].{f['key']}")
    return out


def validate(doc_type, fields, line_items, uncertain=(), source_text=None, confidence=None) -> dict:
    spec = spec_for(doc_type)
    issues, missing = [], []

    def add(field, severity, message):
        issues.append({"field": field, "severity": severity, "message": message})

    def check(key, label, type_, value, path):
        if type_ == "string":
            if not isinstance(value, str) or not value.strip():
                add(path, "error", f"{label} must be text.")
        elif type_ == "date":
            if _parse_date(value) is None:
                add(path, "error", f"{label} is not a valid date in YYYY-MM-DD format (value left unchanged).")
        elif type_ == "number":
            if not _is_num(value):
                add(path, "error", f"{label} must be a number (value left unchanged).")
            elif key in NON_NEGATIVE and value < 0:
                add(path, "error", f"{label} cannot be negative.")
            elif key == "quantity":
                if value < 0:
                    add(path, "error", f"{label} cannot be negative.")
                elif value == 0:
                    add(path, "warning", f"{label} is zero.")
        elif type_ == "currency":
            if not isinstance(value, str) or not re.fullmatch(r"[A-Z]{3}", value.strip()):
                add(path, "error", f"{label} must be a 3-letter currency code such as USD or EUR.")
            elif value.strip() not in KNOWN_CURRENCIES:
                add(path, "warning", f"{label} '{value}' is not a common currency code. Please confirm.")

    for f in spec["fields"]:
        key, value = f["key"], fields.get(f["key"])
        if value is None:
            missing.append(key)
            add(key, "warning" if f["required"] else "info",
                f"{f['label']} was not found." + (" It is required." if f["required"] else ""))
        else:
            check(key, f["label"], f["type"], value, key)

    if spec["items"]:
        if not line_items:
            missing.append("line_items")
            add("line_items", "warning", "No line items were found.")
        for i, row in enumerate(line_items):
            for f in spec["items"]:
                path, value = f"line_items[{i}].{f['key']}", row.get(f["key"])
                if value is None:
                    if f["required"]:
                        missing.append(path)
                        add(path, "warning", f"Line {i + 1}: {f['label']} was not found.")
                else:
                    check(f["key"], f"Line {i + 1}: {f['label']}", f["type"], value, path)
            q, p, t = row.get("quantity"), row.get("unit_price"), row.get("line_total")
            if _is_num(q) and _is_num(p) and _is_num(t) and abs(q * p - t) > max(TOLERANCE, 0.001 * abs(t)):
                add(f"line_items[{i}].line_total", "warning",
                    f"Line {i + 1}: quantity x unit price ({q * p:.2f}) does not match the line total ({t:.2f}).")

    for a, b in DATE_PAIRS:
        da, db = _parse_date(fields.get(a)), _parse_date(fields.get(b))
        if da and db and db < da:
            add(b, "warning", f"{b.replace('_', ' ').capitalize()} is earlier than {a.replace('_', ' ')}.")

    sub, tax, total = fields.get("subtotal"), fields.get("tax"), fields.get("total_amount")
    if _is_num(sub) and _is_num(tax) and _is_num(total) and abs(sub + tax - total) > TOLERANCE:
        add("total_amount", "warning", f"Subtotal + tax ({sub + tax:.2f}) does not match the total ({total:.2f}).")

    unc = {u for u in uncertain}
    for key in unc:
        add(key, "warning", "The AI marked this value as uncertain. Please check it against the document.")
    if source_text:
        for key in ungrounded(fields, line_items, source_text, spec):
            if key not in unc:
                unc.add(key)
                add(key, "warning", "This value was not found in the source text. Please check it.")
    if confidence is not None and confidence < 0.6:
        add("document_type", "warning", f"The document type is uncertain (confidence {confidence:.0%}).")

    severities = {i["severity"] for i in issues}
    status = "invalid" if "error" in severities else "needs_review" if ("warning" in severities) else "valid"
    return {"status": status, "issues": issues, "missing_fields": missing, "uncertain_fields": sorted(unc)}
