from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.models.farm import Farm, FarmStatus
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.carbon_token import CarbonToken, TokenStatus
from app.models.farmer_credit_balance import FarmerCreditBalance
from app.models.payout import Payout
from app.models.verification import VerificationRequest
from app.schemas.verification_schema import VerificationRequestResponse
from app.schemas.carbon_token_schema import TokenSummaryResponse

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── GET /admin/risk-reports ───────────────────────────────────────────────────
@router.get("/risk-reports", response_model=List[VerificationRequestResponse])
def get_risk_reports(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """All verification requests sorted by risk_score descending (highest risk first)."""
    return (
        db.query(VerificationRequest)
        .order_by(VerificationRequest.risk_score.desc())
        .all()
    )


# ── GET /admin/token-summary ──────────────────────────────────────────────────
@router.get("/token-summary", response_model=TokenSummaryResponse)
def token_summary(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Aggregate token statistics for the admin dashboard. ADMIN only."""
    all_tokens = db.query(CarbonToken).all()
    total_tokens     = len(all_tokens)
    active_tokens    = sum(1 for t in all_tokens if t.status == TokenStatus.MINTED)
    retired_tokens   = sum(1 for t in all_tokens if t.status == TokenStatus.RETIRED)
    suspended_tokens = sum(1 for t in all_tokens if t.status == TokenStatus.SUSPENDED)
    total_minted_credits    = sum(t.credit_amount for t in all_tokens)
    zero_credit_certificates = sum(1 for t in all_tokens if t.credit_amount == 0)

    return TokenSummaryResponse(
        total_tokens=total_tokens,
        total_minted_credits=total_minted_credits,
        active_tokens=active_tokens,
        retired_tokens=retired_tokens,
        suspended_tokens=suspended_tokens,
        zero_credit_certificates=zero_credit_certificates,
    )


# ── GET /admin/workflow-status ────────────────────────────────────────────────
@router.get("/workflow-status")
def workflow_status(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Aggregate workflow diagnostic counts for identifying bottlenecks.
    ADMIN only.
    """
    farms_total    = db.query(func.count(Farm.id)).scalar() or 0
    farms_approved = db.query(func.count(Farm.id)).filter(
        Farm.farm_status == FarmStatus.APPROVED
    ).scalar() or 0

    reports_draft      = db.query(func.count(CarbonReport.id)).filter(
        CarbonReport.status == ReportStatus.DRAFT
    ).scalar() or 0
    reports_submitted  = db.query(func.count(CarbonReport.id)).filter(
        CarbonReport.status == ReportStatus.SUBMITTED
    ).scalar() or 0
    reports_verified   = db.query(func.count(CarbonReport.id)).filter(
        CarbonReport.status == ReportStatus.VERIFIED
    ).scalar() or 0
    reports_rejected   = db.query(func.count(CarbonReport.id)).filter(
        CarbonReport.status == ReportStatus.REJECTED
    ).scalar() or 0

    # Reports verified but no token minted yet = mintable
    verified_report_ids = [
        r[0] for r in db.query(CarbonReport.id).filter(
            CarbonReport.status == ReportStatus.VERIFIED
        ).all()
    ]
    minted_report_ids = set(
        r[0] for r in db.query(CarbonToken.carbon_report_id).filter(
            CarbonToken.carbon_report_id.in_(verified_report_ids)
        ).all()
    ) if verified_report_ids else set()
    reports_mintable  = len([r for r in verified_report_ids if r not in minted_report_ids])
    reports_tokenized = db.query(func.count(CarbonToken.id)).scalar() or 0

    credits_total  = db.query(func.sum(CarbonToken.credit_amount)).scalar() or 0
    payouts_total  = db.query(func.count(Payout.id)).scalar() or 0

    return {
        "farms_total": farms_total,
        "farms_approved": farms_approved,
        "reports_draft": reports_draft,
        "reports_submitted": reports_submitted,
        "reports_verified": reports_verified,
        "reports_rejected": reports_rejected,
        "reports_mintable": reports_mintable,
        "reports_tokenized": reports_tokenized,
        "credits_total": int(credits_total),
        "payouts_total": payouts_total,
    }
