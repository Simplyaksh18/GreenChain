"""
User profile router — Phase 8.

GET  /users/me   — any authenticated user
PATCH /users/me  — any authenticated user (name, wallet_address)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.user_schema import UserProfileResponse, UserProfileUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """Return the logged-in user's full profile including wallet_address."""
    return current_user


@router.patch("/me", response_model=UserProfileResponse)
def update_my_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update the logged-in user's mutable profile fields.

    Allowed fields:
    - name          : non-empty string
    - wallet_address: valid 0x Ethereum address, or null/empty to clear
    """
    if payload.name is not None:
        current_user.name = payload.name

    if "wallet_address" in payload.model_fields_set:
        current_user.wallet_address = payload.wallet_address

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user
