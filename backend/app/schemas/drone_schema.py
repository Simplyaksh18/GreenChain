"""Pydantic schemas for DroneObservation — Phase 7 / 9C."""
from datetime import date, datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DroneObservationCreate(BaseModel):
    """POST /drone/observations — manual entry."""
    farm_id: int
    crop_cycle_id: Optional[int] = None
    observation_date: date
    vegetation_cover_percent: float = Field(ge=0.0, le=100.0)
    standing_water_percent: float = Field(ge=0.0, le=100.0)
    anomaly_score: float = Field(default=0.0, ge=0.0, le=100.0)
    image_reference: Optional[str] = None

    @field_validator("observation_date")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > datetime.now(timezone.utc).date():
            raise ValueError("observation_date cannot be in the future")
        return v


class DroneSimulateRequest(BaseModel):
    farm_id: int
    crop_cycle_id: Optional[int] = None
    number_of_observations: int = Field(default=3, ge=1, le=20)


class DroneObservationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    farm_id: int
    crop_cycle_id: Optional[int]
    observation_date: date
    vegetation_cover_percent: float
    standing_water_percent: float
    anomaly_score: float
    image_reference: Optional[str]
    source: str = "DRONE_SIMULATED"
    created_at: datetime


class DroneSimulateResponse(BaseModel):
    created: int
    observations: list[DroneObservationResponse]
