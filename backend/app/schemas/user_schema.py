import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator
from app.models.user import UserRole

# Ethereum / EVM address: 0x followed by exactly 40 hex chars
_ETH_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


class UserRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    is_active: bool
    is_approved: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Phase 8: profile endpoints ─────────────────────────────────────────────────

class UserProfileResponse(BaseModel):
    """Full profile including wallet_address — used by GET /users/me."""
    model_config = {"from_attributes": True}

    id: int
    name: str
    email: str
    role: UserRole
    is_active: bool
    is_approved: bool
    wallet_address: Optional[str] = None
    created_at: datetime


# ── Phase 15: Google OAuth schemas ────────────────────────────────────────────

class GoogleLoginRequest(BaseModel):
    """Mobile sends Google access token; backend verifies with Google userinfo API."""
    google_access_token: str


class GoogleRegisterRequest(BaseModel):
    """
    Create a GreenChain account via Google OAuth.
    Backend verifies the access token to confirm email ownership.
    Role is always user-selected — Google never decides the role.
    """
    google_access_token: str
    name: str
    email: EmailStr
    role: UserRole


class GoogleLoginResponse(BaseModel):
    """Returned when Google user already has a GreenChain account → issue JWT."""
    access_token: str
    token_type: str = "bearer"
    auth_provider: str = "GOOGLE"


class GoogleNeedsRegistrationResponse(BaseModel):
    """
    Returned (HTTP 404) when Google user has no GreenChain account yet.
    Mobile uses name/email/google_sub to prefill the registration screen.
    """
    needs_registration: bool = True
    name: str
    email: str
    google_sub: str
    profile_photo_url: Optional[str]


class UserProfileUpdate(BaseModel):
    """Payload for PATCH /users/me — all fields optional."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    wallet_address: Optional[str] = Field(default=None)

    @field_validator("wallet_address", mode="before")
    @classmethod
    def validate_wallet(cls, v):
        if v is None or v == "":
            return None
        if not _ETH_ADDRESS_RE.match(str(v)):
            raise ValueError(
                "wallet_address must be a valid Ethereum address "
                "(0x followed by exactly 40 hex characters)"
            )
        return v

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            if not isinstance(v, str) or not v.strip():
                raise ValueError("name cannot be empty or blank")
            return v.strip()
        return v
