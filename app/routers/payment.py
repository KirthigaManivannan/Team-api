
from fastapi import APIRouter

from app.schemas.payment import PaymentDueDateRequest
from app.services import payment_service

router = APIRouter(tags=["payment"])


@router.post("/payment/check-due-date")
def check_due_date(payload: PaymentDueDateRequest):
    """Check whether an invoice payment is overdue or upcoming."""

    result = payment_service.check_payment_due_date(
        payload.due_date
    )

    return {
        "invoice_number": payload.invoice_number,
        "due_date": payload.due_date,
        **result
    }
