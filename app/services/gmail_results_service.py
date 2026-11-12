
import json
import sqlite3

from app.services.duplicate_service import initialize_database


def initialize_gmail_results_table():
    """Create a table to store Gmail document extraction results."""

    db_path = initialize_database()

    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS gmail_extraction_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                subject TEXT,
                sender TEXT,
                filename TEXT NOT NULL,
                document_type TEXT,
                classification_confidence REAL,
                fields_json TEXT,
                line_items_json TEXT,
                validation_json TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(message_id, filename)
            )
        """)

    return db_path

def save_gmail_extraction_result(
    message_id,
    subject,
    sender,
    filename,
    document_type,
    classification_confidence,
    fields,
    line_items,
    validation
):
    """Save extracted Gmail document results in SQLite."""

    db_path = initialize_gmail_results_table()

    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            INSERT INTO gmail_extraction_results (
                message_id,
                subject,
                sender,
                filename,
                document_type,
                classification_confidence,
                fields_json,
                line_items_json,
                validation_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id, filename) DO UPDATE SET
                subject = excluded.subject,
                sender = excluded.sender,
                document_type = excluded.document_type,
                classification_confidence = excluded.classification_confidence,
                fields_json = excluded.fields_json,
                line_items_json = excluded.line_items_json,
                validation_json = excluded.validation_json,
                processed_at = CURRENT_TIMESTAMP
        """, (
            message_id,
            subject,
            sender,
            filename,
            document_type,
            classification_confidence,
            json.dumps(fields),
            json.dumps(line_items),
            json.dumps(validation)
        ))

    return True

def get_gmail_extraction_results(limit=50):
    """Retrieve saved Gmail extraction results."""

    db_path = initialize_gmail_results_table()

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute("""
            SELECT *
            FROM gmail_extraction_results
            ORDER BY processed_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

    results = []

    for row in rows:
        results.append({
            "id": row["id"],
            "message_id": row["message_id"],
            "subject": row["subject"],
            "sender": row["sender"],
            "filename": row["filename"],
            "document_type": row["document_type"],
            "classification_confidence": row["classification_confidence"],
            "fields": json.loads(row["fields_json"] or "{}"),
            "line_items": json.loads(row["line_items_json"] or "[]"),
            "validation": json.loads(row["validation_json"] or "{}"),
            "processed_at": row["processed_at"]
        })

    return results
