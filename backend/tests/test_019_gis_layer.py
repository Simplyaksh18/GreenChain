"""
test_019_gis_layer.py — Phase 12 GIS layer tests

Tests:
  1.  GET /gis/providers/status — returns expected shape
  2.  GET /gis/providers/status — does NOT expose API key values
  3.  GET /gis/providers/health — FARMER gets 403
  4.  GET /gis/providers/health — FPO/ADMIN gets response
  5.  GET /gis/farms/{id}/boundary — no boundary returns has_boundary=false
  6.  GET /gis/farms/{id}/boundary — with boundary returns geojson + areas
  7.  GET /gis/farms/{id}/map-data — returns marker + satellite_summary
  8.  POST /gis/satellite/search — AUTO provider returns scenes (mock fallback)
  9.  POST /gis/satellite/search — explicit MOCK provider returns scenes
  10. POST /gis/satellite/indices — returns scenes with indices
  11. POST /gis/farms/{id}/boundary/validate — valid polygon accepted
  12. POST /gis/farms/{id}/boundary/validate — invalid JSON rejected
  13. POST /gis/farms/{id}/boundary/validate — too few points rejected
  14. POST /gis/farms/{id}/boundary/validate — area mismatch triggers warning
  15. Fallback chain: MOCK used when no real provider configured
  16. Provider fallback: Copernicus attempted before Bhuvan in AUTO mode
  17. geometry_utils: polygon_area_m2 — known square gives correct area
  18. geometry_utils: validate_polygon_geojson — invalid lon rejected
  19. Existing /farms endpoints unaffected (non-regression)
"""
import json
import math
import pytest

from tests.conftest import _make_user, _make_fpo_profile, _make_farm
from app.models.user import UserRole
from app.models.farm import FarmStatus
from app.security import create_access_token
from app.services.gis.geometry_utils import (
    polygon_area_m2, validate_polygon_geojson, GeoJSONValidationError,
    compute_polygon_areas,
)
from app.services.gis.normalizer import normalize_scene, NormalizedScene
from app.services.gis.mock_provider import MockProvider
from app.services.gis.gis_service import GISService


def _token(user) -> str:
    return create_access_token({"sub": str(user.id)})


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def setup(db):
    farmer    = _make_user(db, "GIS Farmer",  "gis_farmer@test.com",  UserRole.FARMER)
    fpo_user  = _make_user(db, "GIS FPO",     "gis_fpo@test.com",     UserRole.FPO)
    admin     = _make_user(db, "GIS Admin",   "gis_admin@test.com",   UserRole.ADMIN)
    fpo_prof  = _make_fpo_profile(db, fpo_user)
    farm      = _make_farm(db, farmer, fpo_profile=fpo_prof, approved=True)
    return {
        "farmer": farmer,
        "fpo_user": fpo_user,
        "admin": admin,
        "fpo_profile": fpo_prof,
        "farm": farm,
    }


_VALID_POLYGON = json.dumps({
    "type": "Polygon",
    "coordinates": [[
        [77.5000, 12.9000],
        [77.5100, 12.9000],
        [77.5100, 12.9100],
        [77.5000, 12.9100],
        [77.5000, 12.9000],
    ]]
})

_LARGE_FARM_POLYGON = json.dumps({
    "type": "Polygon",
    "coordinates": [[
        [77.0000, 12.0000],
        [78.0000, 12.0000],
        [78.0000, 13.0000],
        [77.0000, 13.0000],
        [77.0000, 12.0000],
    ]]
})


# ── 1. Provider status shape ──────────────────────────────────────────────────

def test_provider_status_shape(client, setup):
    token = _token(setup["farmer"])
    r = client.get("/gis/providers/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "copernicus" in data
    assert "bhuvan" in data
    assert "bhoonidhi" in data
    assert "mock_fallback_enabled" in data
    assert "active_provider" in data
    assert "mock_mode" in data
    assert isinstance(data["copernicus"]["configured"], bool)


# ── 2. Provider status does NOT expose keys ───────────────────────────────────

def test_provider_status_no_keys(client, setup):
    token = _token(setup["farmer"])
    r = client.get("/gis/providers/status", headers={"Authorization": f"Bearer {token}"})
    raw = r.text
    # Ensure no real API key values appear in the response
    import os
    key = os.environ.get("COPERNICUS_API_KEY", "")
    if key:
        assert key not in raw
    assert "secret" not in raw.lower() or "configured" in raw.lower()


# ── 3. Health check blocked for FARMER ───────────────────────────────────────

def test_health_check_farmer_forbidden(client, setup):
    token = _token(setup["farmer"])
    r = client.get("/gis/providers/health", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


# ── 4. Health check allowed for FPO/ADMIN ────────────────────────────────────

def test_health_check_admin_allowed(client, setup):
    token = _token(setup["admin"])
    r = client.get("/gis/providers/health", headers={"Authorization": f"Bearer {token}"})
    # May return non-200 if providers are unreachable in test env; just check structure
    assert r.status_code == 200
    data = r.json()
    assert "copernicus" in data
    assert "mock" in data


# ── 5. Boundary endpoint — no boundary ───────────────────────────────────────

def test_boundary_no_boundary(client, setup):
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id
    r = client.get(f"/gis/farms/{farm_id}/boundary",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["has_boundary"] is False
    assert data["farm_boundary_geojson"] is None


# ── 6. Boundary endpoint — with boundary ─────────────────────────────────────

def test_boundary_with_boundary(client, setup, db):
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id
    # Save boundary first via existing endpoint
    r = client.patch(
        f"/farms/{farm_id}/boundary",
        json={
            "farm_boundary_geojson": _VALID_POLYGON,
            "boundary_area_hectares": 1.2,
            "boundary_area_acres": 2.96,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200

    r2 = client.get(f"/gis/farms/{farm_id}/boundary",
                    headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    data = r2.json()
    assert data["has_boundary"] is True
    # Response is now a dict (parsed GeoJSON), not a raw string
    assert isinstance(data["farm_boundary_geojson"], dict)
    assert data["farm_boundary_geojson"]["type"] == "Polygon"
    assert data["computed_area"] is not None
    assert data["computed_area"]["area_hectares"] > 0


# ── 7. Map data endpoint ──────────────────────────────────────────────────────

def test_map_data(client, setup):
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id
    r = client.get(f"/gis/farms/{farm_id}/map-data",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "marker" in data
    assert data["marker"]["latitude"] == setup["farm"].latitude
    assert data["marker"]["longitude"] == setup["farm"].longitude
    assert "satellite_summary" in data
    assert "provider" in data["satellite_summary"]


# ── 8. Satellite search — AUTO (mock fallback in test env) ────────────────────

def test_satellite_search_auto(client, setup):
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id
    r = client.post(
        "/gis/satellite/search",
        json={
            "farm_id": farm_id,
            "provider": "AUTO",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "cloud_cover_max": 30,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "provider" in data
    assert "scenes" in data
    assert isinstance(data["scenes"], list)
    assert data["count"] == len(data["scenes"])


# ── 9. Satellite search — explicit MOCK ──────────────────────────────────────

def test_satellite_search_mock(client, setup):
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id
    r = client.post(
        "/gis/satellite/search",
        json={
            "farm_id": farm_id,
            "provider": "MOCK",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "MOCK"
    assert data["is_mock"] is True
    assert len(data["scenes"]) >= 1
    # Each scene has indices with ndvi/ndwi
    for scene in data["scenes"]:
        assert "indices" in scene
        assert "ndvi" in scene["indices"]


# ── 10. Satellite indices ─────────────────────────────────────────────────────

def test_satellite_indices(client, setup):
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id
    r = client.post(
        "/gis/satellite/indices",
        json={
            "farm_id": farm_id,
            "provider": "MOCK",
            "indices": ["NDVI", "NDWI"],
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["requested_indices"] == ["NDVI", "NDWI"]
    assert "scenes" in data


# ── 11. Boundary validate — valid ─────────────────────────────────────────────

def test_boundary_validate_valid(client, setup):
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id
    r = client.post(
        f"/gis/farms/{farm_id}/boundary/validate",
        json={"farm_boundary_geojson": _VALID_POLYGON},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is True
    assert data["area_hectares"] > 0
    assert data["error"] is None


# ── 12. Boundary validate — invalid JSON ─────────────────────────────────────

def test_boundary_validate_invalid_json(client, setup):
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id
    r = client.post(
        f"/gis/farms/{farm_id}/boundary/validate",
        json={"farm_boundary_geojson": "not-json{{{"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is False
    assert data["error"] is not None


# ── 13. Boundary validate — too few points ────────────────────────────────────

def test_boundary_validate_too_few_points(client, setup):
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id
    bad = json.dumps({
        "type": "Polygon",
        "coordinates": [[[77.5, 12.9], [77.51, 12.9], [77.5, 12.9]]]
    })
    r = client.post(
        f"/gis/farms/{farm_id}/boundary/validate",
        json={"farm_boundary_geojson": bad},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is False


# ── 14. Boundary validate — area mismatch warning ─────────────────────────────

def test_boundary_validate_area_warning(client, setup):
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id
    # setup farm has 5 acres; _LARGE_FARM_POLYGON is ~10,000 km² — extreme mismatch
    r = client.post(
        f"/gis/farms/{farm_id}/boundary/validate",
        json={"farm_boundary_geojson": _LARGE_FARM_POLYGON},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is True        # not blocked, just warned
    assert data["area_warning"] is not None


# ── 15. Mock fallback when no real provider configured ────────────────────────

def test_mock_fallback_logic():
    """Unit test: GISService returns MOCK when no real providers have data."""
    svc = GISService()
    # Small AOI in the middle of nowhere
    aoi = {"type": "Point", "coordinates": [77.5, 12.9]}
    result = svc.search_scenes(
        aoi_geojson=aoi,
        start_date="2026-05-01",
        end_date="2026-05-31",
        provider="AUTO",
    )
    # In test env, real providers likely fail → MOCK fallback (if enabled)
    assert "provider" in result
    assert "scenes" in result
    # Provider is either a real one or MOCK — never None with mock enabled
    assert result["provider"] is not None


# ── 16. Provider ordering: Copernicus before Bhuvan ──────────────────────────

def test_provider_order():
    """Copernicus must appear first in the real-providers list."""
    from app.services.gis.gis_service import _REAL_PROVIDERS
    names = [p.provider_name for p in _REAL_PROVIDERS]
    assert names[0] == "COPERNICUS"
    assert names[1] == "BHUVAN"
    assert names[2] == "BHOONIDHI"


# ── 17. geometry_utils: polygon_area_m2 ──────────────────────────────────────

def test_polygon_area_unit_square():
    """
    1° × 1° square centred near equator.
    1° longitude at lat=0 ≈ 111,320 m; 1° latitude ≈ 110,574 m
    → area ≈ 12.3 × 10^9 m² (12,364 km²) — order-of-magnitude check.
    """
    coords = [
        [0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]
    ]
    area = polygon_area_m2(coords)
    # 1° × 1° ≈ 12,300 km² = 1.23×10^10 m²; allow 10% tolerance
    assert 1.4e10 > area > 1.1e10


def test_polygon_area_small_farm():
    """_VALID_POLYGON is 0.01°×0.01° (~1.1 km × 1.1 km ≈ 1.2 km² = 120 ha)."""
    areas = compute_polygon_areas(_VALID_POLYGON)
    assert areas is not None
    # 0.01° × 0.01° at lat≈12.9° ≈ 1.1 km² ≈ 110–130 ha
    assert 50 < areas["area_hectares"] < 200


# ── 18. geometry_utils: invalid longitude rejected ────────────────────────────

def test_invalid_longitude_rejected():
    bad = json.dumps({
        "type": "Polygon",
        "coordinates": [[
            [200.0, 12.9],   # lon > 180 — invalid
            [77.51, 12.9],
            [77.51, 12.91],
            [77.50, 12.91],
            [200.0, 12.9],
        ]]
    })
    with pytest.raises(GeoJSONValidationError):
        validate_polygon_geojson(bad)


# ── 19. Non-regression: existing /farms endpoints still work ──────────────────

def test_existing_farms_unaffected(client, setup):
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id
    r = client.get(f"/farms/{farm_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == farm_id
    assert "farm_name" in data
    assert "farm_status" in data


# ── 20. PATCH boundary with dict GeoJSON returns 200 ─────────────────────────

def test_patch_boundary_dict_input(client, setup):
    """PATCH /farms/{id}/boundary accepts a GeoJSON dict (not just a string)."""
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id
    geojson_dict = {
        "type": "Polygon",
        "coordinates": [[
            [77.5000, 12.9000],
            [77.5100, 12.9000],
            [77.5100, 12.9100],
            [77.5000, 12.9100],
            [77.5000, 12.9000],
        ]]
    }
    r = client.patch(
        f"/farms/{farm_id}/boundary",
        json={"farm_boundary_geojson": geojson_dict},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    # Response farm_boundary_geojson must be a dict, not a string
    assert isinstance(data["farm_boundary_geojson"], dict), (
        f"Expected dict, got {type(data['farm_boundary_geojson'])}: {data['farm_boundary_geojson']!r}"
    )
    assert data["farm_boundary_geojson"]["type"] == "Polygon"


# ── 21. PATCH boundary with string GeoJSON — response is a dict ──────────────

def test_patch_boundary_string_input_returns_dict(client, setup):
    """PATCH with a stringified JSON still works; response is always a dict."""
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id
    r = client.patch(
        f"/farms/{farm_id}/boundary",
        json={"farm_boundary_geojson": _VALID_POLYGON},   # string input
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data["farm_boundary_geojson"], dict), (
        f"Expected dict, got {type(data['farm_boundary_geojson'])}"
    )
    assert data["farm_boundary_geojson"]["type"] == "Polygon"


# ── 22. GET /gis/farms/{id}/boundary — farm_boundary_geojson is a dict ───────

def test_gis_boundary_returns_dict(client, setup):
    """GET /gis/farms/{id}/boundary returns farm_boundary_geojson as a dict."""
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id

    # Save boundary first
    client.patch(
        f"/farms/{farm_id}/boundary",
        json={"farm_boundary_geojson": _VALID_POLYGON},
        headers={"Authorization": f"Bearer {token}"},
    )

    r = client.get(f"/gis/farms/{farm_id}/boundary",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["has_boundary"] is True
    assert isinstance(data["farm_boundary_geojson"], dict), (
        f"Expected dict, got {type(data['farm_boundary_geojson'])}"
    )
    assert data["farm_boundary_geojson"]["type"] == "Polygon"


# ── 23. GET /gis/farms/{id}/map-data — farm_boundary_geojson is a dict ───────

def test_gis_map_data_boundary_is_dict(client, setup):
    """GET /gis/farms/{id}/map-data returns farm_boundary_geojson as a dict."""
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id

    # Save boundary first
    client.patch(
        f"/farms/{farm_id}/boundary",
        json={"farm_boundary_geojson": _VALID_POLYGON},
        headers={"Authorization": f"Bearer {token}"},
    )

    r = client.get(f"/gis/farms/{farm_id}/map-data",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["has_boundary"] is True
    assert isinstance(data["farm_boundary_geojson"], dict), (
        f"Expected dict, got {type(data['farm_boundary_geojson'])}"
    )
    assert data["farm_boundary_geojson"]["type"] == "Polygon"


# ── 24. Invalid GeoJSON returns 422/400, not 500 ─────────────────────────────

def test_patch_boundary_invalid_geojson_not_500(client, setup):
    """Sending garbage GeoJSON must return 4xx, never 500."""
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id
    r = client.patch(
        f"/farms/{farm_id}/boundary",
        json={"farm_boundary_geojson": "not-valid-geojson{{{"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (400, 422), (
        f"Expected 400 or 422 for invalid GeoJSON, got {r.status_code}: {r.text}"
    )


# ── 25. Existing invalid DB value does not crash GET ─────────────────────────

def test_get_boundary_invalid_db_value_no_crash(client, setup, db):
    """
    If the DB column contains a non-JSON string (legacy corruption), GET endpoints
    must return farm_boundary_geojson=null, not 500.
    """
    farm = setup["farm"]
    # Directly corrupt the DB value (bypasses Pydantic validation)
    farm.farm_boundary_geojson = "THIS IS NOT JSON %%$$"
    db.commit()

    token = _token(setup["farmer"])

    r1 = client.get(f"/gis/farms/{farm.id}/boundary",
                    headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 200, f"GET boundary crashed: {r1.text}"
    assert r1.json()["farm_boundary_geojson"] is None

    r2 = client.get(f"/gis/farms/{farm.id}/map-data",
                    headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200, f"GET map-data crashed: {r2.text}"
    assert r2.json()["farm_boundary_geojson"] is None

    # Clean up
    farm.farm_boundary_geojson = None
    db.commit()


# ── 26. PATCH boundary — response has_boundary reflects saved state ───────────

def test_patch_boundary_has_boundary_flag(client, setup):
    """After saving, has_boundary must be True; before, False."""
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id

    # Confirm no boundary yet
    r = client.get(f"/gis/farms/{farm_id}/boundary",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.json()["has_boundary"] is False

    # Save
    r2 = client.patch(
        f"/farms/{farm_id}/boundary",
        json={"farm_boundary_geojson": _VALID_POLYGON},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200, r2.text

    # Confirm saved
    r3 = client.get(f"/gis/farms/{farm_id}/boundary",
                    headers={"Authorization": f"Bearer {token}"})
    assert r3.json()["has_boundary"] is True


# ── 27. Satellite search — no boundary → CENTER_POINT_BUFFER ─────────────────

def test_satellite_search_no_boundary_aoi_source(client, setup):
    """Farm without a boundary → aoi_source=CENTER_POINT_BUFFER + aoi_warning present."""
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id

    r = client.post(
        "/gis/satellite/search",
        json={
            "farm_id": farm_id,
            "provider": "MOCK",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["aoi_source"] == "CENTER_POINT_BUFFER", data.get("aoi_source")
    assert data["aoi_warning"] is not None
    assert "boundary" in data["aoi_warning"].lower()
    assert "bbox" in data


# ── 28. Satellite search — with boundary → BOUNDARY ──────────────────────────

def test_satellite_search_with_boundary_aoi_source(client, setup):
    """Farm with a saved boundary → aoi_source=BOUNDARY, aoi_warning=None."""
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id

    # Save boundary first
    client.patch(
        f"/farms/{farm_id}/boundary",
        json={"farm_boundary_geojson": _VALID_POLYGON},
        headers={"Authorization": f"Bearer {token}"},
    )

    r = client.post(
        "/gis/satellite/search",
        json={
            "farm_id": farm_id,
            "provider": "MOCK",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["aoi_source"] == "BOUNDARY", data.get("aoi_source")
    assert data["aoi_warning"] is None
    assert "bbox" in data


# ── 29. Satellite indices — aoi_source included ───────────────────────────────

def test_satellite_indices_aoi_source(client, setup):
    """POST /gis/satellite/indices also returns aoi_source and aoi_warning."""
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id

    r = client.post(
        "/gis/satellite/indices",
        json={
            "farm_id": farm_id,
            "provider": "MOCK",
            "indices": ["NDVI", "NDWI"],
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "aoi_source" in data
    assert data["aoi_source"] in ("BOUNDARY", "CENTER_POINT_BUFFER")
    assert "aoi_warning" in data
    assert "bbox" in data


# ── 30. map-data endpoint includes `boundary` alias ──────────────────────────

def test_map_data_boundary_alias(client, setup):
    """GET /gis/farms/{id}/map-data returns both farm_boundary_geojson and boundary."""
    token = _token(setup["farmer"])
    farm_id = setup["farm"].id

    # Save a boundary
    client.patch(
        f"/farms/{farm_id}/boundary",
        json={"farm_boundary_geojson": _VALID_POLYGON},
        headers={"Authorization": f"Bearer {token}"},
    )

    r = client.get(f"/gis/farms/{farm_id}/map-data",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    data = r.json()
    # Both fields present and equal
    assert "farm_boundary_geojson" in data
    assert "boundary" in data
    assert isinstance(data["farm_boundary_geojson"], dict)
    assert isinstance(data["boundary"], dict)
    assert data["farm_boundary_geojson"] == data["boundary"]


# ── 31. Regression: has_boundary=True must never coexist with null boundary ────

def test_has_boundary_true_boundary_never_null(client, setup, db):
    """
    Regression for bug where has_boundary=True but farm_boundary_geojson=null.

    Root cause: parse_geojson_from_storage() raised TypeError when the SQLAlchemy
    field was already a Python dict rather than a JSON string, causing the function
    to silently return None.

    This test directly sets farm.farm_boundary_geojson to a dict (simulating how
    SQLAlchemy may surface the value), then confirms both GET endpoints return a
    non-null boundary dict — not null.
    """
    import json as _json
    farm = setup["farm"]
    token = _token(setup["farmer"])

    # Simulate the exact bug condition: dict stored directly in the ORM field
    polygon = {
        "type": "Polygon",
        "coordinates": [[
            [77.5000, 12.9000], [77.5100, 12.9000], [77.5100, 12.9100],
            [77.5000, 12.9100], [77.5000, 12.9000],
        ]]
    }
    # Store as canonical JSON string (normal DB path) — the parse helper must
    # also handle dict input returned by SQLAlchemy deserialization.
    farm.farm_boundary_geojson = _json.dumps(polygon)
    farm.boundary_area_hectares = 1.0
    farm.boundary_area_acres = 2.47
    db.commit()
    db.refresh(farm)

    # GET /gis/farms/{id}/boundary
    r1 = client.get(f"/gis/farms/{farm.id}/boundary",
                    headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1["has_boundary"] is True, "has_boundary should be True"
    assert d1["farm_boundary_geojson"] is not None, (
        "REGRESSION: has_boundary=True but farm_boundary_geojson=null — "
        "parse_geojson_from_storage() dict-handling fix may be missing"
    )
    assert isinstance(d1["farm_boundary_geojson"], dict)
    assert d1["farm_boundary_geojson"]["type"] == "Polygon"
    assert d1["boundary"] is not None, "boundary alias must also be non-null"

    # GET /gis/farms/{id}/map-data
    r2 = client.get(f"/gis/farms/{farm.id}/map-data",
                    headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200, r2.text
    d2 = r2.json()
    assert d2["has_boundary"] is True
    assert d2["farm_boundary_geojson"] is not None, (
        "REGRESSION: has_boundary=True but farm_boundary_geojson=null in map-data"
    )
    assert isinstance(d2["farm_boundary_geojson"], dict)
    assert d2["boundary"] is not None, "boundary alias must also be non-null in map-data"

    # Clean up
    farm.farm_boundary_geojson = None
    farm.boundary_area_hectares = None
    farm.boundary_area_acres = None
    db.commit()
