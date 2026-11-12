
import base64
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
LABEL_NAME = "Invoice-Processing"


def get_gmail_service():
    """Connect to Gmail using the saved OAuth token."""

    token_path = Path("token.json")

    if not token_path.exists():
        raise RuntimeError(
            "Gmail token not found. Run python gmail_test.py first."
        )

    creds = Credentials.from_authorized_user_file(
        str(token_path), SCOPES
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())

    if not creds.valid:
        raise RuntimeError(
            "Gmail authorization expired. Run python gmail_test.py again."
        )

    return build("gmail", "v1", credentials=creds)


def get_invoice_label(service):
    """Find the Invoice-Processing Gmail label."""

    response = service.users().labels().list(
        userId="me"
    ).execute()

    for label in response.get("labels", []):
        if label["name"] == LABEL_NAME:
            return label["id"]

    raise RuntimeError(
        f"Gmail label '{LABEL_NAME}' was not found."
    )


def get_labelled_emails(service, max_results=10):
    """Retrieve emails from the selected Gmail label."""

    label_id = get_invoice_label(service)

    response = service.users().messages().list(
        userId="me",
        labelIds=[label_id],
        maxResults=max_results
    ).execute()

    return response.get("messages", [])


def get_email_details(service, message_id):
    """Retrieve email subject and sender."""

    email = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full"
    ).execute()

    headers = email.get("payload", {}).get("headers", [])

    def get_header(name):
        return next(
            (
                h["value"] for h in headers
                if h["name"].lower() == name.lower()
            ),
            ""
        )

    return {
        "message_id": message_id,
        "subject": get_header("Subject"),
        "sender": get_header("From"),
        "payload": email.get("payload", {})
    }


def get_attachment_bytes(service, message_id, attachment_id):
    """Download attachment bytes from Gmail."""

    attachment = service.users().messages().attachments().get(
        userId="me",
        messageId=message_id,
        id=attachment_id
    ).execute()

    return base64.urlsafe_b64decode(
        attachment["data"]
    )


def get_email_attachments(service, message_id, payload):
    """Retrieve supported PDF and image attachments."""

    attachments = []

    def walk_parts(parts):
        for part in parts:
            filename = part.get("filename", "")

            if filename:
                extension = Path(filename).suffix.lower()

                if extension in {".pdf", ".png", ".jpg", ".jpeg"}:
                    body = part.get("body", {})
                    attachment_id = body.get("attachmentId")

                    if attachment_id:
                        data = get_attachment_bytes(
                            service,
                            message_id,
                            attachment_id
                        )
                    elif body.get("data"):
                        data = base64.urlsafe_b64decode(
                            body["data"]
                        )
                    else:
                        data = None

                    if data:
                        attachments.append({
                            "filename": Path(filename).name,
                            "data": data
                        })

            if part.get("parts"):
                walk_parts(part["parts"])

    walk_parts(payload.get("parts", []))

    return attachments
