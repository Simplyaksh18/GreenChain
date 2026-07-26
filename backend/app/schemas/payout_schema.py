"""Pydantic schemas for Payout — Phase 9."""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, model_validator

from app.models.payout import PayoutStatus


class PayoutInitiateRequest(BaseModel):
    credit_balance_id: int
    amount_credits:    int = Field(ge=1)
    price_per_credit:  int = Field(ge=1, description="Amount in paise (smallest INR unit)")
    currency:          str = Field(default="INR", max_length=10)
    remarks:           Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_amount(self) -> "PayoutInitiateRequest":
        # payout_amount sanity — no overflow
        total = self.amount_credits * self.price_per_credit
        if total <= 0:
            raise ValueError("payout_amount must be positive")
        return self


class PayoutResponse(BaseModel):
    id:                     int
    farmer_id:              int
    fpo_id:                 int
    credit_balance_id:      int
    amount_credits:         int
    price_per_credit:       int
    payout_amount:          int
    currency:               str
    payout_method:          Optional[str]
    status:                 PayoutStatus
    initiated_by:           int
    initiated_at:           datetime
    completed_at:           Optional[datetime]
    remarks:                Optional[str]
    # Phase 10B: provider tracking
    idempotency_key:        Optional[str] = None
    provider_reference_id:  Optional[str] = None   # RazorpayX payout_id (pout_XXXX) when live

    model_config = {"from_attributes": True}


class PayoutCompleteRequest(BaseModel):
    remarks: Optional[str] = Field(default=None, max_length=500)
