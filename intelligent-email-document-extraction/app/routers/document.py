from fastapi import APIRouter, File, UploadFile

from app.schemas.extraction import TextResult
from app.services import file_service

router = APIRouter(prefix="/document", tags=["document"])


@router.post("/upload", response_model=TextResult)
def upload_document(file: UploadFile = File(...)):
    data = file_service.read_upload(file)
    return file_service.extract_text(file.filename or "upload", data)
