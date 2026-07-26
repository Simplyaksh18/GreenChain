from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class FPOListItemResponse(BaseModel):
    """Minimal FPO info for farmer-facing FPO selection."""
    id: int
    organization_name: str
    registration_number: str
    district: str
    state: str

    model_config = {"from_attributes": True}


class FPOProfileCreate(BaseModel):
    organization_name: str
    registration_number: str
    district: str
    state: str


class FPOProfileResponse(BaseModel):
    id: int
    user_id: int
    organization_name: str
    registration_number: str
    district: str
    state: str
    wallet_address:    Optional[str] = None
    vault_identifier:  Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FPOWalletUpdateRequest(BaseModel):
    """PATCH /fpo/profile/wallet — FPO only."""
    wallet_address:   Optional[str] = None
    vault_identifier: Optional[str] = None
    wallet_network:   Optional[str] = None

    @field_validator("wallet_address")
    @classmethod
    def validate_wallet(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError("wallet_address must be a valid 0x-prefixed 42-character EVM address")
        return v.lower()


def _mask_wallet(address: Optional[str]) -> Optional[str]:
    """
    Mask wallet address: first 6 + last 6 chars visible.
    e.g. 0xbf26...1234 → 0xbf26...5ad68c (actual last 6)
    """
    if not address:
        return None
    if len(address) <= 12:
        return address
    return address[:6] + "..." + address[-6:]


class FPOWalletResponse(BaseModel):
    id:                   int
    organization_name:    str
    wallet_address:       Optional[str]      # raw address (FPO sees own wallet in full)
    wallet_address_masked: Optional[str] = None  # Phase 10A: first6...last6
    vault_identifier:     Optional[str]
    wallet_verified:      bool = False
    wallet_verified_at:   Optional[datetime] = None
    wallet_network:       Optional[str] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_enriched(cls, profile) -> "FPOWalletResponse":
        obj = cls.model_validate(profile)
        obj.wallet_address_masked = _mask_wallet(profile.wallet_address)
        return obj


class FPOWalletVerifyRequest(BaseModel):
    """POST /fpo/profile/wallet/verify — trigger wallet verification."""
    # No body needed for mock mode; kept for future web3 mode params
    pass


class FPOWalletVerifyResponse(BaseModel):
    verified: bool
    wallet_address: Optional[str]
    wallet_address_masked: Optional[str]
    wallet_network: Optional[str]
    verified_at: Optional[datetime]
    message: str
