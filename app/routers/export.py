import csv
import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services import duplicate_service

router = APIRouter(prefix="/invoices", tags=["CSV Export"])


@router.get("/export")
def export_invoices():
    """Export registered invoices as a CSV file."""

    invoices = duplicate_service.get_registered_invoices()

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "invoice_number",
            "supplier_name",
            "invoice_date",
        ],
    )

    writer.writeheader()
    writer.writerows(invoices)

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=invoices.csv"
        },
    )