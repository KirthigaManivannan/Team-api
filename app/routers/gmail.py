
import secrets

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

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


@router.get("/connect")
def connect_gmail(request: Request):
    """Start Google OAuth authorization."""

    try:
        state = secrets.token_urlsafe(32)
        request.session["oauth_state"] = state

        flow = gmail_service.create_oauth_flow(state=state)

        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent"
        )

        # Save the PKCE verifier so the callback can reuse it.
        request.session["oauth_code_verifier"] = flow.code_verifier

        return RedirectResponse(authorization_url)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not start Gmail authorization: {str(exc)}"
        )


@router.get("/callback")
def gmail_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None
):
    """Handle Google's OAuth callback and save credentials."""

    if error:
        request.session.pop("oauth_state", None)
        request.session.pop("oauth_code_verifier", None)

        raise HTTPException(
            status_code=400,
            detail=f"Google authorization failed: {error}"
        )

    expected_state = request.session.pop("oauth_state", None)

    if not expected_state or not state or not secrets.compare_digest(
        expected_state, state
    ):
        request.session.pop("oauth_code_verifier", None)

        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state. Please try connecting again."
        )

    if not code:
        request.session.pop("oauth_code_verifier", None)

        raise HTTPException(
            status_code=400,
            detail="Google authorization code is missing."
        )

    # Retrieve the original PKCE verifier from the session.
    code_verifier = request.session.pop("oauth_code_verifier", None)

    if not code_verifier:
        raise HTTPException(
            status_code=400,
            detail="OAuth code verifier is missing. Please reconnect Gmail."
        )

    try:
        flow = gmail_service.create_oauth_flow(state=state)

        # Restore the verifier generated during /connect.
        flow.code_verifier = code_verifier

        flow.fetch_token(code=code)

        credentials = flow.credentials
        gmail_service.save_credentials(credentials)

        # Verify the Gmail account and saved token.
        email_address = gmail_service.get_gmail_profile()

        request.session["gmail_connected"] = True

        return RedirectResponse(
            url="/?gmail_connected=true",
            status_code=303
        )

    except Exception as exc:
        gmail_service.TOKEN_PATH.unlink(missing_ok=True)

        raise HTTPException(
            status_code=502,
            detail=f"Could not complete Gmail authorization: {str(exc)}"
        )


@router.get("/status")
def gmail_status():
    """Return the current Gmail connection status."""

    if not gmail_service.TOKEN_PATH.exists():
        return {
            "connected": False,
            "email": None
        }

    try:
        email_address = gmail_service.get_gmail_profile()

        return {
            "connected": True,
            "email": email_address
        }

    except Exception:
        return {
            "connected": False,
            "email": None
        }


@router.post("/disconnect")
def disconnect_gmail():
    """Remove the locally saved Gmail authorization."""

    gmail_service.TOKEN_PATH.unlink(missing_ok=True)

    return {
        "success": True,
        "connected": False,
        "message": "Gmail disconnected successfully."
    }


@router.post("/process")
def process_gmail_emails(
    max_results: int = Query(default=10, ge=1, le=50)
):
    """Read labelled Gmail messages and process attachments."""

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
                service, message_id
            )

            attachments = gmail_service.get_email_attachments(
                service, message_id, details["payload"]
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
                extracted = file_service.extract_text(
                    attachment["filename"],
                    attachment["data"]
                )

                classification = llm_service.classify(
                    extracted["text"]
                )

                doc_type = classification["document_type"]

                extraction = llm_service.extract_fields(
                    extracted["text"],
                    doc_type
                )

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
