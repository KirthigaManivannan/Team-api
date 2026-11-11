import os

from fastapi import APIRouter, File, UploadFile

from app.errors import AppError, FileError
from app.schemas.extraction import EmailSubmit, TextResult
from app.services import email_service, file_service

router = APIRouter(prefix="/email", tags=["email"])


@router.post("/submit", response_model=TextResult)
def submit_email(payload: EmailSubmit):
    text = email_service.build_email_text(payload.subject, payload.sender, payload.recipient, payload.body)
    return {"filename": payload.subject or "Pasted email", "input_type": "email", "method": "direct", "pages": 1, "text": text}


@router.post("/upload", response_model=TextResult)
def upload_email(file: UploadFile = File(...)):
    name = file.filename or "email.eml"
    if not name.lower().endswith(".eml"):
        raise FileError("Unsupported file type. Upload an .eml file.", 415)
    data = file_service.read_upload(file)
    if not data:
        raise FileError("The file is empty.", 400)
    parsed = email_service.parse_eml(data)
    text = email_service.build_email_text(parsed["subject"], parsed["sender"], parsed["recipient"], parsed["body"])

    attachments = []
    for att_name, att_bytes in parsed["attachments"]:
        try:
            res = file_service.extract_text(att_name, att_bytes)
            attachments.append({"filename": res["filename"], "input_type": res["input_type"], "text": res["text"], "error": None})
        except AppError as exc:
            attachments.append({"filename": att_name, "input_type": None, "text": "", "error": exc.message})

    return {
        "filename": os.path.basename(name),
        "input_type": "email",
        "method": "eml",
        "pages": 1,
        "text": text,
        "warnings": [] if not parsed["attachments"] else [f"{len(parsed['attachments'])} attachment(s) found and read separately."],
        "attachments": attachments,
    }

