
from pydantic import BaseModel, Field


class MatchingFields(BaseModel):
    supplier_name: str = Field(min_length=1)
    currency: str | None = None
    total_amount: float


class MatchingLineItem(BaseModel):
    description: str = Field(min_length=1)
    quantity: float = Field(ge=0)
    unit_price: float | None = None
    line_total: float | None = None


class MatchingDocument(BaseModel):
    fields: MatchingFields
    line_items: list[MatchingLineItem] = Field(default_factory=list)


class MatchingRequest(BaseModel):
    purchase_order: MatchingDocument
    invoice: MatchingDocument
