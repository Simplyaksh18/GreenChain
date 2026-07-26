from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.farm import Farm, CropCycle
from app.models.sensor import SensorReading, SensorSourceType
from app.schemas.sensor_schema import (
    SimulateRequest, SimulateResponse,
    SensorReadingCreate, SensorReadingResponse, SensorSummaryResponse,
)
from app.services.sensor_simulator import simulate_sensor_readings
from app.services.emission_estimator import estimate_methane

router = APIRouter(prefix="/sensors", tags=["Sensors"])


# ── shared helpers ─────────────────────────────────────────────────────────────

def _require_farm_access(farm: Farm, current_user: User, db: Session):
    """Raise 403 unless user is ADMIN, the farm owner, or the linked FPO."""
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


# ── POST /sensors/readings ─────────────────────────────────────────────────────
@router.post("/readings", response_model=SensorReadingResponse, status_code=status.HTTP_201_CREATED)
def create_manual_reading(
    payload: SensorReadingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a manual sensor reading. FARMER (own farm), FPO (linked), ADMIN."""
    if current_user.role == UserRole.VERIFIER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    farm = _get_farm_or_404(payload.farm_id, db)
    cycle = _get_cycle_or_404(payload.crop_cycle_id, db)

    if cycle.farm_id != farm.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Crop cycle does not belong to the specified farm")

    _require_farm_access(farm, current_user, db)

    # Validate reading_time >= crop cycle start_date
    from datetime import timezone as _tz
    reading_date = payload.reading_time.date() if hasattr(payload.reading_time, "date") else payload.reading_time
    if hasattr(reading_date, "__le__") and reading_date < cycle.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"reading_time cannot be before crop cycle start_date ({cycle.start_date})",
        )

    # Auto-calculate estimated_methane from emission estimator
    methane_result = estimate_methane(
        soil_moisture=payload.soil_moisture,
        water_depth_cm=payload.water_depth_cm,
        temperature_c=payload.temperature_c,
        crop_type=cycle.crop_type,
    )

    reading = SensorReading(
        farm_id=farm.id,
        crop_cycle_id=cycle.id,
        reading_time=payload.reading_time,
        soil_moisture=payload.soil_moisture,
        water_depth_cm=payload.water_depth_cm,
        temperature_c=payload.temperature_c,
        humidity=payload.humidity,
        rainfall_mm=payload.rainfall_mm,
        estimated_methane=methane_result.estimated_methane,
        data_quality_score=payload.data_quality_score,
        source_type=SensorSourceType.MANUAL,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


# ── POST /sensors/simulate ─────────────────────────────────────────────────────
@router.post("/simulate", response_model=SimulateResponse, status_code=status.HTTP_201_CREATED)
def simulate_readings(
    payload: SimulateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Role gate: FARMER, FPO, ADMIN only
    if current_user.role == UserRole.VERIFIER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    farm = _get_farm_or_404(payload.farm_id, db)
    cycle = _get_cycle_or_404(payload.crop_cycle_id, db)

    # Verify cycle belongs to the farm
    if cycle.farm_id != farm.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Crop cycle does not belong to the specified farm",
        )

    _require_farm_access(farm, current_user, db)

    # ── Date realism: cap readings at today ────────────────────────────────────
    today_utc = datetime.now(timezone.utc)
    today_date = today_utc.date()
    cycle_start_date = cycle.start_date

    if cycle_start_date > today_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Crop cycle start date {cycle_start_date} is in the future. "
                "Cannot simulate sensor readings before the cycle begins."
            ),
        )

    # How many days are actually available from cycle start → today?
    available_days = (today_date - cycle_start_date).days + 1
    effective_days = min(payload.number_of_days, available_days)
    capped = effective_days < payload.number_of_days

    # Start simulation from cycle's start date (always in the past or today)
    start_time = datetime(
        cycle_start_date.year, cycle_start_date.month, cycle_start_date.day,
        6, 0, 0, tzinfo=timezone.utc,
    )

    # Generate and persist readings
    simulated = simulate_sensor_readings(
        farm_id=farm.id,
        crop_cycle_id=cycle.id,
        crop_type=cycle.crop_type,
        number_of_days=effective_days,
        start_time=start_time,
    )

    readings = [
        SensorReading(
            farm_id=r.farm_id,
            crop_cycle_id=r.crop_cycle_id,
            reading_time=r.reading_time,
            soil_moisture=r.soil_moisture,
            water_depth_cm=r.water_depth_cm,
            temperature_c=r.temperature_c,
            humidity=r.humidity,
            rainfall_mm=r.rainfall_mm,
            estimated_methane=r.estimated_methane,
            data_quality_score=r.data_quality_score,
            source_type=r.source_type,
        )
        for r in simulated
    ]
    db.bulk_save_objects(readings)
    db.commit()

    return SimulateResponse(
        generated_readings=len(readings),
        farm_id=farm.id,
        crop_cycle_id=cycle.id,
        requested_days=payload.number_of_days,
        capped_at_today=capped,
    )


# ── GET /sensors/farm/{farm_id} ────────────────────────────────────────────────
@router.get("/farm/{farm_id}", response_model=List[SensorReadingResponse])
def get_readings_by_farm(
    farm_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    farm = _get_farm_or_404(farm_id, db)
    _require_farm_access(farm, current_user, db)
    readings = (
        db.query(SensorReading)
        .filter(SensorReading.farm_id == farm_id)
        .order_by(SensorReading.reading_time)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return readings


# ── GET /sensors/crop-cycle/{crop_cycle_id} ───────────────────────────────────
@router.get("/crop-cycle/{crop_cycle_id}", response_model=List[SensorReadingResponse])
def get_readings_by_crop_cycle(
    crop_cycle_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cycle = _get_cycle_or_404(crop_cycle_id, db)
    farm = _get_farm_or_404(cycle.farm_id, db)
    _require_farm_access(farm, current_user, db)
    readings = (
        db.query(SensorReading)
        .filter(SensorReading.crop_cycle_id == crop_cycle_id)
        .order_by(SensorReading.reading_time)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return readings


# ── GET /sensors/summary/{crop_cycle_id} ──────────────────────────────────────
@router.get("/summary/{crop_cycle_id}", response_model=SensorSummaryResponse)
def get_cycle_summary(
    crop_cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cycle = _get_cycle_or_404(crop_cycle_id, db)
    farm = _get_farm_or_404(cycle.farm_id, db)
    _require_farm_access(farm, current_user, db)

    agg = (
        db.query(
            func.count(SensorReading.id).label("total"),
            func.avg(SensorReading.soil_moisture).label("avg_moisture"),
            func.avg(SensorReading.water_depth_cm).label("avg_water"),
            func.avg(SensorReading.temperature_c).label("avg_temp"),
            func.avg(SensorReading.humidity).label("avg_humidity"),
            func.avg(SensorReading.estimated_methane).label("avg_methane"),
            func.avg(SensorReading.data_quality_score).label("avg_quality"),
        )
        .filter(SensorReading.crop_cycle_id == crop_cycle_id)
        .first()
    )

    def _r(v):
        return round(float(v), 4) if v is not None else None

    return SensorSummaryResponse(
        crop_cycle_id=crop_cycle_id,
        total_readings=agg.total or 0,
        avg_soil_moisture=_r(agg.avg_moisture),
        avg_water_depth_cm=_r(agg.avg_water),
        avg_temperature_c=_r(agg.avg_temp),
        avg_humidity=_r(agg.avg_humidity),
        avg_methane=_r(agg.avg_methane),
        avg_data_quality_score=_r(agg.avg_quality),
    )
