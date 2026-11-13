
import base64
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[2]
TOKEN_PATH = ROOT / "token.json"

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
LABEL_NAME = "Invoice-Processing"

REDIRECT_URI = os.getenv(
    "REDIRECT_URI",
    "http://127.0.0.1:8000/gmail/callback"
)


def get_oauth_client_config():
    """Build Google OAuth configuration from environment variables."""

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is missing from .env"
        )

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI]
        }
    }



def create_oauth_flow(state=None):
    flow = Flow.from_client_config(
        get_oauth_client_config(),
        scopes=SCOPES,
        state=state,
        autogenerate_code_verifier=True
    )

    flow.redirect_uri = REDIRECT_URI

    return flow



def save_credentials(creds):
    """Save authorized Gmail credentials locally."""

    TOKEN_PATH.write_text(
        creds.to_json(),
        encoding="utf-8"
    )


def get_gmail_service():
    """Connect to Gmail using the saved OAuth token."""

    if not TOKEN_PATH.exists():
        raise RuntimeError(
            "Gmail is not connected. Please connect your Gmail account first."
        )

    creds = Credentials.from_authorized_user_file(
        str(TOKEN_PATH), SCOPES
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds)

    if not creds.valid:
        raise RuntimeError(
            "Gmail authorization expired. Please reconnect your Gmail account."
        )

    return build("gmail", "v1", credentials=creds)


def get_gmail_profile():
    """Retrieve the connected Gmail account address."""

    service = get_gmail_service()

    profile = service.users().getProfile(
        userId="me"
    ).execute()

    return profile.get("emailAddress")


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
