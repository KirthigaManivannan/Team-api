
from pydantic import BaseModel, Field


class PaymentDueDateRequest(BaseModel):
    invoice_number: str | None = None
    due_date: str = Field(min_length=1)
