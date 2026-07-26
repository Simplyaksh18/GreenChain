"""
ai.py — Phase 18 AI Layer endpoints.

4 endpoints:
  POST /ai/mrv-summary/{farm_id}                — Farmer or FPO
  POST /ai/verification-assist/{vr_id}          — Verifier only
  POST /ai/fpo/action-summary                   — FPO only
  POST /ai/farmer/help                          — Farmer only

SAFETY INVARIANTS:
  * All endpoints are read-only. No DB writes.
  * Responses are advisory and carry a DISCLAIMER field.
  * AI never auto-approves or auto-rejects anything.
  * AI never changes credit amounts, report status, or any record.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    get_current_farmer,
    get_current_fpo,
    get_current_user,
    get_current_verifier,
)
from app.models.farm import Farm
from app.models.fpo import FPOProfile
from app.models.user import User, UserRole
from app.schemas.ai_schema import (
    FarmerHelpRequest,
    FarmerHelpResponse,
    FPOActionSummaryResponse,
    MRVSummaryResponse,
    VerificationAssistResponse,
)
from app.services import ai_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])


# ── MRV Summary ────────────────────────────────────────────────────────────────

@router.post(
    "/mrv-summary/{farm_id}",
    response_model=MRVSummaryResponse,
    summary="AI MRV summary for a farm",
    description=(
        "Returns an AI-generated summary and insights for the MRV data of a farm. "
        "Accessible by the farm owner (FARMER role) or by any FPO member. "
        "Read-only — does not alter any record."
    ),
)
def mrv_summary(
    farm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MRVSummaryResponse:
    # Role gate: farmer (own farms only) or FPO
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")

    if current_user.role == UserRole.FARMER:
        if farm.farmer_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only view summaries for your own farms")
    elif current_user.role == UserRole.FPO:
        fpo_profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
        if fpo_profile is None or farm.fpo_id != fpo_profile.id:
            raise HTTPException(status_code=403, detail="Farm is not linked to your FPO")
    else:
        raise HTTPException(status_code=403, detail="Farmers and FPO members can access this endpoint")

    try:
        return ai_service.get_mrv_summary(farm_id=farm_id, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("mrv_summary error for farm %d: %s", farm_id, exc)
        raise HTTPException(status_code=500, detail="AI service error")


# ── Verification Assist ────────────────────────────────────────────────────────

@router.post(
    "/verification-assist/{verification_request_id}",
    response_model=VerificationAssistResponse,
    summary="AI verification risk assessment",
    description=(
        "Returns risk level, evidence checklist, fraud flags, and a non-binding "
        "recommendation for a verification request. "
        "Verifier role only. Human verifier makes the final approval decision. "
        "Read-only — does not alter any record or status."
    ),
)
def verification_assist(
    verification_request_id: int,
    current_user: User = Depends(get_current_verifier),  # 403 if not VERIFIER
    db: Session = Depends(get_db),
) -> VerificationAssistResponse:
    try:
        return ai_service.get_verification_assist(
            verification_request_id=verification_request_id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("verification_assist error for VR %d: %s", verification_request_id, exc)
        raise HTTPException(status_code=500, detail="AI service error")


# ── FPO Action Summary ─────────────────────────────────────────────────────────

@router.post(
    "/fpo/action-summary",
    response_model=FPOActionSummaryResponse,
    summary="AI action summary for FPO dashboard",
    description=(
        "Returns a prioritised list of action items for the calling FPO "
        "(pending approvals, mintable reports, open payouts, evidence gaps). "
        "FPO role only. Read-only."
    ),
)
def fpo_action_summary(
    current_user: User = Depends(get_current_fpo),  # 403 if not FPO
    db: Session = Depends(get_db),
) -> FPOActionSummaryResponse:
    fpo_profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if fpo_profile is None:
        raise HTTPException(status_code=404, detail="FPO profile not found. Create a profile first.")

    try:
        return ai_service.get_fpo_action_summary(fpo_id=fpo_profile.id, db=db)
    except Exception as exc:
        logger.exception("fpo_action_summary error for fpo %d: %s", fpo_profile.id, exc)
        raise HTTPException(status_code=500, detail="AI service error")


# ── Farmer Help ────────────────────────────────────────────────────────────────

@router.post(
    "/farmer/help",
    response_model=FarmerHelpResponse,
    summary="AI help text for farmers",
    description=(
        "Returns plain-language explanation and insights for a farmer topic. "
        "Farmer role only. Optionally provide farm_id or report_id for "
        "context-aware responses. Read-only."
    ),
)
def farmer_help(
    payload: FarmerHelpRequest,
    current_user: User = Depends(get_current_farmer),  # 403 if not FARMER
    db: Session = Depends(get_db),
) -> FarmerHelpResponse:
    # If farm_id provided, verify it belongs to this farmer
    if payload.farm_id is not None:
        farm = db.query(Farm).filter(Farm.id == payload.farm_id).first()
        if farm is None or farm.farmer_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="farm_id does not belong to you",
            )

    try:
        return ai_service.get_farmer_help(
            topic=payload.topic,
            db=db,
            farm_id=payload.farm_id,
            report_id=payload.report_id,
        )
    except Exception as exc:
        logger.exception("farmer_help error: %s", exc)
        raise HTTPException(status_code=500, detail="AI service error")
