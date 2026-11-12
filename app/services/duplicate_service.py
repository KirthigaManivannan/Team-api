
import os
import sqlite3
from pathlib import Path


def get_database_path():
    """Get the SQLite database location."""
    default_path = Path.home() / ".invoice_registry" / "invoices.db"
    return Path(os.getenv("INVOICE_DB_PATH", str(default_path)))


def initialize_database(db_path=None):
    """Create the invoice table if it does not exist."""
    path = Path(db_path) if db_path else get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL,
                supplier_name TEXT NOT NULL,
                invoice_date TEXT NOT NULL,
                invoice_number_key TEXT NOT NULL,
                supplier_name_key TEXT NOT NULL,
                invoice_date_key TEXT NOT NULL,
                UNIQUE (
                    invoice_number_key,
                    supplier_name_key,
                    invoice_date_key
                )
            )
        """)

    return path


def check_and_register_invoice(fields, db_path=None):
    """
    Check whether an invoice already exists.
    Register it if it is new.
    """
    invoice_number = str(fields.get("invoice_number") or "").strip()
    supplier_name = str(fields.get("supplier_name") or "").strip()
    invoice_date = str(fields.get("invoice_date") or "").strip()

    if not invoice_number or not supplier_name or not invoice_date:
        raise ValueError(
            "Invoice number, supplier name and invoice date are required."
        )

    path = initialize_database(db_path)

    # Normalize values to avoid case and whitespace differences.
    invoice_key = invoice_number.casefold()
    supplier_key = supplier_name.casefold()
    date_key = invoice_date.casefold()

    with sqlite3.connect(path) as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO invoices (
                invoice_number,
                supplier_name,
                invoice_date,
                invoice_number_key,
                supplier_name_key,
                invoice_date_key
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                invoice_number,
                supplier_name,
                invoice_date,
                invoice_key,
                supplier_key,
                date_key,
            ),
        )

        if cursor.rowcount == 0:
            return {
                "duplicate": True,
                "message": "This invoice already exists.",
                "invoice_number": invoice_number,
            }

    return {
        "duplicate": False,
        "message": "New invoice registered successfully.",
        "invoice_number": invoice_number,
    }
