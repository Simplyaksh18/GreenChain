"""
Mobile API router — Phase 8.

GET /mobile/dashboard  — role-aware summary dashboard
"""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.farm import Farm, CropCycle, CropCycleStatus
from app.models.sensor import SensorReading
from app.models.satellite_observation import SatelliteObservation
from app.models.drone_observation import DroneObservation
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.carbon_token import CarbonToken, TokenStatus
from app.models.verification import VerificationRequest, VerificationStatus, RiskLevel
from app.models.fpo import FPOProfile
from app.services.mrv_engine import calculate_mrv
from app.schemas.mobile_schema import (
    MobileDashboardResponse,
    FarmerDashboardData,
    FpoDashboardData,
    VerifierDashboardData,
    AdminDashboardData,
)
from app.utils.response import ok

router = APIRouter(prefix="/mobile", tags=["Mobile"])


def _farmer_dashboard(user: User, db: Session) -> dict:
    farms = db.query(Farm).filter(Farm.farmer_id == user.id).all()
    farm_ids = [f.id for f in farms]

    approved_farms = sum(1 for f in farms if f.is_approved)

    active_cycles = 0
    if farm_ids:
        active_cycles = (
            db.query(CropCycle)
            .filter(
                CropCycle.farm_id.in_(farm_ids),
                CropCycle.status == CropCycleStatus.ACTIVE,
            )
            .count()
        )

    total_readings = 0
    avg_quality = 0.0
    if farm_ids:
        readings = (
            db.query(SensorReading)
            .filter(SensorReading.farm_id.in_(farm_ids))
            .all()
        )
        total_readings = len(readings)
        if readings:
            avg_quality = round(
                sum(r.data_quality_score for r in readings) / total_readings, 2
            )

    reports = []
    if farm_ids:
        reports = db.query(CarbonReport).filter(CarbonReport.farm_id.in_(farm_ids)).all()

    verified_reports = sum(1 for r in reports if r.status == ReportStatus.VERIFIED)

    tokens = (
        db.query(CarbonToken).filter(CarbonToken.farmer_id == user.id).all()
    )
    total_credits = sum(t.credit_amount for t in tokens)

    # Latest MRV confidence: use the first farm that has data
    latest_mrv_confidence = None
    if farm_ids:
        sat_obs = (
            db.query(SatelliteObservation)
            .filter(SatelliteObservation.farm_id.in_(farm_ids))
            .all()
        )
        drone_obs = (
            db.query(DroneObservation)
            .filter(DroneObservation.farm_id.in_(farm_ids))
            .all()
        )
        all_readings = (
            db.query(SensorReading)
            .filter(SensorReading.farm_id.in_(farm_ids))
            .all()
        )
        if all_readings or sat_obs or drone_obs:
            mrv = calculate_mrv(all_readings, sat_obs, drone_obs)
            latest_mrv_confidence = mrv.confidence_score

    data = FarmerDashboardData(
        my_farms_count=len(farms),
        approved_farms_count=approved_farms,
        active_crop_cycles=active_cycles,
        total_sensor_readings=total_readings,
        avg_sensor_quality=avg_quality,
        total_carbon_reports=len(reports),
        verified_reports=verified_reports,
        token_count=len(tokens),
        total_credits=total_credits,
        latest_mrv_confidence=latest_mrv_confidence,
    )
    return data.model_dump()


def _fpo_dashboard(user: User, db: Session) -> dict:
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == user.id).first()
    if not profile:
        return FpoDashboardData(
            linked_farms_count=0,
            approved_linked_farms=0,
            farmers_count=0,
            pending_reports=0,
            high_risk_farms=0,
        ).model_dump()

    farms = db.query(Farm).filter(Farm.fpo_id == profile.id).all()
    farm_ids = [f.id for f in farms]
    approved = sum(1 for f in farms if f.is_approved)

    farmer_ids = list({f.farmer_id for f in farms})

    pending_reports = 0
    if farm_ids:
        pending_reports = (
            db.query(CarbonReport)
            .filter(
                CarbonReport.farm_id.in_(farm_ids),
                CarbonReport.status == ReportStatus.SUBMITTED,
            )
            .count()
        )

    # High-risk farms: distinct farm IDs that have at least one HIGH-risk VR
    high_risk_farms = 0
    if farm_ids:
        high_risk_report_ids = {
            vr.carbon_report_id
            for vr in db.query(VerificationRequest)
            .filter(VerificationRequest.risk_level == RiskLevel.HIGH)
            .all()
        }
        if high_risk_report_ids:
            affected_farm_ids = {
                r.farm_id
                for r in db.query(CarbonReport)
                .filter(
                    CarbonReport.farm_id.in_(farm_ids),
                    CarbonReport.id.in_(high_risk_report_ids),
                )
                .all()
            }
            high_risk_farms = len(affected_farm_ids)

    data = FpoDashboardData(
        linked_farms_count=len(farms),
        approved_linked_farms=approved,
        farmers_count=len(farmer_ids),
        pending_reports=pending_reports,
        high_risk_farms=high_risk_farms,
    )
    return data.model_dump()


def _verifier_dashboard(user: User, db: Session) -> dict:
    today = datetime.now(timezone.utc).date()
    all_vr = db.query(VerificationRequest).all()
    pending = sum(1 for vr in all_vr if vr.status == VerificationStatus.PENDING)
    high_risk = sum(1 for vr in all_vr if vr.risk_level == RiskLevel.HIGH)

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

    data = VerifierDashboardData(
        pending_verifications=pending,
        high_risk_reports=high_risk,
        approved_today=approved_today,
        rejected_today=rejected_today,
    )
    return data.model_dump()


def _admin_dashboard(user: User, db: Session) -> dict:
    from app.models.user import User as UserModel
    total_farms = db.query(Farm).count()
    total_users = db.query(UserModel).count()
    all_reports = db.query(CarbonReport).all()
    total_reports = len(all_reports)
    verified_reports = sum(1 for r in all_reports if r.status == ReportStatus.VERIFIED)
    all_tokens = db.query(CarbonToken).all()
    total_tokens = len(all_tokens)
    total_credits = sum(t.credit_amount for t in all_tokens)
    all_vr = db.query(VerificationRequest).all()
    high_risk_reports = sum(1 for vr in all_vr if vr.risk_level == RiskLevel.HIGH)

    data = AdminDashboardData(
        total_farms=total_farms,
        total_users=total_users,
        total_reports=total_reports,
        verified_reports=verified_reports,
        total_tokens=total_tokens,
        total_credits=float(total_credits),
        high_risk_reports=high_risk_reports,
    )
    return data.model_dump()


@router.get("/dashboard")
def mobile_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Role-aware mobile dashboard summary.
    Returns a standard response envelope with role-specific data.
    """
    role = current_user.role

    if role == UserRole.FARMER:
        data = _farmer_dashboard(current_user, db)
    elif role == UserRole.FPO:
        data = _fpo_dashboard(current_user, db)
    elif role == UserRole.VERIFIER:
        data = _verifier_dashboard(current_user, db)
    else:  # ADMIN
        data = _admin_dashboard(current_user, db)

    return ok(
        data={"role": role.value, "data": data},
        message=f"Dashboard loaded for {role.value}",
    )
