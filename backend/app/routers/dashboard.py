"""
Dashboard router — Phase 7.

GET /dashboard/farm/{farm_id}   — FARMER(own) / FPO(linked) / VERIFIER / ADMIN
GET /dashboard/admin            — ADMIN only
GET /dashboard/verifier         — VERIFIER / ADMIN
"""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.dependencies import get_current_admin
from app.models.user import User, UserRole
from app.models.farm import Farm
from app.models.sensor import SensorReading
from app.models.satellite_observation import SatelliteObservation
from app.models.drone_observation import DroneObservation
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.carbon_token import CarbonToken, TokenStatus
from app.models.verification import VerificationRequest, VerificationStatus, RiskLevel
from app.services.mrv_engine import calculate_mrv
from app.schemas.dashboard_schema import (
    FarmDashboardResponse,
    AdminDashboardResponse,
    VerifierDashboardResponse,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _get_farm_or_404(farm_id: int, db: Session) -> Farm:
    farm = db.get(Farm, farm_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm


def _assert_farm_access(farm: Farm, current_user: User) -> None:
    role = current_user.role
    if role in (UserRole.ADMIN, UserRole.VERIFIER):
        return
    if role == UserRole.FARMER and farm.farmer_id == current_user.id:
        return
    if role == UserRole.FPO and farm.fpo_id is not None:
        return
    raise HTTPException(status_code=403, detail="Not authorised to access this farm")


@router.get("/farm/{farm_id}", response_model=FarmDashboardResponse)
def farm_dashboard(
    farm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Aggregated MRV dashboard for a single farm — sensor, satellite, drone,
    carbon reports, and MRV engine output.
    """
    farm = _get_farm_or_404(farm_id, db)
    _assert_farm_access(farm, current_user)

    sensor_readings = (
        db.query(SensorReading).filter(SensorReading.farm_id == farm_id).all()
    )
    satellite_obs = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.farm_id == farm_id)
        .all()
    )
    drone_obs = (
        db.query(DroneObservation).filter(DroneObservation.farm_id == farm_id).all()
    )
    carbon_reports = (
        db.query(CarbonReport).filter(CarbonReport.farm_id == farm_id).all()
    )

    avg_quality = 0.0
    if sensor_readings:
        avg_quality = round(
            sum(r.data_quality_score for r in sensor_readings) / len(sensor_readings), 2
        )

    verified_credits = sum(
        r.estimated_credits
        for r in carbon_reports
        if r.status == ReportStatus.VERIFIED
    )

    # Run MRV engine
    mrv = calculate_mrv(sensor_readings, satellite_obs, drone_obs)

    return FarmDashboardResponse(
        farm_id=farm.id,
        farm_name=farm.farm_name,
        land_area_acres=farm.land_area_acres,
        is_approved=farm.is_approved,
        total_sensor_readings=len(sensor_readings),
        avg_sensor_quality=avg_quality,
        total_satellite_observations=len(satellite_obs),
        total_drone_observations=len(drone_obs),
        total_carbon_reports=len(carbon_reports),
        verified_credits=verified_credits,
        mrv_confidence_score=mrv.confidence_score,
        mrv_consistency_score=mrv.consistency_score,
        mrv_flags=mrv.flags,
    )


@router.get("/admin", response_model=AdminDashboardResponse)
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Platform-wide statistics. ADMIN only."""
    from app.models.user import User as UserModel

    total_farms = db.query(Farm).count()
    approved_farms = db.query(Farm).filter(Farm.is_approved.is_(True)).count()
    total_farmers = db.query(UserModel).filter(UserModel.role == UserRole.FARMER).count()

    all_reports = db.query(CarbonReport).all()
    total_carbon_reports = len(all_reports)
    verified_reports = sum(1 for r in all_reports if r.status == ReportStatus.VERIFIED)
    pending_verification = (
        db.query(VerificationRequest)
        .filter(VerificationRequest.status == VerificationStatus.PENDING)
        .count()
    )

    all_tokens = db.query(CarbonToken).all()
    total_tokens_minted = len(all_tokens)
    total_credits_issued = sum(t.credit_amount for t in all_tokens)

    all_vr = db.query(VerificationRequest).all()
    high_risk_reports = sum(1 for vr in all_vr if vr.risk_level == RiskLevel.HIGH)
    # Critical fraud alerts: MEDIUM risk or higher with risk_score > 80
    critical_fraud_alerts = sum(
        1 for vr in all_vr if vr.risk_score is not None and vr.risk_score > 80
    )

    return AdminDashboardResponse(
        total_farms=total_farms,
        approved_farms=approved_farms,
        total_farmers=total_farmers,
        total_carbon_reports=total_carbon_reports,
        verified_reports=verified_reports,
        pending_verification=pending_verification,
        total_tokens_minted=total_tokens_minted,
        total_credits_issued=total_credits_issued,
        high_risk_reports=high_risk_reports,
        critical_fraud_alerts=critical_fraud_alerts,
    )


@router.get("/verifier", response_model=VerifierDashboardResponse)
def verifier_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verifier workload overview. VERIFIER or ADMIN only."""
    if current_user.role not in (UserRole.VERIFIER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Verifier or Admin access required")

    all_vr = db.query(VerificationRequest).all()
    pending = sum(1 for vr in all_vr if vr.status == VerificationStatus.PENDING)

    today = date.today()
    approved_today = sum(
        1 for vr in all_vr
        if vr.status == VerificationStatus.APPROVED
        and vr.verified_at is not None
        and vr.verified_at.date() == today
    )
    rejected_today = sum(
        1 for vr in all_vr
        if vr.status == VerificationStatus.REJECTED
        and vr.verified_at is not None
        and vr.verified_at.date() == today
    )

    scored = [vr for vr in all_vr if vr.risk_score is not None]
    avg_risk = round(sum(vr.risk_score for vr in scored) / len(scored), 2) if scored else 0.0
    high_risk_count = sum(1 for vr in all_vr if vr.risk_level == RiskLevel.HIGH)

    # Reports with fraud flags: those with risk_score > 70 (proxy for fraud flags)
    reports_with_fraud_flags = sum(
        1 for vr in all_vr if vr.risk_score is not None and vr.risk_score > 70
    )

    return VerifierDashboardResponse(
        pending_verifications=pending,
        approved_today=approved_today,
        rejected_today=rejected_today,
        avg_risk_score=avg_risk,
        high_risk_count=high_risk_count,
        reports_with_fraud_flags=reports_with_fraud_flags,
    )
