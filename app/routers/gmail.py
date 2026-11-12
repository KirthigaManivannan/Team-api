
from fastapi import APIRouter, HTTPException, Query

from app.errors import AppError
from app.services import (
    duplicate_service,
    file_service,
    gmail_service,
    gmail_results_service,
    llm_service,
    validation_service,
)

router = APIRouter(prefix="/gmail", tags=["Gmail Integration"])


@router.post("/process")
def process_gmail_emails(
    max_results: int = Query(default=10, ge=1, le=50)
):
    """
    Read labelled Gmail messages, process attachments,
    extract document fields and validate the results.
    """

    try:
        service = gmail_service.get_gmail_service()

        messages = gmail_service.get_labelled_emails(
            service,
            max_results=max_results
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Gmail: {str(exc)}"
        )

    response = {
        "total_emails_found": len(messages),
        "processed": 0,
        "skipped": 0,
        "results": []
    }

    for message in messages:
        message_id = message["id"]

        # Check whether this Gmail message was already processed
        if duplicate_service.is_gmail_message_processed(message_id):
            response["skipped"] += 1

            response["results"].append({
                "message_id": message_id,
                "status": "skipped",
                "reason": "Email was already processed."
            })

            continue

        try:
            details = gmail_service.get_email_details(
                service,
                message_id
            )

            attachments = gmail_service.get_email_attachments(
                service,
                message_id,
                details["payload"]
            )

            if not attachments:
                response["skipped"] += 1

                response["results"].append({
                    "message_id": message_id,
                    "subject": details["subject"],
                    "status": "skipped",
                    "reason": "No supported PDF or image attachments found."
                })

                continue

            attachment_results = []

            for attachment in attachments:

                # Extract PDF text or perform OCR
                extracted = file_service.extract_text(
                    attachment["filename"],
                    attachment["data"]
                )

                # AI document classification
                classification = llm_service.classify(
                    extracted["text"]
                )

                doc_type = classification["document_type"]

                # Extract structured document fields
                extraction = llm_service.extract_fields(
                    extracted["text"],
                    doc_type
                )

                # Validate extracted information
                validation = validation_service.validate(
                    doc_type,
                    extraction["fields"],
                    extraction["line_items"],
                    uncertain=extraction["uncertain_fields"],
                    source_text=extracted["text"],
                    confidence=classification["confidence"]
                )

                attachment_results.append({
                    "filename": attachment["filename"],
                    "document_type": doc_type,
                    "classification_confidence": classification["confidence"],
                    "fields": extraction["fields"],
                    "line_items": extraction["line_items"],
                    "validation": validation
                })

                gmail_results_service.save_gmail_extraction_result(
    message_id=message_id,
    subject=details["subject"],
    sender=details["sender"],
    filename=attachment["filename"],
    document_type=doc_type,
    classification_confidence=classification["confidence"],
    fields=extraction["fields"],
    line_items=extraction["line_items"],
    validation=validation
)

            # Register only after all attachments finish successfully
            registered = duplicate_service.register_gmail_message(
                message_id=message_id,
                subject=details["subject"],
                status="completed"
            )

            if not registered:
                response["skipped"] += 1
                status = "skipped"
                reason = "Email was registered by another process."
            else:
                response["processed"] += 1
                status = "completed"
                reason = None

            response["results"].append({
                "message_id": message_id,
                "subject": details["subject"],
                "sender": details["sender"],
                "status": status,
                "reason": reason,
                "attachments": attachment_results
            })

        except AppError as exc:
            response["results"].append({
                "message_id": message_id,
                "status": "failed",
                "error": exc.message
            })

        except Exception as exc:
            response["results"].append({
                "message_id": message_id,
                "status": "failed",
                "error": str(exc)
            })

    return response

@router.get("/results")
def get_gmail_results(
    limit: int = Query(default=50, ge=1, le=200)
):
    """Get saved Gmail document extraction results."""

    try:
        results = gmail_results_service.get_gmail_extraction_results(
            limit=limit
        )

        return {
            "total_results": len(results),
            "results": results
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve Gmail results: {str(exc)}"
        )

@router.get("/history")
def get_gmail_history(
    limit: int = Query(default=50, ge=1, le=200)
):
    """Retrieve Gmail processing history."""

    try:
        history = duplicate_service.get_gmail_processing_history(
            limit=limit
        )

        return {
            "total_history": len(history),
            "history": history
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve Gmail history: {str(exc)}"
        )
