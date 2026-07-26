from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.dependencies import get_current_user, get_current_verifier
from app.models.user import User, UserRole
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.verification import VerificationRequest, VerificationStatus
from app.models.sensor import SensorReading
from app.models.satellite_observation import SatelliteObservation
from app.models.drone_observation import DroneObservation
from app.models.evidence import EvidenceFile
from app.models.farm import Farm, FarmStatus
from app.services.verification_engine import calculate_risk
from app.schemas.verification_schema import (
    VerificationRequestResponse, ApproveRequest, RejectRequest,
)

router = APIRouter(prefix="/verification", tags=["Verification"])


def _get_vr_or_404(verification_id: int, db: Session) -> VerificationRequest:
    vr = db.query(VerificationRequest).filter(VerificationRequest.id == verification_id).first()
    if not vr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification request not found")
    return vr


def _enrich_vr(vr: VerificationRequest, db: Session) -> dict:
    """
    Build a dict that extends the VerificationRequest ORM object with
    computed evidence summary, re-calculated risk factors, and verifier name.

    These fields are NOT stored in the DB — they are derived on read from
    the related carbon report, sensor readings, satellite/drone observations,
    evidence files, farm approval status, and users table.
    """
    report = db.query(CarbonReport).filter(CarbonReport.id == vr.carbon_report_id).first()

    sensor_count = 0
    satellite_count = 0
    drone_count = 0
    avg_quality: float = 0.0
    num_evidence = 0
    farm_is_approved = True
    baseline_methane = 0.0
    current_methane = 0.0
    methane_reduction = 0.0
    co2e = 0.0
    credits = 0

    if report:
        cycle_id = report.crop_cycle_id

        sensor_count = (
            db.query(func.count(SensorReading.id))
            .filter(SensorReading.crop_cycle_id == cycle_id)
            .scalar()
        ) or 0

        avg_quality = float(
            db.query(func.avg(SensorReading.data_quality_score))
            .filter(SensorReading.crop_cycle_id == cycle_id)
            .scalar() or 0.0
        )

        satellite_count = (
            db.query(func.count(SatelliteObservation.id))
            .filter(SatelliteObservation.crop_cycle_id == cycle_id)
            .scalar()
        ) or 0

        drone_count = (
            db.query(func.count(DroneObservation.id))
            .filter(DroneObservation.crop_cycle_id == cycle_id)
            .scalar()
        ) or 0

        num_evidence = (
            db.query(func.count(EvidenceFile.id))
            .filter(EvidenceFile.crop_cycle_id == cycle_id)
            .scalar()
        ) or 0

        farm = db.query(Farm).filter(Farm.id == report.farm_id).first()
        farm_is_approved = (farm.farm_status == FarmStatus.APPROVED) if farm else True

        baseline_methane = report.baseline_methane_kg
        current_methane = report.current_methane_kg
        methane_reduction = report.methane_reduction_kg
        co2e = report.co2e_reduction_tonnes
        credits = report.estimated_credits

    # Re-compute risk factors (deterministic from the same inputs used at submission)
    risk_result = calculate_risk(
        num_readings=sensor_count,
        avg_quality_score=avg_quality,
        num_evidence_files=num_evidence,
        farm_is_approved=farm_is_approved,
        baseline_methane_kg=baseline_methane,
        methane_reduction_kg=methane_reduction,
        estimated_credits=credits,
    )

    # Verifier name
    verifier_name: str | None = None
    if vr.verifier_id:
        verifier = db.query(User).filter(User.id == vr.verifier_id).first()
        if verifier:
            verifier_name = verifier.name

    base = {
        "id": vr.id,
        "carbon_report_id": vr.carbon_report_id,
        "verifier_id": vr.verifier_id,
        "status": vr.status,
        "remarks": vr.remarks,
        "risk_score": vr.risk_score,
        "risk_level": vr.risk_level,
        "recommendation": vr.recommendation,
        "verified_at": vr.verified_at,
        "created_at": vr.created_at,
        # Enriched
        "risk_factors": risk_result.factors_triggered,
        "sensor_count": sensor_count,
        "satellite_count": satellite_count,
        "drone_count": drone_count,
        "avg_quality_score": round(avg_quality, 2) if sensor_count > 0 else None,
        "num_evidence_files": num_evidence,
        "baseline_methane_kg": round(baseline_methane, 4) if report else None,
        "current_methane_kg": round(current_methane, 4) if report else None,
        "methane_reduction_kg": round(methane_reduction, 4) if report else None,
        "co2e_reduction_tonnes": round(co2e, 6) if report else None,
        "estimated_credits": credits if report else None,
        "verifier_name": verifier_name,
    }
    return base


_FARM_NOT_APPROVED_MSG = "Farm must be approved by FPO before verification."


def _assert_farm_approved_for_vr(vr: VerificationRequest, db: Session):
    """Raise 400 if the underlying farm is not FPO-approved."""
    report = db.query(CarbonReport).filter(CarbonReport.id == vr.carbon_report_id).first()
    if report:
        farm = db.query(Farm).filter(Farm.id == report.farm_id).first()
        if farm and farm.farm_status != FarmStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_FARM_NOT_APPROVED_MSG,
            )


# ── GET /verification/pending ─────────────────────────────────────────────────
@router.get("/pending", response_model=List[VerificationRequestResponse])
def list_pending(
    current_user: User = Depends(get_current_verifier),
    db: Session = Depends(get_db),
):
    """
    Return pending verifications whose underlying farm is FPO-approved.
    Unapproved-farm reports are silently excluded from the queue.
    """
    pending = (
        db.query(VerificationRequest)
        .filter(VerificationRequest.status == VerificationStatus.PENDING)
        .order_by(VerificationRequest.created_at.asc())
        .all()
    )
    # Filter: only include requests where the farm is approved
    result = []
    for vr in pending:
        report = db.query(CarbonReport).filter(CarbonReport.id == vr.carbon_report_id).first()
        if report:
            farm = db.query(Farm).filter(Farm.id == report.farm_id).first()
            if farm and farm.farm_status != FarmStatus.APPROVED:
                continue  # exclude from queue — farm not APPROVED
        result.append(vr)
    return result


# ── GET /verification/{verification_id} ───────────────────────────────────────
@router.get("/{verification_id}", response_model=VerificationRequestResponse)
def get_verification(
    verification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in (UserRole.VERIFIER, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    vr = _get_vr_or_404(verification_id, db)
    _assert_farm_approved_for_vr(vr, db)
    return _enrich_vr(vr, db)


# ── POST /verification/{verification_id}/approve ──────────────────────────────
@router.post("/{verification_id}/approve", response_model=VerificationRequestResponse)
def approve_verification(
    verification_id: int,
    payload: ApproveRequest = ApproveRequest(),
    current_user: User = Depends(get_current_verifier),
    db: Session = Depends(get_db),
):
    vr = _get_vr_or_404(verification_id, db)
    _assert_farm_approved_for_vr(vr, db)

    if vr.status != VerificationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PENDING requests can be approved. Current status: {vr.status.value}",
        )

    now = datetime.now(timezone.utc)
    vr.status = VerificationStatus.APPROVED
    vr.verifier_id = current_user.id
    vr.verified_at = now
    if payload.remarks:
        vr.remarks = payload.remarks

    report = db.query(CarbonReport).filter(CarbonReport.id == vr.carbon_report_id).first()
    if report:
        report.status = ReportStatus.VERIFIED
        db.add(report)

    db.add(vr)
    db.commit()
    db.refresh(vr)
    return _enrich_vr(vr, db)


# ── POST /verification/{verification_id}/reject ───────────────────────────────
@router.post("/{verification_id}/reject", response_model=VerificationRequestResponse)
def reject_verification(
    verification_id: int,
    payload: RejectRequest,
    current_user: User = Depends(get_current_verifier),
    db: Session = Depends(get_db),
):
    vr = _get_vr_or_404(verification_id, db)
    _assert_farm_approved_for_vr(vr, db)

    if vr.status != VerificationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PENDING requests can be rejected. Current status: {vr.status.value}",
        )

    now = datetime.now(timezone.utc)
    vr.status = VerificationStatus.REJECTED
    vr.verifier_id = current_user.id
    vr.verified_at = now
    vr.remarks = payload.remarks

    report = db.query(CarbonReport).filter(CarbonReport.id == vr.carbon_report_id).first()
    if report:
        report.status = ReportStatus.REJECTED
        db.add(report)

    db.add(vr)
    db.commit()
    db.refresh(vr)
    return _enrich_vr(vr, db)
