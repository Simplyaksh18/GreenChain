"""
GIS Router — Phase 12

Endpoints:
  GET  /gis/providers/status              — all roles — configuration state
  GET  /gis/providers/health              — ADMIN only — live connectivity check
  GET  /gis/farms/{farm_id}/boundary      — all roles — farm boundary (alias)
  GET  /gis/farms/{farm_id}/map-data      — all roles — marker + boundary + latest satellite summary
  POST /gis/satellite/search              — all roles — search scenes via provider
  POST /gis/satellite/indices             — all roles — NDVI/NDWI for a farm+period

Boundary save uses the existing PATCH /farms/{farm_id}/boundary endpoint
(already implemented in farms.py) — no duplication.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.farm import Farm
from app.routers.farms import _get_farm_or_404, _assert_farm_access
from app.schemas.farm_schema import (
    normalize_geojson_for_storage, parse_geojson_from_storage,
)
from app.services.gis.gis_service import get_gis_service
from app.services.gis.geometry_utils import (
    validate_polygon_geojson, compute_polygon_areas,
    GeoJSONValidationError, geojson_to_bbox, point_geojson,
)

router = APIRouter(prefix="/gis", tags=["GIS"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class SatelliteSearchRequest(BaseModel):
    farm_id: int
    provider: str = "AUTO"              # AUTO | COPERNICUS | BHUVAN | BHOONIDHI | MOCK
    start_date: str                     # "YYYY-MM-DD"
    end_date: str                       # "YYYY-MM-DD"
    cloud_cover_max: float = 30.0

    @field_validator("cloud_cover_max")
    @classmethod
    def clamp_cloud(cls, v: float) -> float:
        return max(0.0, min(100.0, v))


class SatelliteIndicesRequest(BaseModel):
    farm_id: int
    crop_cycle_id: Optional[int] = None
    provider: str = "AUTO"
    indices: List[str] = ["NDVI", "NDWI"]
    start_date: str
    end_date: str


class BoundaryValidationResponse(BaseModel):
    valid: bool
    area_m2: Optional[float] = None
    area_hectares: Optional[float] = None
    area_acres: Optional[float] = None
    area_warning: Optional[str] = None
    error: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _farm_aoi(farm: Farm) -> Dict[str, Any]:
    """Return AOI GeoJSON for a farm: boundary polygon if available, else point."""
    boundary = parse_geojson_from_storage(farm.farm_boundary_geojson)
    if boundary:
        return boundary
    return point_geojson(farm.longitude, farm.latitude)


def _aoi_meta(farm: Farm) -> Dict[str, Optional[str]]:
    """
    Return AOI source metadata for satellite search responses.

    aoi_source:  "BOUNDARY"            — satellite AOI is the saved polygon
                 "CENTER_POINT_BUFFER" — no boundary; AOI is a buffer around farm centre
    aoi_warning: None when boundary exists; human-readable warning otherwise.
    """
    if farm.farm_boundary_geojson:
        return {"aoi_source": "BOUNDARY", "aoi_warning": None}
    return {
        "aoi_source": "CENTER_POINT_BUFFER",
        "aoi_warning": (
            "No farm boundary saved. Satellite analysis is estimated from the farm "
            "center point. Draw a boundary for accurate MRV."
        ),
    }


# ── GET /gis/providers/status ─────────────────────────────────────────────────

@router.get("/providers/status")
def gis_provider_status(
    current_user: User = Depends(get_current_user),
):
    """
    Returns configuration state for all satellite providers.
    Fast — config check only, no outbound calls.
    API keys are NEVER exposed in the response.
    """
    svc = get_gis_service()
    return svc.get_provider_status()


# ── GET /gis/providers/health ─────────────────────────────────────────────────

@router.get("/providers/health")
def gis_provider_health(
    current_user: User = Depends(get_current_user),
):
    """
    Run live connectivity health checks on all providers.
    ADMIN + FPO only (makes outbound HTTP calls).
    """
    if current_user.role not in (UserRole.ADMIN, UserRole.FPO):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN or FPO may run provider health checks",
        )
    svc = get_gis_service()
    return svc.run_health_checks()


# ── GET /gis/farms/{farm_id}/boundary ────────────────────────────────────────

@router.get("/farms/{farm_id}/boundary")
def gis_get_boundary(
    farm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return stored GeoJSON boundary + computed areas for a farm."""
    farm = _get_farm_or_404(farm_id, db)
    _assert_farm_access(farm, current_user, db)

    areas: Optional[Dict[str, float]] = None
    if farm.farm_boundary_geojson:
        areas = compute_polygon_areas(farm.farm_boundary_geojson)

    # parse_geojson_from_storage: DB Text → dict (or None on invalid/missing)
    boundary_obj = parse_geojson_from_storage(farm.farm_boundary_geojson)
    return {
        "farm_id": farm.id,
        "farm_name": farm.farm_name,
        "latitude": farm.latitude,
        "longitude": farm.longitude,
        "has_boundary": bool(farm.farm_boundary_geojson),
        # Primary field — always a parsed dict, never a raw string
        "farm_boundary_geojson": boundary_obj,
        # Convenience alias so mobile can use either field name
        "boundary": boundary_obj,
        "boundary_area_hectares": farm.boundary_area_hectares,
        "boundary_area_acres": farm.boundary_area_acres,
        "computed_area": areas,
    }


# ── GET /gis/farms/{farm_id}/map-data ────────────────────────────────────────

@router.get("/farms/{farm_id}/map-data")
def gis_farm_map_data(
    farm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    One-shot map payload for the mobile Farm Map screen.
    Returns: marker, boundary GeoJSON, area, latest satellite summary.
    The satellite summary uses AUTO provider (best available).
    """
    farm = _get_farm_or_404(farm_id, db)
    _assert_farm_access(farm, current_user, db)

    # Latest satellite scenes (past 30 days, no cloud filter needed for summary)
    today = date.today()
    start = (today - timedelta(days=30)).isoformat()
    end   = today.isoformat()

    aoi = _farm_aoi(farm)
    svc = get_gis_service()
    sat = svc.search_scenes(
        aoi_geojson=aoi,
        start_date=start,
        end_date=end,
        cloud_cover_max=50.0,
        provider="AUTO",
        farm_id=farm_id,
    )

    # Latest scene summary
    latest_scene = None
    if sat.get("scenes"):
        latest_scene = sat["scenes"][-1]

    bbox = geojson_to_bbox(aoi)

    # parse_geojson_from_storage: DB Text → dict (or None on invalid/missing)
    boundary_obj = parse_geojson_from_storage(farm.farm_boundary_geojson)
    return {
        "farm_id": farm.id,
        "farm_name": farm.farm_name,
        "marker": {
            "latitude": farm.latitude,
            "longitude": farm.longitude,
        },
        "bbox": bbox,
        "has_boundary": bool(farm.farm_boundary_geojson),
        # Primary field — always a parsed dict, never a raw string
        "farm_boundary_geojson": boundary_obj,
        # Convenience alias so mobile can use either field name
        "boundary": boundary_obj,
        "boundary_area_hectares": farm.boundary_area_hectares,
        "boundary_area_acres": farm.boundary_area_acres,
        "land_area_acres": farm.land_area_acres,
        "satellite_summary": {
            "provider": sat.get("provider"),
            "is_mock": sat.get("is_mock", False),
            "scene_count": sat.get("count", 0),
            "latest_scene": latest_scene,
        },
    }


# ── POST /gis/satellite/search ────────────────────────────────────────────────

@router.post("/satellite/search")
def gis_satellite_search(
    payload: SatelliteSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Search satellite scenes for a farm.
    provider="AUTO" tries real providers first; MOCK only as last resort.
    Explicit provider="MOCK" allowed for all authenticated users (testing).
    """
    farm = _get_farm_or_404(payload.farm_id, db)
    _assert_farm_access(farm, current_user, db)

    aoi = _farm_aoi(farm)
    svc = get_gis_service()
    result = svc.search_scenes(
        aoi_geojson=aoi,
        start_date=payload.start_date,
        end_date=payload.end_date,
        cloud_cover_max=payload.cloud_cover_max,
        provider=payload.provider,
        farm_id=payload.farm_id,
    )
    # Enrich with AOI source metadata so mobile can show which AOI was used
    result.update(_aoi_meta(farm))
    result["bbox"] = geojson_to_bbox(aoi)
    return result


# ── POST /gis/satellite/indices ───────────────────────────────────────────────

@router.post("/satellite/indices")
def gis_satellite_indices(
    payload: SatelliteIndicesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get NDVI/NDWI indices for a farm over a date range.
    Phase 12 Stage A: returns scene list with indices where available.
    Phase 13 will compute per-pixel averages via Sentinel Hub Process API.
    """
    farm = _get_farm_or_404(payload.farm_id, db)
    _assert_farm_access(farm, current_user, db)

    aoi = _farm_aoi(farm)
    svc = get_gis_service()
    result = svc.get_indices(
        farm_id=payload.farm_id,
        aoi_geojson=aoi,
        start_date=payload.start_date,
        end_date=payload.end_date,
        indices=payload.indices,
        provider=payload.provider,
        crop_cycle_id=payload.crop_cycle_id,
    )
    result["requested_indices"] = payload.indices
    # Enrich with AOI source metadata so mobile can show which AOI was used
    result.update(_aoi_meta(farm))
    result["bbox"] = geojson_to_bbox(aoi)
    return result


# ── POST /gis/farms/{farm_id}/boundary/validate ───────────────────────────────

class BoundaryValidateRequest(BaseModel):
    farm_boundary_geojson: str = ""


@router.post("/farms/{farm_id}/boundary/validate", response_model=BoundaryValidationResponse)
def validate_boundary(
    farm_id: int,
    payload: BoundaryValidateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Validate a proposed boundary GeoJSON without saving.
    Returns area + warning if boundary area differs significantly from
    the registered land_area_acres.
    """
    farm = _get_farm_or_404(farm_id, db)
    _assert_farm_access(farm, current_user, db)

    geojson_str = payload.farm_boundary_geojson
    if not geojson_str:
        return BoundaryValidationResponse(valid=False, error="farm_boundary_geojson is required")

    try:
        validate_polygon_geojson(geojson_str)
    except GeoJSONValidationError as exc:
        return BoundaryValidationResponse(valid=False, error=str(exc))

    areas = compute_polygon_areas(geojson_str)
    if not areas or areas["area_m2"] <= 0:
        return BoundaryValidationResponse(valid=False, error="Polygon area is zero or could not be computed")

    # Area mismatch warning
    warning: Optional[str] = None
    if farm.land_area_acres and farm.land_area_acres > 0:
        ratio = areas["area_acres"] / farm.land_area_acres
        if ratio < 0.5 or ratio > 2.0:
            warning = (
                f"Boundary area ({areas['area_acres']:.2f} acres) differs significantly "
                f"from registered land area ({farm.land_area_acres:.2f} acres). "
                "Please verify the boundary."
            )

    return BoundaryValidationResponse(
        valid=True,
        area_m2=areas["area_m2"],
        area_hectares=areas["area_hectares"],
        area_acres=areas["area_acres"],
        area_warning=warning,
    )
