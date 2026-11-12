
from fastapi import APIRouter, HTTPException

from app.schemas.extraction import (
    DuplicateCheckRequest,
    DuplicateCheckResponse,
)
from app.services import duplicate_service

router = APIRouter(prefix="/invoices", tags=["duplicate invoices"])


@router.post(
    "/check-duplicate",
    response_model=DuplicateCheckResponse,
)
def check_duplicate(payload: DuplicateCheckRequest):
    """Check whether an invoice already exists and register it if new."""

    try:
        result = duplicate_service.check_and_register_invoice(
            fields=payload.model_dump()
        )
        return result

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
