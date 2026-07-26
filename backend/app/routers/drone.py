"""
Drone observation router — Phase 7.

POST /drone/simulate  — FARMER(own) / FPO / VERIFIER / ADMIN
GET  /drone/{farm_id} — FARMER(own) / FPO / VERIFIER / ADMIN
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
from app.models.drone_observation import DroneObservation, DroneSource
from app.schemas.drone_schema import (
    DroneObservationCreate,
    DroneSimulateRequest,
    DroneObservationResponse,
    DroneSimulateResponse,
)

router = APIRouter(prefix="/drone", tags=["Drone"])


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


@router.post(
    "/observations",
    response_model=DroneObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_drone_observation(
    body: DroneObservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a manual drone observation. FARMER (own), FPO (linked), ADMIN."""
    if current_user.role == UserRole.VERIFIER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    farm = _get_farm_or_404(body.farm_id, db)
    _assert_farm_access(farm, current_user)

    if body.crop_cycle_id is not None:
        from app.models.farm import CropCycle
        cycle = db.get(CropCycle, body.crop_cycle_id)
        if not cycle or cycle.farm_id != farm.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Crop cycle not found or does not belong to this farm")
        if body.observation_date < cycle.start_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"observation_date cannot be before crop cycle start_date ({cycle.start_date})")

    if body.observation_date < farm.created_at.date():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"observation_date cannot be before farm created_at ({farm.created_at.date()})")

    obs = DroneObservation(
        farm_id=farm.id,
        crop_cycle_id=body.crop_cycle_id,
        observation_date=body.observation_date,
        vegetation_cover_percent=body.vegetation_cover_percent,
        standing_water_percent=body.standing_water_percent,
        anomaly_score=body.anomaly_score,
        image_reference=body.image_reference,
        source=DroneSource.DRONE_MANUAL,
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)
    return DroneObservationResponse.model_validate(obs)


@router.post(
    "/simulate",
    response_model=DroneSimulateResponse,
    status_code=status.HTTP_201_CREATED,
)
def simulate_drone_observations(
    body: DroneSimulateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate synthetic drone observations for a farm."""
    farm = _get_farm_or_404(body.farm_id, db)
    _assert_farm_access(farm, current_user)

    today = datetime.now(timezone.utc).date()
    INTERVAL_DAYS = 7

    # ── Date realism: generate backward from today so all N obs are in the past ─
    # Always anchor last observation to today and go backward.
    # For simulation endpoints, crop cycle start_date is not a constraint on obs dates —
    # it's just used for validation of real manual observations. Here we always use
    # ideal_base so N observations always fit before today, even for recently-started cycles.
    base_date = today - timedelta(days=(body.number_of_observations - 1) * INTERVAL_DAYS)

    created = []
    rng = random.Random(body.farm_id * 777 + body.number_of_observations)

    for i in range(body.number_of_observations):
        obs_date = base_date + timedelta(days=i * INTERVAL_DAYS)
        if obs_date > today:
            break  # Do not generate future observations
        veg_cover = round(rng.uniform(55.0, 90.0), 2)
        water_pct = round(rng.uniform(5.0, 35.0), 2)
        anomaly = round(rng.uniform(0.0, 30.0), 2)

        obs = DroneObservation(
            farm_id=body.farm_id,
            crop_cycle_id=body.crop_cycle_id,
            observation_date=obs_date,
            vegetation_cover_percent=veg_cover,
            standing_water_percent=water_pct,
            anomaly_score=anomaly,
            image_reference=f"drone_farm{body.farm_id}_obs{i+1}.jpg",
        )
        db.add(obs)
        created.append(obs)

    db.commit()
    for obs in created:
        db.refresh(obs)

    return DroneSimulateResponse(
        created=len(created),
        observations=[DroneObservationResponse.model_validate(o) for o in created],
    )


@router.get(
    "/{farm_id}",
    response_model=list[DroneObservationResponse],
)
def list_drone_observations(
    farm_id: int,
    crop_cycle_id: Optional[int] = Query(default=None, description="Filter by crop cycle"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List drone observations for a farm.

    Optional filter: crop_cycle_id
    Pagination: limit (default 100), offset (default 0)
    """
    farm = _get_farm_or_404(farm_id, db)
    _assert_farm_access(farm, current_user)
    q = (
        db.query(DroneObservation)
        .filter(DroneObservation.farm_id == farm_id)
        .order_by(DroneObservation.observation_date)
    )
    if crop_cycle_id is not None:
        q = q.filter(DroneObservation.crop_cycle_id == crop_cycle_id)
    obs = q.offset(offset).limit(limit).all()
    return [DroneObservationResponse.model_validate(o) for o in obs]
