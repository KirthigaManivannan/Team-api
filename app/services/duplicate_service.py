
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
def get_registered_invoices(db_path=None):
    """Retrieve all registered invoices from the database."""
    path = initialize_database(db_path)

    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row

        cursor = connection.execute("""
            SELECT
                invoice_number,
                supplier_name,
                invoice_date
            FROM invoices
            ORDER BY id
        """)

    return [dict(row) for row in cursor.fetchall()]


def initialize_gmail_history(db_path=None):
    """Create a table to track Gmail messages already processed."""

    path = initialize_database(db_path)

    with sqlite3.connect(path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS processed_gmail_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL UNIQUE,
                subject TEXT,
                status TEXT NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    return path


def is_gmail_message_processed(message_id, db_path=None):
    """Check whether a Gmail message has already been processed."""

    path = initialize_gmail_history(db_path)

    with sqlite3.connect(path) as connection:
        result = connection.execute(
            """
            SELECT 1
            FROM processed_gmail_messages
            WHERE message_id = ?
            """,
            (message_id,)
        ).fetchone()

    return result is not None


def register_gmail_message(
    message_id,
    subject,
    status="completed",
    db_path=None
):
    """Register a Gmail message after processing."""

    path = initialize_gmail_history(db_path)

    with sqlite3.connect(path) as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO processed_gmail_messages (
                message_id,
                subject,
                status
            )
            VALUES (?, ?, ?)
            """,
            (message_id, subject, status)
        )

    return cursor.rowcount > 0

def get_gmail_processing_history(limit=50):
    """Retrieve previously processed Gmail messages."""

    path = initialize_gmail_history()

    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute("""
            SELECT
                message_id,
                subject,
                status,
                processed_at
            FROM processed_gmail_messages
            ORDER BY processed_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return [
        {
            "message_id": row["message_id"],
            "subject": row["subject"],
            "status": row["status"],
            "processed_at": row["processed_at"]
        }
        for row in rows
    ]
