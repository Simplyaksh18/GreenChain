"""
geometry_utils.py — GeoJSON validation and area calculation helpers.

All calculations use WGS84 coordinates (EPSG:4326).
Area uses the Shoelace / spherical excess formula — accurate enough for
agricultural parcels (< 1% error for typical farm sizes).
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple


# ── GeoJSON validation ────────────────────────────────────────────────────────

class GeoJSONValidationError(ValueError):
    pass


def validate_polygon_geojson(raw: str) -> Dict[str, Any]:
    """
    Parse and validate a GeoJSON Polygon string.
    Raises GeoJSONValidationError with a human-readable message on failure.
    Returns the parsed dict on success.
    """
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GeoJSONValidationError(f"Invalid JSON: {exc}") from exc

    gtype = obj.get("type", "")
    if gtype not in ("Polygon", "Feature"):
        raise GeoJSONValidationError(
            f"Expected GeoJSON type 'Polygon' or 'Feature', got '{gtype}'"
        )

    if gtype == "Feature":
        geom = obj.get("geometry") or {}
        if geom.get("type") != "Polygon":
            raise GeoJSONValidationError(
                "Feature geometry must be a Polygon"
            )
        coords_rings = geom.get("coordinates", [])
    else:
        coords_rings = obj.get("coordinates", [])

    if not coords_rings:
        raise GeoJSONValidationError("Polygon has no coordinate rings")

    outer_ring = coords_rings[0]
    if len(outer_ring) < 4:
        raise GeoJSONValidationError(
            "Polygon outer ring must have at least 4 positions (3 unique + close)"
        )

    # Validate each [lon, lat] pair
    for pos in outer_ring:
        if len(pos) < 2:
            raise GeoJSONValidationError(f"Coordinate position too short: {pos}")
        lon, lat = pos[0], pos[1]
        if not (-180 <= lon <= 180):
            raise GeoJSONValidationError(
                f"Longitude {lon} out of range [-180, 180]. "
                "Coordinates must be [longitude, latitude] (WGS84)."
            )
        if not (-90 <= lat <= 90):
            raise GeoJSONValidationError(
                f"Latitude {lat} out of range [-90, 90]."
            )

    return obj


def extract_polygon_coords(geojson: Dict[str, Any]) -> List[List[float]]:
    """Return outer ring coordinates from a validated GeoJSON Polygon or Feature."""
    if geojson.get("type") == "Feature":
        return geojson["geometry"]["coordinates"][0]
    return geojson["coordinates"][0]


# ── Area calculation ──────────────────────────────────────────────────────────

_EARTH_RADIUS_M = 6_371_000.0  # metres


def polygon_area_m2(coords: List[List[float]]) -> float:
    """
    Calculate the area of a WGS84 polygon in square metres using the
    spherical excess (l'Huilier) approximation via the Shoelace formula
    projected to a local Cartesian plane.

    Sufficient for agricultural parcels (<50 km²); for larger areas use
    a proper geodetic library.
    """
    if len(coords) < 3:
        return 0.0

    # Use centroid lat for projection
    lats = [c[1] for c in coords]
    lons = [c[0] for c in coords]
    lat0 = math.radians(sum(lats) / len(lats))

    # Convert to local Cartesian (metres from centroid)
    def to_xy(lon: float, lat: float) -> Tuple[float, float]:
        x = math.radians(lon) * _EARTH_RADIUS_M * math.cos(lat0)
        y = math.radians(lat) * _EARTH_RADIUS_M
        return x, y

    pts = [to_xy(c[0], c[1]) for c in coords]

    # Shoelace formula
    n = len(pts)
    area = 0.0
    for i in range(n - 1):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2.0


def area_m2_to_hectares(m2: float) -> float:
    return m2 / 10_000.0


def area_m2_to_acres(m2: float) -> float:
    return m2 / 4_046.856


def compute_polygon_areas(geojson_str: str) -> Optional[Dict[str, float]]:
    """
    Full pipeline: parse → validate → compute area.
    Returns dict with hectares and acres, or None on error.
    """
    try:
        geojson = validate_polygon_geojson(geojson_str)
        coords  = extract_polygon_coords(geojson)
        m2      = polygon_area_m2(coords)
        return {
            "area_m2":       round(m2, 2),
            "area_hectares": round(area_m2_to_hectares(m2), 4),
            "area_acres":    round(area_m2_to_acres(m2), 4),
        }
    except Exception:
        return None


# ── Bounding box ──────────────────────────────────────────────────────────────

def geojson_to_bbox(geojson: Dict[str, Any]) -> List[float]:
    """Return [min_lon, min_lat, max_lon, max_lat] for any GeoJSON geometry."""
    gtype = geojson.get("type", "")
    if gtype == "Point":
        lon, lat = geojson["coordinates"]
        buf = 0.05
        return [lon - buf, lat - buf, lon + buf, lat + buf]
    if gtype == "Feature":
        return geojson_to_bbox(geojson["geometry"])
    if gtype == "Polygon":
        coords = geojson["coordinates"][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        return [min(lons), min(lats), max(lons), max(lats)]
    return [0.0, 0.0, 0.0, 0.0]


def point_geojson(lon: float, lat: float) -> Dict[str, Any]:
    return {"type": "Point", "coordinates": [lon, lat]}
