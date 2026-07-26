from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.farm import Farm, CropCycle
from app.models.sensor import SensorReading
from app.schemas.carbon_schema import (
    EmissionEstimateRequest, EmissionEstimateResponse,
    BaselineMethaneResponse, CurrentMethaneResponse,
)
from app.services.emission_estimator import estimate_methane, CROP_FACTORS

router = APIRouter(prefix="/emissions", tags=["Emissions"])

SUPPORTED_CROPS = set(CROP_FACTORS.keys())


def _require_farm_access(farm: Farm, current_user: User, db: Session):
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


# ── POST /emissions/estimate ──────────────────────────────────────────────────
@router.post("/estimate", response_model=EmissionEstimateResponse)
def estimate_emission(
    payload: EmissionEstimateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    One-shot methane estimate from raw sensor values.
    Any authenticated user may call this.
    """
    result = estimate_methane(
        soil_moisture=payload.soil_moisture,
        water_depth_cm=payload.water_depth_cm,
        temperature_c=payload.temperature_c,
        crop_type=payload.crop_type,
    )
    return EmissionEstimateResponse(
        estimated_methane=result.estimated_methane,
        confidence_score=result.confidence_score,
        explanation=result.explanation,
    )


# ── POST /emissions/baseline/{crop_cycle_id} ──────────────────────────────────
@router.post("/baseline/{crop_cycle_id}", response_model=BaselineMethaneResponse)
def get_baseline_methane(
    crop_cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Baseline methane = average of the **first 7** sensor readings for this
    crop cycle (ordered by reading_time ascending).
    """
    cycle = db.query(CropCycle).filter(CropCycle.id == crop_cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop cycle not found")

    farm = db.query(Farm).filter(Farm.id == cycle.farm_id).first()
    _require_farm_access(farm, current_user, db)

    readings = (
        db.query(SensorReading)
        .filter(SensorReading.crop_cycle_id == crop_cycle_id)
        .order_by(SensorReading.reading_time.asc())
        .limit(7)
        .all()
    )
    if not readings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sensor readings found for this crop cycle. Run simulation first.",
        )

    baseline = round(sum(r.estimated_methane for r in readings) / len(readings), 6)
    return BaselineMethaneResponse(
        crop_cycle_id=crop_cycle_id,
        baseline_methane=baseline,
        readings_used=len(readings),
    )


# ── POST /emissions/current/{crop_cycle_id} ───────────────────────────────────
@router.post("/current/{crop_cycle_id}", response_model=CurrentMethaneResponse)
def get_current_methane(
    crop_cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Current methane = average of the **latest 7** sensor readings (ordered by
    reading_time descending, so newest first).
    """
    cycle = db.query(CropCycle).filter(CropCycle.id == crop_cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop cycle not found")

    farm = db.query(Farm).filter(Farm.id == cycle.farm_id).first()
    _require_farm_access(farm, current_user, db)

    readings = (
        db.query(SensorReading)
        .filter(SensorReading.crop_cycle_id == crop_cycle_id)
        .order_by(SensorReading.reading_time.desc())
        .limit(7)
        .all()
    )
    if not readings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sensor readings found for this crop cycle. Run simulation first.",
        )

    current = round(sum(r.estimated_methane for r in readings) / len(readings), 6)
    return CurrentMethaneResponse(
        crop_cycle_id=crop_cycle_id,
        current_methane=current,
        readings_used=len(readings),
    )
