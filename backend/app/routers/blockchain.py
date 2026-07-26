from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.dependencies import get_current_user, get_current_admin
from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.farm import Farm
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.blockchain_transaction import BlockchainTransaction
from app.schemas.blockchain_schema import BlockchainTransactionResponse
from app.services.blockchain_service import anchor_report_hash

router = APIRouter(prefix="/blockchain", tags=["Blockchain"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_report_or_404(report_id: int, db: Session) -> CarbonReport:
    report = db.query(CarbonReport).filter(CarbonReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carbon report not found")
    return report


def _assert_report_view_access(report: CarbonReport, current_user: User, db: Session):
    """FARMER (own farm), FPO (linked farm), VERIFIER, ADMIN."""
    if current_user.role in (UserRole.ADMIN, UserRole.VERIFIER):
        return
    farm = db.query(Farm).filter(Farm.id == report.farm_id).first()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    if current_user.role == UserRole.FARMER:
        if farm.farmer_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return
    if current_user.role == UserRole.FPO:
        profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
        if not profile or farm.fpo_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


# ── POST /blockchain/anchor-report/{report_id} ────────────────────────────────
@router.post(
    "/anchor-report/{report_id}",
    response_model=BlockchainTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def anchor_report(
    report_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Anchor a VERIFIED carbon report's hash on the blockchain.
    Idempotent: if already anchored, returns the existing transaction (still 201).
    ADMIN only.
    """
    report = _get_report_or_404(report_id, db)
    if report.status != ReportStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only VERIFIED reports can be anchored. Current status: {report.status.value}",
        )
    tx = anchor_report_hash(report, db)
    return tx


# ── GET /blockchain/report/{report_id} ────────────────────────────────────────
@router.get(
    "/report/{report_id}",
    response_model=List[BlockchainTransactionResponse],
)
def get_report_transactions(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all blockchain transactions for a carbon report.
    Roles: FARMER (own farm), FPO (linked farm), VERIFIER, ADMIN.
    """
    report = _get_report_or_404(report_id, db)
    _assert_report_view_access(report, current_user, db)
    return (
        db.query(BlockchainTransaction)
        .filter(BlockchainTransaction.carbon_report_id == report_id)
        .order_by(BlockchainTransaction.created_at.asc())
        .all()
    )
