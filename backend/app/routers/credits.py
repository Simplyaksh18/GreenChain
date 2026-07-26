"""
Credit Balance router — Phase 9 Custodial Model.

GET /credits/my-balance                           FARMER only
GET /fpo/credits/farmers                          FPO only — all farmer balances under FPO (enriched)
GET /fpo/credits/farmers/{balance_id}/payout-details  FPO only — farmer payout info for a balance
GET /admin/credits/summary                        ADMIN only
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

# Fix for passlib/bcrypt incompatibility: inject __about__ if missing
try:
    import bcrypt
    if not hasattr(bcrypt, "__about__"):
        bcrypt.__about__ = type("about", (object,), {"__version__": bcrypt.__version__})
except ImportError:
    pass

logger = logging.getLogger(__name__)

from app.database import get_db
from app.dependencies import get_current_user, get_current_admin
from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.farmer_credit_balance import FarmerCreditBalance, CreditBalanceStatus
from app.schemas.credit_balance_schema import (
    CreditBalanceResponse,
    EnrichedCreditBalanceResponse,
    FarmerCreditSummaryResponse,
    PlatformCreditSummaryResponse,
)

router = APIRouter(tags=["Credits"])


# ── GET /credits/my-balance ───────────────────────────────────────────────────
@router.get(
    "/credits/my-balance",
    response_model=FarmerCreditSummaryResponse,
)
def get_my_credit_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the credit balance summary for the logged-in farmer."""
    if current_user.role != UserRole.FARMER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Farmers only")

    balances = (
        db.query(FarmerCreditBalance)
        .filter(FarmerCreditBalance.farmer_id == current_user.id)
        .order_by(FarmerCreditBalance.created_at.desc())
        .all()
    )

    total_earned      = sum(b.credits_earned for b in balances)
    total_distributed = sum(b.credits_distributed for b in balances)
    total_available   = sum(b.credits_available for b in balances)
    total_tokenized   = sum(
        b.credits_earned for b in balances if b.status == CreditBalanceStatus.TOKENIZED
    )

    # Dev-mode diagnostic log — no PII, only aggregate credit values
    logger.info(
        "GET /credits/my-balance | farmer_id=%s balance_count=%s "
        "total_earned=%s total_available=%s total_distributed=%s total_tokenized=%s",
        current_user.id,
        len(balances),
        total_earned,
        total_available,
        total_distributed,
        total_tokenized,
    )

    return FarmerCreditSummaryResponse(
        total_earned=total_earned,
        total_distributed=total_distributed,
        total_available=total_available,
        total_tokenized=total_tokenized,
        balances=[CreditBalanceResponse.model_validate(b) for b in balances],
    )


# ── GET /fpo/credits/farmers ──────────────────────────────────────────────────
@router.get(
    "/fpo/credits/farmers",
    response_model=List[EnrichedCreditBalanceResponse],
)
def get_fpo_farmer_balances(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all farmer credit balances under this FPO, enriched with farmer and farm details."""
    if current_user.role != UserRole.FPO:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FPO only")

    fpo_profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not fpo_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")

    balances = (
        db.query(FarmerCreditBalance)
        .filter(FarmerCreditBalance.fpo_id == fpo_profile.id)
        .order_by(FarmerCreditBalance.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Enrich with farmer name/email, farm name, and payout method
    from app.models.user import User as UserModel
    from app.models.farm import Farm
    from app.models.carbon_report import CarbonReport
    from app.models.farmer_profile import FarmerProfile
    from app.schemas.farmer_profile_schema import _mask_upi

    results: List[EnrichedCreditBalanceResponse] = []
    for b in balances:
        farmer_user = db.query(UserModel).filter(UserModel.id == b.farmer_id).first()
        report = db.query(CarbonReport).filter(CarbonReport.id == b.carbon_report_id).first()
        farm = db.query(Farm).filter(Farm.id == report.farm_id).first() if report else None
        farmer_profile = db.query(FarmerProfile).filter(
            FarmerProfile.user_id == b.farmer_id
        ).first()

        enriched = EnrichedCreditBalanceResponse(
            **CreditBalanceResponse.model_validate(b).model_dump(),
            farmer_name=farmer_user.name if farmer_user else None,
            farmer_email=farmer_user.email if farmer_user else None,
            farm_name=farm.farm_name if farm else None,
            farmer_payout_method=(
                farmer_profile.preferred_payout_method.value
                if farmer_profile and farmer_profile.preferred_payout_method else None
            ),
            # Phase 10A: FPO sees masked UPI only — never raw UPI ID
            farmer_upi_id=_mask_upi(farmer_profile.upi_id) if (farmer_profile and farmer_profile.upi_id) else None,
        )
        results.append(enriched)
    return results


# ── GET /fpo/credits/farmers/{balance_id}/payout-details ─────────────────────
@router.get(
    "/fpo/credits/farmers/{balance_id}/payout-details",
    response_model=dict,
)
def get_farmer_payout_details_for_fpo(
    balance_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FPO views farmer payout details for a specific credit balance.
    Returns farmer name, email, payout method and masked account info.
    """
    if current_user.role != UserRole.FPO:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FPO only")

    fpo_profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not fpo_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")

    balance = db.query(FarmerCreditBalance).filter(FarmerCreditBalance.id == balance_id).first()
    if not balance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credit balance not found")
    if balance.fpo_id != fpo_profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Balance does not belong to your FPO")

    from app.models.user import User as UserModel
    from app.models.farmer_profile import FarmerProfile
    from app.schemas.farmer_profile_schema import _mask_upi, _mask_account
    farmer_user = db.query(UserModel).filter(UserModel.id == balance.farmer_id).first()
    farmer_profile = db.query(FarmerProfile).filter(
        FarmerProfile.user_id == balance.farmer_id
    ).first()

    # Phase 10A: mask all sensitive payout details before returning to FPO
    bank_acc_masked = _mask_account(farmer_profile.bank_account_number) if (farmer_profile and farmer_profile.bank_account_number) else None
    upi_masked = _mask_upi(farmer_profile.upi_id) if (farmer_profile and farmer_profile.upi_id) else None

    return {
        "farmer_id": balance.farmer_id,
        "farmer_name": farmer_user.name if farmer_user else None,
        "farmer_email": farmer_user.email if farmer_user else None,
        "preferred_payout_method": (
            farmer_profile.preferred_payout_method.value
            if farmer_profile and farmer_profile.preferred_payout_method else None
        ),
        # Phase 10A: FPO never sees raw UPI ID — only masked version
        "upi_id_masked": upi_masked,
        "bank_name": farmer_profile.bank_name if farmer_profile else None,
        "bank_account_holder_name": (
            farmer_profile.bank_account_holder_name if farmer_profile else None
        ),
        "bank_account_number_masked": bank_acc_masked,
        "ifsc_code": farmer_profile.ifsc_code if farmer_profile else None,
        "payout_details_verified": (
            farmer_profile.payout_details_verified if farmer_profile else False
        ),
        "has_payout_details": farmer_profile is not None and (
            farmer_profile.upi_id is not None
            or farmer_profile.bank_account_number is not None
        ),
    }


# ── GET /admin/credits/summary ────────────────────────────────────────────────
@router.get(
    "/admin/credits/summary",
    response_model=PlatformCreditSummaryResponse,
)
def get_platform_credit_summary(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Platform-wide credit balance summary. ADMIN only."""
    all_balances = db.query(FarmerCreditBalance).all()
    total = len(all_balances)
    total_earned      = sum(b.credits_earned for b in all_balances)
    total_distributed = sum(b.credits_distributed for b in all_balances)
    total_available   = sum(b.credits_available for b in all_balances)

    by_status: dict = {}
    for status_val in CreditBalanceStatus:
        by_status[status_val.value] = sum(
            1 for b in all_balances if b.status == status_val
        )

    return PlatformCreditSummaryResponse(
        total_balances=total,
        total_credits_earned=total_earned,
        total_credits_distributed=total_distributed,
        total_credits_available=total_available,
        by_status=by_status,
    )
