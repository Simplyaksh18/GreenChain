from datetime import date, datetime
import json
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, field_validator, model_validator
from app.models.farm import CropCycleStatus, FarmStatus


# ── GeoJSON storage helpers ───────────────────────────────────────────────────
# The DB column farm_boundary_geojson is Text (string).
# API responses always return a dict (GeoJSON object), never a raw JSON string.
# These two helpers are the single source of truth for that conversion.

def normalize_geojson_for_storage(value: Union[str, Dict[str, Any], None]) -> Optional[str]:
    """
    Coerce incoming value to a canonical JSON string for DB storage.
    Accepts:
      - dict  → json.dumps(dict)
      - str   → parse, validate JSON, re-serialise to canonical form
      - None  → None
    Raises ValueError on invalid JSON string.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return json.dumps(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"farm_boundary_geojson is not valid JSON: {exc}") from exc
        return json.dumps(parsed)   # canonical form
    raise ValueError(f"Unsupported type for farm_boundary_geojson: {type(value)}")


def parse_geojson_from_storage(value: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Parse DB Text value → Python dict for API responses.
    Returns None (not a 500) if the stored value is missing or invalid JSON.

    Handles three cases:
      - None / falsy  → None
      - dict          → returned directly (SQLAlchemy may already deserialise)
      - str           → json.loads() then validate it is a dict
    """
    if not value:
        return None
    if isinstance(value, dict):
        return value   # already a Python dict — return directly
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
        return None   # unexpected non-object JSON
    except (json.JSONDecodeError, TypeError):
        return None


# ─────────────────────────────────────────
# Farm schemas
# ─────────────────────────────────────────

class FarmCreate(BaseModel):
    farm_name: str
    land_area_acres: float
    latitude: float
    longitude: float
    village: str
    district: str
    state: str
    soil_type: str
    water_source: str
    fpo_id: Optional[int] = None

    @field_validator("land_area_acres")
    @classmethod
    def area_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("land_area_acres must be greater than 0")
        return v

    @field_validator("latitude")
    @classmethod
    def lat_range(cls, v: float) -> float:
        if not (-90 <= v <= 90):
            raise ValueError("latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def lon_range(cls, v: float) -> float:
        if not (-180 <= v <= 180):
            raise ValueError("longitude must be between -180 and 180")
        return v


class FarmResponse(BaseModel):
    id: int
    farmer_id: int
    fpo_id: Optional[int]
    farm_name: str
    land_area_acres: float
    latitude: float
    longitude: float
    village: str
    district: str
    state: str
    soil_type: str
    water_source: str
    is_approved: bool
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    # Phase 11 lifecycle
    farm_status: FarmStatus = FarmStatus.DRAFT
    approved_at: Optional[datetime] = None
    approved_by: Optional[int] = None
    archived_at: Optional[datetime] = None
    archive_reason: Optional[str] = None
    # Phase 11 GIS — response always returns a dict, never a raw JSON string
    farm_boundary_geojson: Optional[Dict[str, Any]] = None
    boundary_area_hectares: Optional[float] = None
    boundary_area_acres: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("farm_boundary_geojson", mode="before")
    @classmethod
    def _parse_boundary(cls, v: Any) -> Optional[Dict[str, Any]]:
        """Accept string (from DB Text column) or dict; always return dict or None."""
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            return parse_geojson_from_storage(v)
        return None


class FarmBoundaryUpdate(BaseModel):
    """
    PATCH /farms/{id}/boundary request schema.
    Accepts farm_boundary_geojson as either:
      - a GeoJSON dict  (preferred — sent by mobile as a parsed object)
      - a JSON string   (legacy / backward-compatible)
    Internally normalised to a canonical JSON string before DB storage.
    """
    farm_boundary_geojson: Union[str, Dict[str, Any]]
    boundary_area_hectares: Optional[float] = None
    boundary_area_acres: Optional[float] = None

    @field_validator("farm_boundary_geojson", mode="before")
    @classmethod
    def _coerce_geojson(cls, v: Any) -> str:
        """Always store as a canonical JSON string regardless of input type."""
        return normalize_geojson_for_storage(v)  # raises ValueError → 422 on bad JSON


class FarmBoundaryResponse(BaseModel):
    """
    Response schema for boundary endpoints (PATCH /farms/{id}/boundary and
    GET /farms/{id}/boundary).

    farm_boundary_geojson: parsed GeoJSON dict, never a raw JSON string.
    boundary: same value — convenience alias so mobile can use either field name.
    has_boundary: True when a boundary polygon is saved for this farm.
    """
    farm_id: int
    farm_name: str
    farm_boundary_geojson: Optional[Dict[str, Any]] = None
    # Convenience alias — same value as farm_boundary_geojson
    boundary: Optional[Dict[str, Any]] = None
    has_boundary: bool = False
    boundary_area_hectares: Optional[float] = None
    boundary_area_acres: Optional[float] = None

    model_config = {"from_attributes": True}


class ArchiveFarmRequest(BaseModel):
    reason: Optional[str] = None


class SuspendFarmRequest(BaseModel):
    reason: Optional[str] = None


# ─────────────────────────────────────────
# Crop-cycle schemas
# ─────────────────────────────────────────

class CropCycleCreate(BaseModel):
    crop_type: str
    season: str
    start_date: date
    end_date: Optional[date] = None
    baseline_method: str
    reduction_practice: str


class CropCycleUpdate(BaseModel):
    """PATCH /farms/{farm_id}/crop-cycles/{cycle_id} — all fields optional."""
    crop_type: Optional[str] = None
    season: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    baseline_method: Optional[str] = None
    reduction_practice: Optional[str] = None
    status: Optional[CropCycleStatus] = None

    @model_validator(mode="after")
    def validate_dates(self) -> "CropCycleUpdate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self

    @field_validator("crop_type", "season", "baseline_method", "reduction_practice", mode="before")
    @classmethod
    def no_empty_string(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() == "":
            raise ValueError("Field cannot be empty")
        return v


class HarvestCropCycleRequest(BaseModel):
    harvest_date: date
    yield_quantity: Optional[float] = None
    yield_unit: Optional[str] = None     # "tonnes" | "quintals" | "kg"
    end_date: Optional[date] = None      # if not set, defaults to harvest_date


class CloseCropCycleRequest(BaseModel):
    closed_notes: Optional[str] = None


class CropCycleResponse(BaseModel):
    id: int
    farm_id: int
    crop_type: str
    season: str
    start_date: date
    end_date: Optional[date]
    baseline_method: str
    reduction_practice: str
    status: CropCycleStatus
    # Phase 11 lifecycle
    harvest_date: Optional[date] = None
    closed_at: Optional[datetime] = None
    yield_quantity: Optional[float] = None
    yield_unit: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
