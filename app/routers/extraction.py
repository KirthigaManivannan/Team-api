from fastapi import APIRouter

from app.config import get_settings
from app.schemas.extraction import ExtractionResponse, ExtractRequest
from app.services import llm_service, validation_service
from app.services.field_specs import spec_for

router = APIRouter(tags=["extraction"])


@router.post("/extract", response_model=ExtractionResponse)
def extract(payload: ExtractRequest):
    """Classify the text, extract fields for that type, validate. Raises a clear error if the LLM fails."""
    classification = llm_service.classify(payload.text)
    doc_type = classification["document_type"]
    result = llm_service.extract_fields(payload.text, doc_type)
    report = validation_service.validate(
        doc_type,
        result["fields"],
        result["line_items"],
        uncertain=result["uncertain_fields"],
        source_text=payload.text,
        confidence=classification["confidence"],
    )
    spec = spec_for(doc_type)
    return {
        "filename": payload.filename or "Untitled",
        "document_type": doc_type,
        "classification_confidence": classification["confidence"],
        "fields": result["fields"],
        "line_items": result["line_items"],
        "field_specs": spec["fields"],
        "item_specs": spec["items"],
        "validation": report,
        "model": get_settings().openrouter_model,
    }
