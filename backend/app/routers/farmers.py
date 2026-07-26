"""
Farmer router — Phase 2 + Phase 9 Custodial + Phase 10A Security extension.

GET  /farmers/me
GET  /farmers/my-farms
POST /farmers/payout-details         FARMER only — upsert payout details
GET  /farmers/payout-details         FARMER only — view (masked)
POST /farmers/payout-details/verify  FARMER only — verify payout details format
GET  /farmers/payouts                FARMER only — view own payouts
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.dependencies import get_current_farmer, get_current_user
from app.models.user import User, UserRole
from app.models.farm import Farm
from app.models.farmer_profile import FarmerProfile
from app.models.payout import Payout
from app.schemas.user_schema import UserResponse
from app.schemas.farm_schema import FarmResponse
from app.schemas.farmer_profile_schema import FarmerPayoutDetailsUpsert, FarmerPayoutDetailsResponse
from app.schemas.payout_schema import PayoutResponse

router = APIRouter(prefix="/farmers", tags=["Farmers"])


# ── GET /farmers/me ───────────────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
def get_farmer_me(current_user: User = Depends(get_current_farmer)):
    return current_user


# ── GET /farmers/my-farms ─────────────────────────────────────────────────────
@router.get("/my-farms", response_model=List[FarmResponse])
def get_my_farms(
    current_user: User = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    farms = db.query(Farm).filter(Farm.farmer_id == current_user.id).all()
    return farms


# ── POST /farmers/payout-details ─────────────────────────────────────────────
@router.post(
    "/payout-details",
    response_model=FarmerPayoutDetailsResponse,
    status_code=status.HTTP_200_OK,
)
def upsert_payout_details(
    payload: FarmerPayoutDetailsUpsert,
    current_user: User = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    """
    Create or update payout details for the logged-in farmer.
    FARMER only. Bank account number is masked in responses.
    """
    profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == current_user.id).first()
    if profile is None:
        profile = FarmerProfile(user_id=current_user.id)
        db.add(profile)

    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    profile.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(profile)
    return FarmerPayoutDetailsResponse.from_orm_masked(profile)


# ── GET /farmers/payout-details ──────────────────────────────────────────────
@router.get(
    "/payout-details",
    response_model=FarmerPayoutDetailsResponse,
)
def get_payout_details(
    current_user: User = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    """Get payout details for the logged-in farmer. Bank account is masked."""
    profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payout details not set. POST /farmers/payout-details first.",
        )
    return FarmerPayoutDetailsResponse.from_orm_masked(profile)


# ── POST /farmers/payout-details/verify ──────────────────────────────────────
@router.post(
    "/payout-details/verify",
    response_model=FarmerPayoutDetailsResponse,
)
def verify_payout_details(
    current_user: User = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    """
    Verify the farmer's payout details by format check (Phase 10A).

    Checks:
    - UPI: must contain '@' (VPA format)
    - Bank transfer: account must be 9–18 digits + IFSC must be 11 chars

    On success: sets payout_details_verified = True, payout_verification_method = "FORMAT_CHECK".
    Returns masked payout details.

    Future: Penny Drop verification (PENNY_DROP method) for bank accounts.
    """
    profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payout details not set. POST /farmers/payout-details first.",
        )

    errors = []
    if profile.preferred_payout_method is None:
        errors.append("preferred_payout_method not set")
    elif profile.preferred_payout_method.value == "UPI":
        if not profile.upi_id or "@" not in profile.upi_id:
            errors.append("UPI ID is missing or invalid (must contain '@')")
    elif profile.preferred_payout_method.value == "BANK_TRANSFER":
        if not profile.bank_account_number or not (9 <= len(profile.bank_account_number) <= 18):
            errors.append("Bank account number is missing or invalid (must be 9–18 digits)")
        if not profile.ifsc_code or len(profile.ifsc_code) != 11:
            errors.append("IFSC code is missing or invalid (must be 11 characters)")

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Payout details verification failed: {'; '.join(errors)}",
        )

    profile.payout_details_verified = True
    profile.payout_details_verified_at = datetime.now(timezone.utc)
    profile.payout_verification_method = "FORMAT_CHECK"
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    return FarmerPayoutDetailsResponse.from_orm_masked(profile)


# ── GET /farmers/payouts ──────────────────────────────────────────────────────
@router.get(
    "/payouts",
    response_model=List[PayoutResponse],
)
def get_farmer_payouts(
    current_user: User = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    """Return all payouts for the logged-in farmer (newest first)."""
    payouts = (
        db.query(Payout)
        .filter(Payout.farmer_id == current_user.id)
        .order_by(Payout.initiated_at.desc())
        .all()
    )
    return payouts
