from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class EmailSubmit(BaseModel):
    subject: Optional[str] = Field(default="", max_length=1000)
    sender: Optional[str] = Field(default="", max_length=500)
    recipient: Optional[str] = Field(default="", max_length=500)
    body: str = Field(max_length=200_000)

    @field_validator("body")
    @classmethod
    def body_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Email body cannot be empty.")
        return v


class TextResult(BaseModel):
    filename: str
    input_type: str  # email | digital_pdf | scanned_pdf | image
    method: str
    pages: int = 1
    text: str
    warnings: list[str] = []
    attachments: list[dict[str, Any]] = []


class ExtractRequest(BaseModel):
    filename: Optional[str] = Field(default="", max_length=300)
    text: str = Field(max_length=500_000)

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("There is no text to extract from.")
        return v


class FieldSpecOut(BaseModel):
    key: str
    label: str
    type: str
    required: bool = False


class ValidationIssue(BaseModel):
    field: str
    severity: str  # error | warning | info
    message: str


class ValidationReport(BaseModel):
    status: str  # valid | needs_review | invalid
    issues: list[ValidationIssue]
    missing_fields: list[str]
    uncertain_fields: list[str]


class ExtractionResponse(BaseModel):
    filename: str
    document_type: str
    classification_confidence: Optional[float] = None
    fields: dict[str, Any]
    line_items: list[dict[str, Any]]
    field_specs: list[FieldSpecOut]
    item_specs: list[FieldSpecOut]
    validation: ValidationReport
    model: str
