from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class InvoiceReviewRequest(BaseModel):
    invoice_number: str | None = Field(None, json_schema_extra={"example": "INV-123"})
    invoice_date:   str | None = Field(None, json_schema_extra={"example": "2026-01-15"})
    vendor_name:    str | None = Field(None, json_schema_extra={"example": "Acme GmbH"})
    customer_name:  str | None = Field(None, json_schema_extra={"example": "Beta Corp"})
    total_amount:   float | None = Field(None, json_schema_extra={"example": 1200.50})
    currency:       str | None = Field(None, json_schema_extra={"example": "EUR"})
    due_date:       str | None = Field(None, json_schema_extra={"example": "2026-03-30"})
    rules_text:     str | None = Field(None, json_schema_extra={"example": "max_amount=5000"})


class InvoiceReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:        int
    decision:  str
    reasons:   list[str]
    evidence:  dict[str, Any]
    timestamp: datetime


class InvoiceReviewListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:        int
    decision:  str
    timestamp: datetime