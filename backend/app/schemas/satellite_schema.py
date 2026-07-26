"""Pydantic schemas for SatelliteObservation — Phase 7 / 9C."""
from datetime import date, datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.satellite_observation import SatelliteSource, VegetationHealth, FloodRisk


class SatelliteObservationCreate(BaseModel):
    """POST /satellite/observations — manual entry."""
    farm_id: int
    crop_cycle_id: Optional[int] = None
    observation_date: date
    ndvi: float = Field(ge=-1.0, le=1.0)
    ndwi: float = Field(ge=-1.0, le=1.0)
    vegetation_health: VegetationHealth
    flood_risk: FloodRisk = FloodRisk.NONE
    cloud_cover_percent: float = Field(default=0.0, ge=0.0, le=100.0)

    @field_validator("observation_date")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > datetime.now(timezone.utc).date():
            raise ValueError("observation_date cannot be in the future")
        return v


class SatelliteSimulateRequest(BaseModel):
    farm_id: int
    crop_cycle_id: Optional[int] = None
    number_of_observations: int = Field(default=5, ge=1, le=30)


class SatelliteObservationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    farm_id: int
    crop_cycle_id: Optional[int]
    observation_date: date
    ndvi: float
    ndwi: float
    vegetation_health: VegetationHealth
    flood_risk: FloodRisk
    cloud_cover_percent: float
    source: str  # String to accommodate extended enum values
    created_at: datetime


class SatelliteSimulateResponse(BaseModel):
    created: int
    observations: list[SatelliteObservationResponse]
