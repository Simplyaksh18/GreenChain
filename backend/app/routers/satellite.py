"""
Satellite observation router — Phase 7.

POST /satellite/simulate  — FARMER or FPO or ADMIN
GET  /satellite/{farm_id} — FARMER(own) / FPO(linked) / VERIFIER / ADMIN
"""
from datetime import datetime, timedelta, timezone
import random
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.farm import Farm
from app.models.satellite_observation import (
    SatelliteObservation,
    SatelliteSource,
    VegetationHealth,
    FloodRisk,
)
from app.schemas.satellite_schema import (
    SatelliteObservationCreate,
    SatelliteSimulateRequest,
    SatelliteObservationResponse,
    SatelliteSimulateResponse,
)

router = APIRouter(prefix="/satellite", tags=["Satellite"])


def _get_farm_or_404(farm_id: int, db: Session) -> Farm:
    farm = db.get(Farm, farm_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm


def _assert_farm_access(farm: Farm, current_user: User) -> None:
    role = current_user.role
    if role == UserRole.ADMIN:
        return
    if role == UserRole.VERIFIER:
        return
    if role == UserRole.FARMER and farm.farmer_id == current_user.id:
        return
    if role == UserRole.FPO:
        from app.models.fpo import FPOProfile
        # Allow if this farm belongs to their FPO
        if farm.fpo_id is not None:
            return
    raise HTTPException(status_code=403, detail="Not authorised to access this farm")


def _simulate_vegetation_health(ndvi: float) -> VegetationHealth:
    if ndvi >= 0.6:
        return VegetationHealth.EXCELLENT
    if ndvi >= 0.4:
        return VegetationHealth.GOOD
    if ndvi >= 0.2:
        return VegetationHealth.FAIR
    return VegetationHealth.POOR


def _simulate_flood_risk(ndwi: float) -> FloodRisk:
    if ndwi >= 0.5:
        return FloodRisk.HIGH
    if ndwi >= 0.3:
        return FloodRisk.MEDIUM
    if ndwi >= 0.1:
        return FloodRisk.LOW
    return FloodRisk.NONE


@router.post(
    "/observations",
    response_model=SatelliteObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_satellite_observation(
    body: SatelliteObservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a manual satellite observation. FARMER (own), FPO (linked), ADMIN."""
    if current_user.role == UserRole.VERIFIER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    farm = _get_farm_or_404(body.farm_id, db)
    _assert_farm_access(farm, current_user)

    # Validate crop_cycle if provided
    if body.crop_cycle_id is not None:
        from app.models.farm import CropCycle
        cycle = db.get(CropCycle, body.crop_cycle_id)
        if not cycle or cycle.farm_id != farm.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Crop cycle not found or does not belong to this farm")
        if body.observation_date < cycle.start_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"observation_date cannot be before crop cycle start_date ({cycle.start_date})")

    # Validate not before farm creation date
    if body.observation_date < farm.created_at.date():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"observation_date cannot be before farm created_at ({farm.created_at.date()})")

    obs = SatelliteObservation(
        farm_id=farm.id,
        crop_cycle_id=body.crop_cycle_id,
        observation_date=body.observation_date,
        ndvi=body.ndvi,
        ndwi=body.ndwi,
        vegetation_health=body.vegetation_health,
        flood_risk=body.flood_risk,
        cloud_cover_percent=body.cloud_cover_percent,
        source=SatelliteSource.SATELLITE_MANUAL,
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)
    return SatelliteObservationResponse.model_validate(obs)


@router.post(
    "/simulate",
    response_model=SatelliteSimulateResponse,
    status_code=status.HTTP_201_CREATED,
)
def simulate_satellite_observations(
    body: SatelliteSimulateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate synthetic satellite observations for a farm.
    Available to FARMER (own farm), FPO, VERIFIER, ADMIN.
    """
    farm = _get_farm_or_404(body.farm_id, db)
    _assert_farm_access(farm, current_user)

    today = datetime.now(timezone.utc).date()
    INTERVAL_DAYS = 5

    # ── Date realism: generate backward from today so all N obs are in the past ─
    # Always anchor last observation to today and go backward.
    # Simulation endpoints don't enforce cycle.start_date as a date floor — that
    # constraint applies only to manual real observations.
    base_date = today - timedelta(days=(body.number_of_observations - 1) * INTERVAL_DAYS)

    created = []
    rng = random.Random(body.farm_id * 1000 + body.number_of_observations)

    for i in range(body.number_of_observations):
        obs_date = base_date + timedelta(days=i * INTERVAL_DAYS)
        if obs_date > today:
            break  # Do not generate future observations
        ndvi = round(rng.uniform(0.35, 0.75), 4)
        ndwi = round(rng.uniform(-0.05, 0.45), 4)
        cloud = round(rng.uniform(0.0, 30.0), 1)

        obs = SatelliteObservation(
            farm_id=body.farm_id,
            crop_cycle_id=body.crop_cycle_id,
            observation_date=obs_date,
            ndvi=ndvi,
            ndwi=ndwi,
            vegetation_health=_simulate_vegetation_health(ndvi),
            flood_risk=_simulate_flood_risk(ndwi),
            cloud_cover_percent=cloud,
            source=SatelliteSource.SATELLITE_SIMULATED,
        )
        db.add(obs)
        created.append(obs)

    db.commit()
    for obs in created:
        db.refresh(obs)

    return SatelliteSimulateResponse(
        created=len(created),
        observations=[SatelliteObservationResponse.model_validate(o) for o in created],
    )


@router.get(
    "/{farm_id}",
    response_model=list[SatelliteObservationResponse],
)
def list_satellite_observations(
    farm_id: int,
    crop_cycle_id: Optional[int] = Query(default=None, description="Filter by crop cycle"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List satellite observations for a farm.

    Optional filter: crop_cycle_id
    Pagination: limit (default 100), offset (default 0)
    """
    farm = _get_farm_or_404(farm_id, db)
    _assert_farm_access(farm, current_user)
    q = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.farm_id == farm_id)
        .order_by(SatelliteObservation.observation_date)
    )
    if crop_cycle_id is not None:
        q = q.filter(SatelliteObservation.crop_cycle_id == crop_cycle_id)
    obs = q.offset(offset).limit(limit).all()
    return [SatelliteObservationResponse.model_validate(o) for o in obs]
