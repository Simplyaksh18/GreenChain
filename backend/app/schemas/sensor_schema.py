from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, field_validator
from app.models.sensor import SensorSourceType


# ── Manual sensor reading create ───────────────────────────────────────────────
class SensorReadingCreate(BaseModel):
    farm_id: int
    crop_cycle_id: int
    reading_time: datetime
    soil_moisture: float        # 0–100
    water_depth_cm: float       # 0–30
    temperature_c: float        # 15–45
    humidity: float             # 20–100
    rainfall_mm: float          # 0–100
    data_quality_score: float   # 0–100

    @field_validator("reading_time")
    @classmethod
    def not_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v > datetime.now(timezone.utc):
            raise ValueError("reading_time cannot be in the future")
        return v

    @field_validator("soil_moisture")
    @classmethod
    def soil_moisture_range(cls, v: float) -> float:
        if not (0 <= v <= 100):
            raise ValueError("soil_moisture must be 0–100")
        return v

    @field_validator("water_depth_cm")
    @classmethod
    def water_depth_range(cls, v: float) -> float:
        if not (0 <= v <= 30):
            raise ValueError("water_depth_cm must be 0–30")
        return v

    @field_validator("temperature_c")
    @classmethod
    def temperature_range(cls, v: float) -> float:
        if not (15 <= v <= 45):
            raise ValueError("temperature_c must be 15–45")
        return v

    @field_validator("humidity")
    @classmethod
    def humidity_range(cls, v: float) -> float:
        if not (20 <= v <= 100):
            raise ValueError("humidity must be 20–100")
        return v

    @field_validator("rainfall_mm")
    @classmethod
    def rainfall_range(cls, v: float) -> float:
        if not (0 <= v <= 100):
            raise ValueError("rainfall_mm must be 0–100")
        return v

    @field_validator("data_quality_score")
    @classmethod
    def quality_range(cls, v: float) -> float:
        if not (0 <= v <= 100):
            raise ValueError("data_quality_score must be 0–100")
        return v


# ── Sensor reading response ────────────────────────────────────────────────────
class SensorReadingResponse(BaseModel):
    id: int
    farm_id: int
    crop_cycle_id: int
    reading_time: datetime
    soil_moisture: float
    water_depth_cm: float
    temperature_c: float
    humidity: float
    rainfall_mm: float
    estimated_methane: float
    data_quality_score: float
    source_type: SensorSourceType
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Simulate request/response ─────────────────────────────────────────────────
class SimulateRequest(BaseModel):
    farm_id: int
    crop_cycle_id: int
    number_of_days: int

    @field_validator("number_of_days")
    @classmethod
    def days_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("number_of_days must be greater than 0")
        if v > 365:
            raise ValueError("number_of_days cannot exceed 365")
        return v


class SimulateResponse(BaseModel):
    generated_readings: int
    farm_id: int
    crop_cycle_id: int
    # Date-realism fields (Phase 9B+)
    requested_days: Optional[int] = None
    capped_at_today: bool = False


# ── Summary ───────────────────────────────────────────────────────────────────
class SensorSummaryResponse(BaseModel):
    crop_cycle_id: int
    total_readings: int
    avg_soil_moisture: Optional[float]
    avg_water_depth_cm: Optional[float]
    avg_temperature_c: Optional[float]
    avg_humidity: Optional[float]
    avg_methane: Optional[float]
    avg_data_quality_score: Optional[float]
