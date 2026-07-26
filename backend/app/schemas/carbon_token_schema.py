from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.carbon_token import TokenStatus


class CarbonTokenResponse(BaseModel):
    id: int
    carbon_report_id: int
    farmer_id: int
    token_id: str
    token_standard: str
    credit_amount: int
    status: TokenStatus
    minted_tx_hash: Optional[str]
    minted_at: Optional[datetime]
    # Phase 9: custodial fields
    fpo_id:                Optional[int] = None
    beneficiary_farmer_id: Optional[int] = None
    custodial_owner_type:  str = "FPO"
    created_at: datetime
    is_certificate: bool = False        # True when credit_amount == 0

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_flag(cls, token) -> "CarbonTokenResponse":
        obj = cls.model_validate(token)
        obj.is_certificate = (token.credit_amount == 0)
        return obj


class TokenSummaryResponse(BaseModel):
    total_tokens: int
    total_minted_credits: int
    active_tokens: int
    retired_tokens: int
    suspended_tokens: int
    zero_credit_certificates: int
