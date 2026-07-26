"""
Carbon Report Detail Router — Phase 11

GET /carbon-reports/{report_id}/detail

Returns a comprehensive report detail including:
- Farm information
- Crop cycle information
- MRV summary (sensor, satellite, drone counts + quality)
- Methane calculations (step by step)
- CO2e calculations
- Credit calculations
- Eligibility explanation
- Verification history
- Blockchain history (hashes truncated for display)
"""
from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.farm import Farm
from app.models.farm import CropCycle
from app.models.carbon_report import CarbonReport
from app.models.sensor import SensorReading
from app.models.satellite_observation import SatelliteObservation
from app.models.drone_observation import DroneObservation
from app.models.evidence import EvidenceFile
from app.models.verification import VerificationRequest
from app.models.blockchain_transaction import BlockchainTransaction
from app.models.carbon_token import CarbonToken
from app.services.credit_eligibility import explain_eligibility

router = APIRouter(prefix="/carbon-reports", tags=["Carbon Report Detail"])


def _truncate_hash(h: str | None, prefix: int = 6, suffix: int = 5) -> str | None:
    """Return '9eefec...41b5b' style shortened hash. Returns None if input is None."""
    if not h:
        return None
    h = h.strip()
    if len(h) <= prefix + suffix + 3:
        return h
    return f"{h[:prefix]}...{h[-suffix:]}"


def _assert_view_access(farm: Farm, current_user: User, db: Session):
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


@router.get("/{report_id}/detail")
def get_report_detail(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Full carbon report detail with MRV evidence, calculations, eligibility,
    verification history, and blockchain history.
    Hash values are truncated (9eefec...41b5b) — full hashes never exposed.
    """
    report = db.query(CarbonReport).filter(CarbonReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carbon report not found")

    farm = db.query(Farm).filter(Farm.id == report.farm_id).first()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    _assert_view_access(farm, current_user, db)

    cycle = db.query(CropCycle).filter(CropCycle.id == report.crop_cycle_id).first()

    # ── FPO info ──────────────────────────────────────────────────────────────
    fpo_profile = db.query(FPOProfile).filter(FPOProfile.id == farm.fpo_id).first() if farm.fpo_id else None

    # ── MRV Evidence ──────────────────────────────────────────────────────────
    cycle_id = report.crop_cycle_id

    sensor_count = db.query(func.count(SensorReading.id)).filter(
        SensorReading.crop_cycle_id == cycle_id
    ).scalar() or 0

    avg_quality = float(db.query(func.avg(SensorReading.data_quality_score)).filter(
        SensorReading.crop_cycle_id == cycle_id
    ).scalar() or 0.0)

    satellite_count = db.query(func.count(SatelliteObservation.id)).filter(
        SatelliteObservation.crop_cycle_id == cycle_id
    ).scalar() or 0

    drone_count = db.query(func.count(DroneObservation.id)).filter(
        DroneObservation.crop_cycle_id == cycle_id
    ).scalar() or 0

    evidence_count = db.query(func.count(EvidenceFile.id)).filter(
        EvidenceFile.crop_cycle_id == cycle_id
    ).scalar() or 0

    # ── Verification History ──────────────────────────────────────────────────
    verifications = db.query(VerificationRequest).filter(
        VerificationRequest.carbon_report_id == report_id
    ).order_by(VerificationRequest.created_at.asc()).all()

    verifier_names = {}
    for vr in verifications:
        if vr.verifier_id and vr.verifier_id not in verifier_names:
            v = db.query(User).filter(User.id == vr.verifier_id).first()
            verifier_names[vr.verifier_id] = v.name if v else None

    # ── Blockchain History ────────────────────────────────────────────────────
    txns = db.query(BlockchainTransaction).filter(
        BlockchainTransaction.carbon_report_id == report_id
    ).order_by(BlockchainTransaction.created_at.asc()).all()

    token = db.query(CarbonToken).filter(
        CarbonToken.carbon_report_id == report_id
    ).first()

    # ── Eligibility ───────────────────────────────────────────────────────────
    eligibility = explain_eligibility(
        baseline_methane_kg=report.baseline_methane_kg,
        current_methane_kg=report.current_methane_kg,
        methane_reduction_kg=report.methane_reduction_kg,
        co2e_reduction_tonnes=report.co2e_reduction_tonnes,
        estimated_credits=report.estimated_credits,
    )

    return {
        # ── Report core ───────────────────────────────────────────────────────
        "report": {
            "id": report.id,
            "status": report.status,
            "report_hash": _truncate_hash(report.report_hash),
            "created_at": report.created_at,
        },

        # ── Farm information ──────────────────────────────────────────────────
        "farm": {
            "id": farm.id,
            "farm_name": farm.farm_name,
            "village": farm.village,
            "district": farm.district,
            "state": farm.state,
            "land_area_acres": farm.land_area_acres,
            "latitude": farm.latitude,
            "longitude": farm.longitude,
            "soil_type": farm.soil_type,
            "water_source": farm.water_source,
            "is_approved": farm.is_approved,
            "farm_status": farm.farm_status,
        },

        # ── FPO information ───────────────────────────────────────────────────
        "fpo": {
            "id": fpo_profile.id if fpo_profile else None,
            "organization_name": fpo_profile.organization_name if fpo_profile else None,
        } if fpo_profile else None,

        # ── Crop information ──────────────────────────────────────────────────
        "crop_cycle": {
            "id": cycle.id if cycle else None,
            "crop_type": cycle.crop_type if cycle else None,
            "season": cycle.season if cycle else None,
            "start_date": cycle.start_date if cycle else None,
            "end_date": cycle.end_date if cycle else None,
            "harvest_date": cycle.harvest_date if cycle else None,
            "baseline_method": cycle.baseline_method if cycle else None,
            "reduction_practice": cycle.reduction_practice if cycle else None,
            "status": cycle.status if cycle else None,
            "yield_quantity": cycle.yield_quantity if cycle else None,
            "yield_unit": cycle.yield_unit if cycle else None,
        } if cycle else None,

        # ── MRV Summary ───────────────────────────────────────────────────────
        "mrv_summary": {
            "sensor_count": sensor_count,
            "avg_sensor_quality": round(avg_quality, 2) if sensor_count > 0 else None,
            "satellite_count": satellite_count,
            "drone_count": drone_count,
            "evidence_file_count": evidence_count,
        },

        # ── Methane & CO2e Calculations ───────────────────────────────────────
        "calculations": {
            "baseline_methane_kg": round(report.baseline_methane_kg, 4),
            "current_methane_kg": round(report.current_methane_kg, 4),
            "methane_reduction_kg": round(report.methane_reduction_kg, 4),
            "co2e_reduction_tonnes": round(report.co2e_reduction_tonnes, 6),
            "gwp_factor_used": 27.2,
            "formula": "(baseline - current) x 27.2 / 1000 = tCO2e",
            "estimated_credits": report.estimated_credits,
        },

        # ── Methane Audit Diagnostics (Phase 13) ──────────────────────────────
        "methane_diagnostics": {
            "baseline_source": "Sensor-derived average methane emission for crop cycle",
            "current_source": "Sensor-derived average methane emission for crop cycle",
            "formula": "(baseline_methane_kg - current_methane_kg) × GWP / 1000 = tCO₂e",
            "gwp_factor": 27.2,
            "co2e_conversion": "methane_reduction_kg × 27.2 / 1000",
            "credits_formula": "floor(co2e_tonnes) when co2e_tonnes ≥ 1.0",
            "input_sensor_count": sensor_count,
            "sensor_quality_average": round(avg_quality, 2) if sensor_count > 0 else None,
            "satellite_observation_count": satellite_count,
            "drone_observation_count": drone_count,
            "methodology": "IPCC 2006 Tier 1 — LinearEmissionEstimator v1",
        },

        # ── Credit Eligibility ────────────────────────────────────────────────
        "eligibility": {
            "eligible": eligibility.eligible,
            "reason": eligibility.reason,
            "current": eligibility.current_co2e,
            "required": eligibility.required_co2e,
            "gap_methane_kg": eligibility.gap_methane_kg,
            "steps": eligibility.steps,
        },

        # ── Verification History ──────────────────────────────────────────────
        "verification_history": [
            {
                "id": vr.id,
                "status": vr.status,
                "risk_score": vr.risk_score,
                "risk_level": vr.risk_level,
                "recommendation": vr.recommendation,
                "remarks": vr.remarks,
                "verifier_name": verifier_names.get(vr.verifier_id),
                "verified_at": vr.verified_at,
                "created_at": vr.created_at,
            }
            for vr in verifications
        ],

        # ── Blockchain History ────────────────────────────────────────────────
        "blockchain_history": [
            {
                "id": tx.id,
                "tx_type": tx.tx_type,
                "tx_hash": _truncate_hash(tx.tx_hash),
                "status": tx.status,
                "created_at": tx.created_at,
            }
            for tx in txns
        ],

        # ── Token ─────────────────────────────────────────────────────────────
        "token": {
            "id": token.id,
            "token_id": token.token_id,
            "token_standard": token.token_standard,
            "credit_amount": token.credit_amount,
            "status": token.status,
            "minted_tx_hash": _truncate_hash(token.minted_tx_hash),
            "minted_at": token.minted_at,
            "is_certificate": token.is_certificate,
        } if token else None,
    }
