"""Pydantic schemas for FarmerCreditBalance — Phase 9."""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel

from app.models.farmer_credit_balance import CreditBalanceStatus


class CreditBalanceResponse(BaseModel):
    id:                 int
    farmer_id:          int
    fpo_id:             int
    carbon_report_id:   int
    carbon_token_id:    Optional[int]
    credits_earned:     int
    credits_distributed: int
    credits_available:  int
    status:             CreditBalanceStatus
    created_at:         datetime
    updated_at:         datetime

    model_config = {"from_attributes": True}


class EnrichedCreditBalanceResponse(CreditBalanceResponse):
    """Extended balance response for FPO Farmer Credits screen.
    Includes farmer name/email, farm name and farmer payout method."""
    farmer_name:          Optional[str] = None
    farmer_email:         Optional[str] = None
    farm_name:            Optional[str] = None
    farmer_payout_method: Optional[str] = None   # UPI | BANK_TRANSFER | None
    farmer_upi_id:        Optional[str] = None
    carbon_token_id:      Optional[int] = None


class FarmerCreditSummaryResponse(BaseModel):
    """Aggregated balance summary for a farmer."""
    total_earned:      int
    total_distributed: int
    total_available:   int
    total_tokenized:   int   # balances in TOKENIZED status
    balances:          List[CreditBalanceResponse]


class PlatformCreditSummaryResponse(BaseModel):
    """Admin-level platform-wide credit summary."""
    total_balances:          int
    total_credits_earned:    int
    total_credits_distributed: int
    total_credits_available: int
    by_status:               dict
