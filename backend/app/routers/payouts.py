"""
Payout router — Phase 9 Custodial Model.

POST /fpo/payouts/initiate              FPO only
POST /fpo/payouts/{payout_id}/complete  FPO only
GET  /fpo/payouts                       FPO only
GET  /admin/payouts                     ADMIN only
"""
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_admin
from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.farmer_credit_balance import FarmerCreditBalance, CreditBalanceStatus
from app.models.payout import Payout, PayoutStatus
from app.schemas.payout_schema import PayoutInitiateRequest, PayoutResponse, PayoutCompleteRequest
from app.services.payout_provider import get_payout_provider, PayoutRequest, MockPayoutProvider

router = APIRouter(tags=["Payouts"])


def _get_fpo_profile_or_403(current_user: User, db: Session) -> FPOProfile:
    if current_user.role != UserRole.FPO:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FPO only")
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")
    return profile


# ── POST /fpo/payouts/initiate ────────────────────────────────────────────────
@router.post(
    "/fpo/payouts/initiate",
    response_model=PayoutResponse,
    status_code=status.HTTP_201_CREATED,
)
def initiate_payout(
    payload: PayoutInitiateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FPO initiates a simulated payout for a farmer's credit balance.
    Validates that the balance belongs to this FPO and has sufficient credits.
    """
    fpo_profile = _get_fpo_profile_or_403(current_user, db)

    balance = db.query(FarmerCreditBalance).filter(
        FarmerCreditBalance.id == payload.credit_balance_id
    ).first()
    if not balance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credit balance not found")
    if balance.fpo_id != fpo_profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Balance does not belong to your FPO")
    if balance.credits_available < payload.amount_credits:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient credits. Available: {balance.credits_available}, requested: {payload.amount_credits}",
        )

    # Resolve payout method from farmer profile if available
    from app.models.farmer_profile import FarmerProfile
    farmer_profile = db.query(FarmerProfile).filter(
        FarmerProfile.user_id == balance.farmer_id
    ).first()
    payout_method = farmer_profile.preferred_payout_method.value if (
        farmer_profile and farmer_profile.preferred_payout_method
    ) else None

    idempotency_key = f"gc-payout-{balance.id}-{uuid.uuid4().hex[:16]}"

    payout = Payout(
        farmer_id=balance.farmer_id,
        fpo_id=fpo_profile.id,
        credit_balance_id=balance.id,
        amount_credits=payload.amount_credits,
        price_per_credit=payload.price_per_credit,
        payout_amount=payload.amount_credits * payload.price_per_credit,
        currency=payload.currency,
        payout_method=payout_method,
        status=PayoutStatus.INITIATED,
        initiated_by=current_user.id,
        initiated_at=datetime.now(timezone.utc),
        remarks=payload.remarks,
        idempotency_key=idempotency_key,
    )
    db.add(payout)
    db.commit()
    db.refresh(payout)

    # ── Attempt provider payout execution ─────────────────────────────────────
    # Only executes when:
    #   RAZORPAY_MODE=test + RAZORPAY_ENABLE_TEST_PAYOUTS=true (RazorpayX test mode)
    # Falls through silently for mock provider (mock's process_payout also works fine).
    # Failures are logged but do NOT block the initiation response.
    import logging as _logging
    _payout_log = _logging.getLogger(__name__)
    try:
        provider = get_payout_provider()
        is_mock = isinstance(provider, MockPayoutProvider)
        _payout_log.info(
            "payout_provider selected | payout_id=%s provider=%s is_mock=%s",
            payout.id,
            type(provider).__name__,
            is_mock,
        )
        farmer = db.query(User).filter(User.id == balance.farmer_id).first()

        # Build masked destination for safe logging
        if farmer_profile and farmer_profile.upi_id:
            upi = farmer_profile.upi_id
            at_idx = upi.find("@")
            if at_idx > 1:
                masked = upi[0] + "***" + upi[at_idx:]
            else:
                masked = upi[:1] + "***"
        elif farmer_profile and farmer_profile.bank_account_number:
            masked = "****" + farmer_profile.bank_account_number[-4:]
        else:
            masked = "N/A"

        payout_request = PayoutRequest(
            payout_id=payout.id,
            idempotency_key=idempotency_key,
            amount_paise=payout.payout_amount,
            currency=payout.currency,
            payout_method=payout_method or "BANK_TRANSFER",
            masked_destination=masked,
            farmer_name=farmer.name if farmer else "Unknown",
            remarks=payload.remarks,
            # Raw payment fields — used by RazorpayX only, never logged
            farmer_email=farmer.email if farmer else None,
            _raw_upi_id=farmer_profile.upi_id if farmer_profile else None,
            _raw_bank_account_number=farmer_profile.bank_account_number if farmer_profile else None,
            _raw_ifsc_code=farmer_profile.ifsc_code if farmer_profile else None,
            _raw_bank_account_holder_name=farmer_profile.bank_account_holder_name if farmer_profile else None,
        )

        result = provider.process_payout(payout_request)

        _payout_log.info(
            "process_payout result | payout_id=%s success=%s provider_reference_id_present=%s message=%s",
            payout.id,
            result.success,
            bool(result.provider_reference_id),
            result.message,
        )

        if result.provider_reference_id:
            payout.provider_reference_id = result.provider_reference_id
            db.add(payout)
            db.commit()
            db.refresh(payout)
        elif not result.success:
            # Provider returned a failure result (not an exception).
            # Store the failure reason in remarks so the mobile UI can surface it.
            # Payout stays INITIATED — it is NOT marked COMPLETED or FAILED automatically.
            # The FPO must either fix the provider config and re-initiate, or use Manual Override.
            _payout_log.warning(
                "process_payout returned success=False (non-fatal) | payout_id=%s | reason: %s",
                payout.id, result.message,
            )
            if result.message:
                payout.remarks = f"[PROVIDER_ERROR] {result.message}"
                db.add(payout)
                db.commit()
                db.refresh(payout)

    except Exception:
        # Payout is already saved as INITIATED — log but don't fail the request
        _payout_log.exception(
            "process_payout exception (non-fatal) payout_id=%s", payout.id
        )

    return payout


# ── POST /fpo/payouts/{payout_id}/complete ────────────────────────────────────
@router.post(
    "/fpo/payouts/{payout_id}/complete",
    response_model=PayoutResponse,
)
def complete_payout(
    payout_id: int,
    payload: PayoutCompleteRequest = PayoutCompleteRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark a payout as COMPLETED. Updates the credit balance:
    - credits_distributed += amount_credits
    - credits_available   -= amount_credits
    - If credits_available == 0, set balance status to DISTRIBUTED.
    FPO only (must own the payout).
    """
    fpo_profile = _get_fpo_profile_or_403(current_user, db)

    payout = db.query(Payout).filter(Payout.id == payout_id).first()
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout not found")
    if payout.fpo_id != fpo_profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Payout does not belong to your FPO")
    if payout.status != PayoutStatus.INITIATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete payout in status {payout.status.value}",
        )

    # Update credit balance
    balance = db.query(FarmerCreditBalance).filter(
        FarmerCreditBalance.id == payout.credit_balance_id
    ).first()
    if balance:
        balance.credits_distributed += payout.amount_credits
        balance.credits_available   -= payout.amount_credits
        if balance.credits_available <= 0:
            balance.credits_available = 0
            balance.status = CreditBalanceStatus.DISTRIBUTED
        balance.updated_at = datetime.now(timezone.utc)
        db.add(balance)

    # Mark payout completed (manual override — does not call Razorpay)
    payout.status = PayoutStatus.COMPLETED
    payout.completed_at = datetime.now(timezone.utc)
    payout.completed_by = current_user.id
    # Tag remarks so the audit trail is clear:
    # - If remarks supplied, prepend [MANUAL] prefix
    # - If no remarks, record that completion was done manually without provider confirmation
    if payload.remarks:
        payout.remarks = f"[MANUAL] {payload.remarks}"
    elif not payout.provider_reference_id:
        # No Razorpay reference → pure manual — always note it
        payout.remarks = "[MANUAL] Completed without provider confirmation"
    db.add(payout)
    db.commit()
    db.refresh(payout)
    return payout


# ── GET /fpo/payouts ──────────────────────────────────────────────────────────
@router.get(
    "/fpo/payouts",
    response_model=List[PayoutResponse],
)
def get_fpo_payouts(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all payouts initiated by this FPO."""
    fpo_profile = _get_fpo_profile_or_403(current_user, db)
    payouts = (
        db.query(Payout)
        .filter(Payout.fpo_id == fpo_profile.id)
        .order_by(Payout.initiated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return payouts


# ── GET /admin/payouts ────────────────────────────────────────────────────────
@router.get(
    "/admin/payouts",
    response_model=List[PayoutResponse],
)
def get_admin_payouts(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """List all payouts on the platform. ADMIN only."""
    payouts = (
        db.query(Payout)
        .order_by(Payout.initiated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return payouts
