from pydantic import BaseModel
from typing import Optional


# ── Emission estimate (single reading) ────────────────────────────────────────
class EmissionEstimateRequest(BaseModel):
    soil_moisture: float
    water_depth_cm: float
    temperature_c: float
    crop_type: str


class EmissionEstimateResponse(BaseModel):
    estimated_methane: float
    confidence_score: float
    explanation: str


# ── Baseline / current methane (aggregate from stored readings) ───────────────
class BaselineMethaneResponse(BaseModel):
    crop_cycle_id: int
    baseline_methane: float          # avg of first 7 readings (kg CH4/day)
    readings_used: int


class CurrentMethaneResponse(BaseModel):
    crop_cycle_id: int
    current_methane: float           # avg of latest 7 readings (kg CH4/day)
    readings_used: int
