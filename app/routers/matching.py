from fastapi import APIRouter

from app.schemas.matching import MatchingRequest
from app.services import matching_service

router = APIRouter(tags=["matching"])


@router.post("/match/po-invoice")
def match_purchase_order_invoice(payload: MatchingRequest):
    """Compare an invoice with its purchase order."""
    return matching_service.compare_documents(payload)