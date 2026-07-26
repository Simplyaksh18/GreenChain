from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.farm import Farm, CropCycle, FarmStatus
from app.models.sensor import SensorReading
from app.models.evidence import EvidenceFile
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.evidence import EvidenceFile
from app.models.verification import VerificationRequest, VerificationStatus
from app.schemas.carbon_report_schema import CarbonReportResponse, SubmitReportRequest
from app.services.carbon_calculator import calculate_carbon_report, InsufficientReadingsError
from app.services.verification_engine import calculate_risk

router = APIRouter(prefix="/carbon-reports", tags=["Carbon Reports"])


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _get_farm_or_404(farm_id: int, db: Session) -> Farm:
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    return farm


def _get_cycle_or_404(cycle_id: int, db: Session) -> CropCycle:
    cycle = db.query(CropCycle).filter(CropCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop cycle not found")
    return cycle


def _assert_generate_access(farm: Farm, current_user: User, db: Session):
    """FARMER (own), FPO (linked), ADMIN. VERIFIER blocked."""
    if current_user.role == UserRole.VERIFIER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verifiers cannot generate reports")
    if current_user.role == UserRole.ADMIN:
        return
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


def _assert_view_access(farm: Farm, current_user: User, db: Session):
    """FARMER (own), FPO (linked), VERIFIER (all), ADMIN (all)."""
    if current_user.role in (UserRole.ADMIN, UserRole.VERIFIER):
        return
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


# ── POST /carbon-reports/generate/{crop_cycle_id} ─────────────────────────────
@router.post("/generate/{crop_cycle_id}", response_model=CarbonReportResponse, status_code=status.HTTP_201_CREATED)
def generate_carbon_report(
    crop_cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cycle = _get_cycle_or_404(crop_cycle_id, db)
    farm = _get_farm_or_404(cycle.farm_id, db)
    _assert_generate_access(farm, current_user, db)

    readings = (
        db.query(SensorReading)
        .filter(SensorReading.crop_cycle_id == crop_cycle_id)
        .order_by(SensorReading.reading_time.asc())
        .all()
    )

    try:
        calc = calculate_carbon_report(readings, farm.id, crop_cycle_id)
    except InsufficientReadingsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    report = CarbonReport(
        farm_id=farm.id,
        crop_cycle_id=crop_cycle_id,
        baseline_methane_kg=calc.baseline_methane_kg,
        current_methane_kg=calc.current_methane_kg,
        methane_reduction_kg=calc.methane_reduction_kg,
        co2e_reduction_tonnes=calc.co2e_reduction_tonnes,
        estimated_credits=calc.estimated_credits,
        report_hash=calc.report_hash,
        status=ReportStatus.DRAFT,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


# ── GET /carbon-reports/farm/{farm_id} ────────────────────────────────────────
@router.get("/farm/{farm_id}", response_model=List[CarbonReportResponse])
def list_reports_by_farm(
    farm_id: int,
    report_status: Optional[ReportStatus] = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List carbon reports for a farm.

    Optional filter: status (DRAFT | SUBMITTED | VERIFIED | REJECTED)
    Pagination: limit (default 100), offset (default 0)
    """
    farm = _get_farm_or_404(farm_id, db)
    _assert_view_access(farm, current_user, db)
    q = db.query(CarbonReport).filter(CarbonReport.farm_id == farm_id)
    if report_status is not None:
        q = q.filter(CarbonReport.status == report_status)
    return q.offset(offset).limit(limit).all()


# ── GET /carbon-reports/{report_id} ───────────────────────────────────────────
@router.get("/{report_id}", response_model=CarbonReportResponse)
def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.query(CarbonReport).filter(CarbonReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carbon report not found")
    farm = _get_farm_or_404(report.farm_id, db)
    _assert_view_access(farm, current_user, db)
    return report


# ── GET /carbon-reports/{report_id}/detail ────────────────────────────────────
@router.get("/{report_id}/detail")
def get_report_detail(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Full carbon report detail for verifiers and admins.
    Returns report data + farm info + crop cycle info + evidence files.

    Access: VERIFIER (all), ADMIN (all), FARMER (own farm), FPO (linked farm).
    """
    report = db.query(CarbonReport).filter(CarbonReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carbon report not found")

    farm = _get_farm_or_404(report.farm_id, db)
    _assert_view_access(farm, current_user, db)

    cycle = _get_cycle_or_404(report.crop_cycle_id, db)

    evidence = (
        db.query(EvidenceFile)
        .filter(EvidenceFile.carbon_report_id == report_id)
        .order_by(EvidenceFile.id.asc())
        .all()
    )

    return {
        "report": {
            "id": report.id,
            "status": report.status.value,
            "baseline_methane_kg": report.baseline_methane_kg,
            "current_methane_kg": report.current_methane_kg,
            "methane_reduction_kg": report.methane_reduction_kg,
            "co2e_reduction_tonnes": report.co2e_reduction_tonnes,
            "estimated_credits": report.estimated_credits,
            "report_hash": report.report_hash,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        },
        "farm": {
            "id": farm.id,
            "farm_name": farm.farm_name,
            "village": farm.village,
            "district": farm.district,
            "area_hectares": farm.boundary_area_hectares,
            "farm_status": farm.farm_status.value,
        },
        "crop_cycle": {
            "id": cycle.id,
            "crop_type": cycle.crop_type,
            "season": cycle.season,
            "start_date": str(cycle.start_date) if cycle.start_date else None,
            "end_date": str(cycle.end_date) if cycle.end_date else None,
            "baseline_method": cycle.baseline_method,
            "reduction_practice": cycle.reduction_practice,
        },
        "evidence_files": [
            {
                "id": ev.id,
                "file_url": ev.file_url,
                "file_type": ev.file_type,
                "evidence_type": ev.evidence_type,
                "description": ev.description,
                "file_hash": ev.file_hash if hasattr(ev, "file_hash") else None,
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
            }
            for ev in evidence
        ],
    }


# ── POST /carbon-reports/{report_id}/submit ───────────────────────────────────
@router.post("/{report_id}/submit", response_model=CarbonReportResponse)
def submit_report(
    report_id: int,
    payload: SubmitReportRequest = SubmitReportRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.query(CarbonReport).filter(CarbonReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carbon report not found")

    farm = _get_farm_or_404(report.farm_id, db)
    _assert_generate_access(farm, current_user, db)

    if report.status != ReportStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only DRAFT reports can be submitted. Current status: {report.status.value}",
        )

    # ── Farm approval gate ────────────────────────────────────────────────
    if farm.farm_status != FarmStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Farm must be approved by FPO before submitting for verification. "
                f"Current farm status: {farm.farm_status.value}"
            ),
        )

    # ── Build risk profile ────────────────────────────────────────────────
    num_readings = (
        db.query(func.count(SensorReading.id))
        .filter(SensorReading.crop_cycle_id == report.crop_cycle_id)
        .scalar()
    ) or 0

    avg_quality = (
        db.query(func.avg(SensorReading.data_quality_score))
        .filter(SensorReading.crop_cycle_id == report.crop_cycle_id)
        .scalar()
    ) or 0.0

    num_evidence = (
        db.query(func.count(EvidenceFile.id))
        .filter(EvidenceFile.crop_cycle_id == report.crop_cycle_id)
        .scalar()
    ) or 0

    risk = calculate_risk(
        num_readings=num_readings,
        avg_quality_score=float(avg_quality),
        num_evidence_files=num_evidence,
        farm_is_approved=farm.is_approved,
        baseline_methane_kg=report.baseline_methane_kg,
        methane_reduction_kg=report.methane_reduction_kg,
        estimated_credits=report.estimated_credits,
    )

    # ── Update report status ──────────────────────────────────────────────
    report.status = ReportStatus.SUBMITTED
    db.add(report)

    # ── Create verification request ───────────────────────────────────────
    vr = VerificationRequest(
        carbon_report_id=report.id,
        verifier_id=None,
        status=VerificationStatus.PENDING,
        remarks=payload.remarks,
        risk_score=risk.risk_score,
        risk_level=risk.risk_level,
        recommendation=risk.recommendation,
        verified_at=None,
    )
    db.add(vr)
    db.commit()
    db.refresh(report)
    return report
