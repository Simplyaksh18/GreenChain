"""
Public Registry — Phase 16.

Exposes verified carbon credit data publicly (no authentication required).

Privacy rules (strictly enforced):
  ✅ EXPOSE: project name, district/state, crop type, verified CO2e, credits,
             token status, short hashes, methodology summary, evidence count,
             verification status
  ❌ NEVER EXPOSE: farmer phone/email, UPI/bank details, wallet secrets,
                   raw private evidence URLs, full wallet addresses

Endpoints:
  GET /registry/public/reports
  GET /registry/public/reports/{report_id}
  GET /registry/public/tokens
  GET /registry/public/tokens/{token_id}
  GET /registry/public/farms/{farm_id}
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.carbon_token import CarbonToken, TokenStatus
from app.models.farm import Farm, CropCycle
from app.models.evidence import EvidenceFile
from app.models.verification import VerificationRequest, VerificationStatus
from app.models.fpo import FPOProfile
from app.models.blockchain_transaction import BlockchainTransaction

router = APIRouter(prefix="/registry/public", tags=["Public Registry"])


# ── Safe field helpers ────────────────────────────────────────────────────────

def _short_hash(h: Optional[str], length: int = 10) -> Optional[str]:
    """Return first+last chars of a hash for display — never the full hash."""
    if not h:
        return None
    if len(h) <= length * 2:
        return h
    return f"{h[:length]}...{h[-6:]}"


def _safe_report(
    report: CarbonReport,
    farm: Optional[Farm],
    cycle: Optional[CropCycle],
    evidence_count: int,
    verification_status: Optional[str],
    fpo_name: Optional[str],
) -> dict:
    """Build public-safe report dict. Strips all PII."""
    return {
        "id": report.id,
        "farm_id": report.farm_id,
        "farm_name": farm.farm_name if farm else None,
        "district": farm.district if farm else None,
        "state": farm.state if farm else None,
        "fpo_name": fpo_name,
        "crop_type": cycle.crop_type if cycle else None,
        "season": cycle.season if cycle else None,
        "baseline_method": cycle.baseline_method if cycle else None,
        "reduction_practice": cycle.reduction_practice if cycle else None,
        "verified_co2e_tonnes": report.co2e_reduction_tonnes,
        "estimated_credits": report.estimated_credits,
        "report_status": report.status.value,
        "report_hash_short": _short_hash(report.report_hash),
        "verification_status": verification_status,
        "evidence_count": evidence_count,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


def _safe_token(token: CarbonToken, report: Optional[CarbonReport], farm: Optional[Farm]) -> dict:
    """Build public-safe token dict."""
    return {
        "id": token.id,
        "token_id": token.token_id,
        "token_standard": token.token_standard,
        "credit_amount": token.credit_amount,
        "status": token.status.value,
        "carbon_report_id": token.carbon_report_id,
        "farm_name": farm.farm_name if farm else None,
        "district": farm.district if farm else None,
        "state": farm.state if farm else None,
        "verified_co2e_tonnes": report.co2e_reduction_tonnes if report else None,
        "minted_tx_hash_short": _short_hash(token.minted_tx_hash),
        "minted_at": token.minted_at.isoformat() if token.minted_at else None,
        "created_at": token.created_at.isoformat() if token.created_at else None,
    }


def _safe_farm(farm: Farm, db: Session) -> dict:
    """Build public-safe farm summary. No farmer contact details."""
    total_reports = db.query(func.count(CarbonReport.id)).filter(CarbonReport.farm_id == farm.id).scalar() or 0
    verified_reports = (
        db.query(func.count(CarbonReport.id))
        .filter(CarbonReport.farm_id == farm.id, CarbonReport.status == ReportStatus.VERIFIED)
        .scalar()
    ) or 0
    total_tokens = (
        db.query(func.count(CarbonToken.id))
        .join(CarbonReport, CarbonToken.carbon_report_id == CarbonReport.id)
        .filter(CarbonReport.farm_id == farm.id)
        .scalar()
    ) or 0

    fpo = db.query(FPOProfile).filter(FPOProfile.id == farm.fpo_id).first() if farm.fpo_id else None

    return {
        "id": farm.id,
        "farm_name": farm.farm_name,
        "village": farm.village,
        "district": farm.district,
        "state": farm.state,
        "land_area_acres": farm.land_area_acres,
        "boundary_area_hectares": farm.boundary_area_hectares,
        "fpo_name": fpo.organization_name if fpo else None,
        "farm_status": farm.farm_status.value,
        "total_reports": total_reports,
        "verified_reports": verified_reports,
        "total_tokens": total_tokens,
    }


def _enrich_report(report: CarbonReport, db: Session) -> dict:
    farm = db.query(Farm).filter(Farm.id == report.farm_id).first()
    cycle = db.query(CropCycle).filter(CropCycle.id == report.crop_cycle_id).first()
    evidence_count = (
        db.query(func.count(EvidenceFile.id))
        .filter(EvidenceFile.carbon_report_id == report.id)
        .scalar()
    ) or 0
    vr = (
        db.query(VerificationRequest)
        .filter(VerificationRequest.carbon_report_id == report.id)
        .first()
    )
    verification_status = vr.status.value if vr else None
    fpo = db.query(FPOProfile).filter(FPOProfile.id == farm.fpo_id).first() if (farm and farm.fpo_id) else None

    return _safe_report(
        report, farm, cycle, evidence_count, verification_status,
        fpo.organization_name if fpo else None,
    )


# ── GET /registry/public/reports ──────────────────────────────────────────────

@router.get("/reports")
def list_public_reports(
    state: Optional[str] = Query(default=None),
    district: Optional[str] = Query(default=None),
    crop_type: Optional[str] = Query(default=None),
    report_status: Optional[str] = Query(default=None, alias="status"),
    credit_min: Optional[int] = Query(default=None, ge=0),
    credit_max: Optional[int] = Query(default=None, ge=0),
    vintage_year: Optional[int] = Query(default=None),
    fpo_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Public registry of carbon reports (no authentication required).
    Returns only public fields — no PII, no wallet details.
    """
    # Only show verified or submitted reports publicly
    q = db.query(CarbonReport).filter(
        CarbonReport.status.in_([ReportStatus.VERIFIED, ReportStatus.SUBMITTED])
    )

    if report_status:
        try:
            q = q.filter(CarbonReport.status == ReportStatus(report_status))
        except ValueError:
            pass

    if credit_min is not None:
        q = q.filter(CarbonReport.estimated_credits >= credit_min)
    if credit_max is not None:
        q = q.filter(CarbonReport.estimated_credits <= credit_max)

    if vintage_year:
        q = q.filter(func.strftime('%Y', CarbonReport.created_at) == str(vintage_year))

    # Farm-level filters need a join
    if state or district or fpo_id:
        q = q.join(Farm, CarbonReport.farm_id == Farm.id)
        if state:
            q = q.filter(Farm.state.ilike(f"%{state}%"))
        if district:
            q = q.filter(Farm.district.ilike(f"%{district}%"))
        if fpo_id:
            fpo = db.query(FPOProfile).filter(FPOProfile.id == fpo_id).first()
            if fpo:
                q = q.filter(Farm.fpo_id == fpo_id)

    if crop_type:
        report_ids = (
            db.query(CarbonReport.id)
            .join(CropCycle, CarbonReport.crop_cycle_id == CropCycle.id)
            .filter(CropCycle.crop_type.ilike(f"%{crop_type}%"))
            .subquery()
        )
        q = q.filter(CarbonReport.id.in_(report_ids))

    reports = q.order_by(CarbonReport.id.desc()).offset(offset).limit(limit).all()
    return [_enrich_report(r, db) for r in reports]


# ── GET /registry/public/reports/{report_id} ──────────────────────────────────

@router.get("/reports/{report_id}")
def get_public_report(report_id: int, db: Session = Depends(get_db)):
    """Public detail for a single carbon report."""
    report = db.query(CarbonReport).filter(
        CarbonReport.id == report_id,
        CarbonReport.status.in_([ReportStatus.VERIFIED, ReportStatus.SUBMITTED]),
    ).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found or not yet verified")
    return _enrich_report(report, db)


# ── GET /registry/public/tokens ───────────────────────────────────────────────

@router.get("/tokens")
def list_public_tokens(
    state: Optional[str] = Query(default=None),
    district: Optional[str] = Query(default=None),
    token_status: Optional[str] = Query(default=None, alias="status"),
    credit_min: Optional[int] = Query(default=None, ge=0),
    credit_max: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Public listing of minted carbon tokens."""
    q = db.query(CarbonToken)

    if token_status:
        try:
            q = q.filter(CarbonToken.status == TokenStatus(token_status))
        except ValueError:
            pass
    if credit_min is not None:
        q = q.filter(CarbonToken.credit_amount >= credit_min)
    if credit_max is not None:
        q = q.filter(CarbonToken.credit_amount <= credit_max)

    tokens = q.order_by(CarbonToken.id.desc()).offset(offset).limit(limit).all()

    result = []
    for tok in tokens:
        report = db.query(CarbonReport).filter(CarbonReport.id == tok.carbon_report_id).first()
        farm = db.query(Farm).filter(Farm.id == report.farm_id).first() if report else None
        if state and (not farm or state.lower() not in (farm.state or "").lower()):
            continue
        if district and (not farm or district.lower() not in (farm.district or "").lower()):
            continue
        result.append(_safe_token(tok, report, farm))

    return result


# ── GET /registry/public/tokens/{token_id} ────────────────────────────────────

@router.get("/tokens/{token_id}")
def get_public_token(token_id: int, db: Session = Depends(get_db)):
    """Public detail for a single token."""
    token = db.query(CarbonToken).filter(CarbonToken.id == token_id).first()
    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    report = db.query(CarbonReport).filter(CarbonReport.id == token.carbon_report_id).first()
    farm = db.query(Farm).filter(Farm.id == report.farm_id).first() if report else None
    return _safe_token(token, report, farm)


# ── GET /registry/public/farms/{farm_id} ──────────────────────────────────────

@router.get("/farms/{farm_id}")
def get_public_farm(farm_id: int, db: Session = Depends(get_db)):
    """Public summary of an approved farm."""
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    return _safe_farm(farm, db)
