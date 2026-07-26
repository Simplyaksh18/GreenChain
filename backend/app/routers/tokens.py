import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_admin
from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.farm import Farm
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.carbon_token import CarbonToken, TokenStatus
from app.schemas.carbon_token_schema import CarbonTokenResponse, TokenSummaryResponse
from app.services.token_service import mint_carbon_token, retire_token, suspend_token, TokenMintError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Tokens"])


# ── GET /fpo/tokens/minted-report-ids ─────────────────────────────────────────
@router.get(
    "/fpo/tokens/minted-report-ids",
    response_model=List[int],
)
def get_fpo_minted_report_ids(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns list of carbon_report_id values for tokens already minted under this FPO.
    FPO only. Used by FPOMintScreen to filter out already-minted reports before display,
    since GET /tokens/my-wallet is FARMER-only and FPOs have no other token listing endpoint.
    """
    if current_user.role != UserRole.FPO:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FPO only")

    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        return []

    farm_ids = [r[0] for r in db.query(Farm.id).filter(Farm.fpo_id == profile.id).all()]
    if not farm_ids:
        return []

    report_ids = [
        r[0] for r in db.query(CarbonReport.id)
        .filter(CarbonReport.farm_id.in_(farm_ids))
        .all()
    ]
    if not report_ids:
        return []

    tokens = (
        db.query(CarbonToken)
        .filter(CarbonToken.carbon_report_id.in_(report_ids))
        .all()
    )
    return [t.carbon_report_id for t in tokens]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_report_or_404(report_id: int, db: Session) -> CarbonReport:
    report = db.query(CarbonReport).filter(CarbonReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carbon report not found")
    return report


def _get_token_or_404(token_id: int, db: Session) -> CarbonToken:
    token = db.query(CarbonToken).filter(CarbonToken.id == token_id).first()
    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    return token


def _assert_token_view_access(token: CarbonToken, current_user: User, db: Session):
    """FARMER (own), FPO (linked farm), VERIFIER, ADMIN."""
    if current_user.role in (UserRole.ADMIN, UserRole.VERIFIER):
        return
    if current_user.role == UserRole.FARMER:
        if token.farmer_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return
    if current_user.role == UserRole.FPO:
        report = db.query(CarbonReport).filter(CarbonReport.id == token.carbon_report_id).first()
        farm = db.query(Farm).filter(Farm.id == report.farm_id).first() if report else None
        profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
        if not profile or not farm or farm.fpo_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _token_response(token: CarbonToken) -> CarbonTokenResponse:
    return CarbonTokenResponse.from_orm_with_flag(token)


# ── POST /admin/tokens/mint/{report_id} ───────────────────────────────────────
@router.post(
    "/admin/tokens/mint/{report_id}",
    response_model=CarbonTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def mint_token(
    report_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Mint a carbon token for a VERIFIED report. ADMIN only.
    Raises 400 if already minted or report not VERIFIED.
    """
    report = _get_report_or_404(report_id, db)
    farm = db.query(Farm).filter(Farm.id == report.farm_id).first()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    # Phase 9: resolve FPO for custodial minting (optional — backward compat preserved)
    fpo_id: int | None = None
    if farm.fpo_id is not None:
        fpo_profile = db.query(FPOProfile).filter(FPOProfile.id == farm.fpo_id).first()
        if fpo_profile:
            fpo_id = fpo_profile.id

    try:
        token = mint_carbon_token(
            report, farm.farmer_id, db,
            fpo_id=fpo_id,
            beneficiary_farmer_id=farm.farmer_id,
        )
    except TokenMintError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return _token_response(token)


# ── POST /fpo/tokens/mint/{report_id} ─────────────────────────────────────────
@router.post(
    "/fpo/tokens/mint/{report_id}",
    response_model=CarbonTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def fpo_mint_token(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FPO mints a custodial carbon token for a verified report linked to its farms.
    Enforces FPO ownership of the linked farm.
    """
    if current_user.role != UserRole.FPO:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FPO only")

    report = _get_report_or_404(report_id, db)
    farm = db.query(Farm).filter(Farm.id == report.farm_id).first()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")

    # Verify farm is linked to this FPO
    fpo_profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not fpo_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FPO profile not found. Create profile first.",
        )

    logger.info(
        "fpo_mint_token | report_id=%s report_status=%s report_farm_id=%s "
        "farm_farmer_id=%s farm_fpo_id=%s current_fpo_user_id=%s fpo_profile_id=%s "
        "fpo_wallet=%s estimated_credits=%s",
        report_id,
        report.status.value if report.status else "None",
        report.farm_id,
        farm.farmer_id,
        farm.fpo_id,
        current_user.id,
        fpo_profile.id,
        fpo_profile.wallet_address or "(not set)",
        report.estimated_credits,
    )

    if farm.fpo_id != fpo_profile.id:
        logger.warning(
            "fpo_mint_token BLOCKED | farm.fpo_id=%s != fpo_profile.id=%s",
            farm.fpo_id, fpo_profile.id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Farm is not linked to your FPO",
        )

    try:
        token = mint_carbon_token(
            report, farm.farmer_id, db,
            fpo_id=fpo_profile.id,
            beneficiary_farmer_id=farm.farmer_id,
        )
    except TokenMintError as exc:
        logger.error(
            "fpo_mint_token TokenMintError | report_id=%s error=%s",
            report_id, str(exc),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    logger.info(
        "fpo_mint_token SUCCESS | report_id=%s token_id=%s tx_hash=%s",
        report_id, token.token_id, token.minted_tx_hash,
    )
    return _token_response(token)


# ── GET /tokens/my-wallet ─────────────────────────────────────────────────────
@router.get(
    "/tokens/my-wallet",
    response_model=List[CarbonTokenResponse],
)
def my_wallet(
    token_status: Optional[TokenStatus] = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns tokens belonging to the logged-in farmer.

    Optional filter: status (MINTED | RETIRED | SUSPENDED)
    Pagination: limit (default 100), offset (default 0)
    FARMER only.
    """
    if current_user.role != UserRole.FARMER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Farmers only")
    q = (
        db.query(CarbonToken)
        .filter(CarbonToken.farmer_id == current_user.id)
        .order_by(CarbonToken.created_at.desc())
    )
    if token_status is not None:
        q = q.filter(CarbonToken.status == token_status)
    tokens = q.offset(offset).limit(limit).all()
    return [_token_response(t) for t in tokens]


# ── GET /tokens/{token_id} ────────────────────────────────────────────────────
@router.get(
    "/tokens/{token_id}",
    response_model=CarbonTokenResponse,
)
def get_token(
    token_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single token. FARMER (own), FPO (linked), VERIFIER, ADMIN."""
    token = _get_token_or_404(token_id, db)
    _assert_token_view_access(token, current_user, db)
    return _token_response(token)


# ── POST /admin/tokens/{token_id}/retire ──────────────────────────────────────
@router.post(
    "/admin/tokens/{token_id}/retire",
    response_model=CarbonTokenResponse,
)
def retire_token_endpoint(
    token_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Retire a token. ADMIN only."""
    token = _get_token_or_404(token_id, db)
    if token.status == TokenStatus.RETIRED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token is already retired")
    token = retire_token(token, db)
    return _token_response(token)


# ── POST /admin/tokens/{token_id}/suspend ─────────────────────────────────────
@router.post(
    "/admin/tokens/{token_id}/suspend",
    response_model=CarbonTokenResponse,
)
def suspend_token_endpoint(
    token_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Suspend a token. ADMIN only."""
    token = _get_token_or_404(token_id, db)
    if token.status == TokenStatus.SUSPENDED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token is already suspended")
    token = suspend_token(token, db)
    return _token_response(token)
