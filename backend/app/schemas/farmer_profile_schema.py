"""Pydantic schemas for FarmerProfile — Phase 9 / Phase 10A."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models.farmer_profile import PayoutMethod


class FarmerPayoutDetailsUpsert(BaseModel):
    """POST/PATCH /farmers/payout-details — FARMER only."""
    preferred_payout_method:  Optional[PayoutMethod] = None
    upi_id:                   Optional[str] = None
    bank_account_holder_name: Optional[str] = None
    bank_account_number:      Optional[str] = None
    ifsc_code:                Optional[str] = None
    bank_name:                Optional[str] = None

    @field_validator("ifsc_code")
    @classmethod
    def ifsc_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        if len(v) != 11:
            raise ValueError("IFSC code must be exactly 11 characters")
        return v

    @field_validator("bank_account_number")
    @classmethod
    def acct_length(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v.isdigit() or not (9 <= len(v) <= 18):
            raise ValueError("Bank account number must be 9–18 digits")
        return v

    @field_validator("upi_id")
    @classmethod
    def upi_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if "@" not in v or len(v) < 3:
            raise ValueError("UPI ID must contain '@' and be a valid VPA (e.g. name@bank)")
        return v.lower()


# ── Masking helpers ────────────────────────────────────────────────────────────

def _mask_account(number: Optional[str]) -> Optional[str]:
    """Return masked account: last 4 digits visible, rest as *. e.g. ****1234"""
    if not number:
        return None
    visible = number[-4:]
    return "*" * (len(number) - 4) + visible


def _mask_upi(upi_id: Optional[str]) -> Optional[str]:
    """
    Mask UPI ID: show first character + *** + @ + provider domain.
    e.g. abc@okicici  → a***@okicici
         ab@upi       → a***@upi
    SECURITY: never log or return raw UPI IDs to FPO or other parties.
    """
    if not upi_id:
        return None
    if "@" not in upi_id:
        return "***"
    local, domain = upi_id.split("@", 1)
    if len(local) == 0:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


class FarmerPayoutDetailsResponse(BaseModel):
    id: int
    user_id: int
    preferred_payout_method:    Optional[PayoutMethod]
    upi_id_masked:              Optional[str] = None    # Phase 10A: always masked
    bank_account_holder_name:   Optional[str]
    bank_account_number_masked: Optional[str] = None   # always masked
    ifsc_code:                  Optional[str]
    bank_name:                  Optional[str] = None
    # Phase 10A: verification status
    payout_details_verified:    bool = False
    payout_details_verified_at: Optional[datetime] = None
    payout_verification_method: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_masked(cls, profile) -> "FarmerPayoutDetailsResponse":
        return cls(
            id=profile.id,
            user_id=profile.user_id,
            preferred_payout_method=profile.preferred_payout_method,
            upi_id_masked=_mask_upi(profile.upi_id),
            bank_account_holder_name=profile.bank_account_holder_name,
            bank_account_number_masked=_mask_account(profile.bank_account_number),
            ifsc_code=profile.ifsc_code,
            bank_name=profile.bank_name,
            payout_details_verified=profile.payout_details_verified,
            payout_details_verified_at=profile.payout_details_verified_at,
            payout_verification_method=profile.payout_verification_method,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
