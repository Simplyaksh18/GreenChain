"""
test_phase13_soc.py — Phase 13 SOC integration tests.

Covers:
  21. Copernicus (SENTINEL_2) obs → source label mentions Copernicus
  22. Simulated source → source label non-empty
  23. LAB measurement → source_label mentions lab
  24. MANUAL measurement → source_label mentions manual
  25. Confidence breakdown structure (all required keys, 0–100 ints)
  26. Diagnostics structure (all auditable fields)
  27. Recommendations present when using fallback
  28. LAB overrides BHUVAN/Copernicus measurements for baseline
  29. BHUVAN measurement overrides fallback
  30. SENTINEL_2 obs → higher confidence than SIMULATED obs
  31. SOC remains informational in Phase 13 (is_informational_only=True)
  32. Overview source_label populated when estimate exists
  33. Payment status endpoint returns safe flags, never secrets
"""
from __future__ import annotations

import pytest
from datetime import date as _date, timedelta as _td

from tests.conftest import (
    _make_user, _make_fpo_profile, _make_farm, _make_cycle,
    _make_satellite_observations,
)
from app.models.user import UserRole
from app.models.satellite_observation import (
    SatelliteObservation, SatelliteSource, VegetationHealth, FloodRisk,
)
from app.security import create_access_token


def _tok(user) -> str:
    return create_access_token({"sub": str(user.id)})


def _auth(user) -> dict:
    return {"Authorization": f"Bearer {_tok(user)}"}


# ── Shared fixture ─────────────────────────────────────────────────────────────

@pytest.fixture
def setup(db):
    farmer   = _make_user(db, "P13 Farmer",  "p13_farmer@test.com",  UserRole.FARMER)
    farmer2  = _make_user(db, "P13 Farmer2", "p13_farmer2@test.com", UserRole.FARMER)
    admin    = _make_user(db, "P13 Admin",   "p13_admin@test.com",   UserRole.ADMIN)
    verifier = _make_user(db, "P13 Verif",   "p13_verif@test.com",   UserRole.VERIFIER)
    fpo_usr  = _make_user(db, "P13 FPO",     "p13_fpo@test.com",     UserRole.FPO)
    fpo_prof = _make_fpo_profile(db, fpo_usr)
    farm     = _make_farm(db, farmer, fpo_profile=fpo_prof, approved=True)
    cycle    = _make_cycle(db, farm)
    return dict(farmer=farmer, farmer2=farmer2, admin=admin,
                verifier=verifier, fpo_usr=fpo_usr, fpo_prof=fpo_prof,
                farm=farm, cycle=cycle)


def _obs_with_source(db, farm, cycle, source_tag: str, count: int = 5, base_ndvi: float = 0.60):
    """Create satellite observations with a specific SatelliteSource."""
    base = _date(2024, 6, 1)
    src = SatelliteSource[source_tag] if source_tag in SatelliteSource.__members__ else SatelliteSource.SATELLITE_SIMULATED
    for i in range(count):
        db.add(SatelliteObservation(
            farm_id=farm.id,
            crop_cycle_id=cycle.id,
            observation_date=base + _td(days=i * 5),
            ndvi=round(base_ndvi + i * 0.01, 4),
            ndwi=0.25,
            vegetation_health=VegetationHealth.GOOD,
            flood_risk=FloodRisk.NONE,
            cloud_cover_percent=5.0,
            source=src,
        ))
    db.commit()


# ── 21. SENTINEL_2 → source_label mentions Copernicus ─────────────────────────

def test_copernicus_source_label_in_estimate(client, setup, db):
    farm, cycle = setup["farm"], setup["cycle"]
    _obs_with_source(db, farm, cycle, "SENTINEL_2", count=5)

    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200, r.text
    d = r.json()
    label = d.get("source_label", "")
    assert "copernicus" in label.lower() or "sentinel" in label.lower(), (
        f"Expected Copernicus/Sentinel in source_label, got: {label!r}"
    )


# ── 22. SATELLITE_SIMULATED → source_label is non-empty ───────────────────────

def test_simulated_source_label_non_empty(client, setup, db):
    farm, cycle = setup["farm"], setup["cycle"]
    _obs_with_source(db, farm, cycle, "SATELLITE_SIMULATED", count=5)

    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200, r.text
    assert r.json().get("source_label", "") != ""


# ── 23. LAB measurement → source_label mentions 'lab' ────────────────────────

def test_lab_source_label(client, setup):
    farm, cycle = setup["farm"], setup["cycle"]
    client.post(
        f"/soc/farms/{farm.id}/measurements",
        json={"soc_percent": 0.91, "soc_source": "LAB"},
        headers=_auth(setup["farmer"]),
    )
    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200, r.text
    assert "lab" in r.json()["source_label"].lower()


# ── 24. MANUAL → source_label mentions 'manual' ───────────────────────────────

def test_manual_source_label(client, setup):
    farm, cycle = setup["farm"], setup["cycle"]
    client.post(
        f"/soc/farms/{farm.id}/measurements",
        json={"soc_percent": 0.72, "soc_source": "MANUAL"},
        headers=_auth(setup["farmer"]),
    )
    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200, r.text
    assert "manual" in r.json()["source_label"].lower()


# ── 25. Confidence breakdown structure ────────────────────────────────────────

def test_confidence_breakdown_structure(client, setup, db):
    farm, cycle = setup["farm"], setup["cycle"]
    _make_satellite_observations(db, farm, cycle, count=5)

    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200, r.text
    d = r.json()
    cb = d.get("confidence_breakdown")
    assert cb is not None, "confidence_breakdown must not be None"
    required = (
        "baseline_source", "baseline_confidence", "observation_source",
        "observation_confidence", "provider_confidence",
        "crop_cycle_confidence", "final_confidence", "reason",
    )
    for key in required:
        assert key in cb, f"Missing confidence_breakdown key: {key}"
    assert 0 <= cb["final_confidence"] <= 100
    assert 0 <= cb["baseline_confidence"] <= 100
    assert isinstance(cb["reason"], str) and len(cb["reason"]) > 10


# ── 26. Diagnostics structure ─────────────────────────────────────────────────

def test_diagnostics_structure(client, setup, db):
    farm, cycle = setup["farm"], setup["cycle"]
    _make_satellite_observations(db, farm, cycle, count=5)

    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200, r.text
    diag = r.json().get("diagnostics")
    assert diag is not None, "diagnostics must not be None"
    required = (
        "provider_used", "observation_count", "farm_area_ha",
        "bulk_density", "soil_depth_cm", "calculation_version",
        "baseline_soc_source", "soc_gain_formula", "co2e_conversion",
    )
    for key in required:
        assert key in diag, f"Missing diagnostics key: {key}"
    assert diag["bulk_density"] == pytest.approx(1.3)
    assert diag["soil_depth_cm"] == pytest.approx(30.0)
    assert diag["calculation_version"] == "v1"
    assert diag["observation_count"] >= 5


# ── 27. Recommendations present with fallback estimation ──────────────────────

def test_recommendations_present(client, setup, db):
    farm, cycle = setup["farm"], setup["cycle"]
    _make_satellite_observations(db, farm, cycle, count=5)

    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200, r.text
    recs = r.json().get("recommendations", [])
    assert isinstance(recs, list) and len(recs) > 0


# ── 28. LAB overrides BHUVAN measurement ──────────────────────────────────────

def test_lab_overrides_bhuvan(client, setup):
    farm, cycle = setup["farm"], setup["cycle"]
    client.post(
        f"/soc/farms/{farm.id}/measurements",
        json={"soc_percent": 0.60, "soc_source": "BHUVAN"},
        headers=_auth(setup["farmer"]),
    )
    client.post(
        f"/soc/farms/{farm.id}/measurements",
        json={"soc_percent": 0.85, "soc_source": "LAB"},
        headers=_auth(setup["farmer"]),
    )
    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    d = r.json()
    assert d["source_used"] == "LAB"
    assert d["baseline_soc_percent"] == pytest.approx(0.85, abs=0.001)


# ── 29. BHUVAN overrides fallback ─────────────────────────────────────────────

def test_bhuvan_overrides_fallback(client, setup):
    farm, cycle = setup["farm"], setup["cycle"]
    client.post(
        f"/soc/farms/{farm.id}/measurements",
        json={"soc_percent": 0.72, "soc_source": "BHUVAN"},
        headers=_auth(setup["farmer"]),
    )
    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    d = r.json()
    assert d["source_used"] == "BHUVAN"
    assert d["baseline_soc_percent"] == pytest.approx(0.72, abs=0.001)


# ── 30. SENTINEL_2 obs → higher confidence than SIMULATED obs ─────────────────

def test_copernicus_higher_confidence_than_simulated(client, setup, db):
    farmer_a = setup["farmer"]
    farmer_b = setup["farmer2"]
    farm_a   = setup["farm"]
    cycle_a  = setup["cycle"]

    farm_b  = _make_farm(db, farmer_b, farm_name="Conf Farm B P13",
                         land_area_acres=farm_a.land_area_acres,
                         soil_type=farm_a.soil_type)
    cycle_b = _make_cycle(db, farm_b, crop_type=cycle_a.crop_type)

    _obs_with_source(db, farm_a, cycle_a, "SATELLITE_SIMULATED", count=5, base_ndvi=0.60)
    _obs_with_source(db, farm_b, cycle_b, "SENTINEL_2",          count=5, base_ndvi=0.60)

    admin = setup["admin"]
    r_a = client.get(f"/soc/farms/{farm_a.id}/crop-cycles/{cycle_a.id}/estimate", headers=_auth(admin))
    r_b = client.get(f"/soc/farms/{farm_b.id}/crop-cycles/{cycle_b.id}/estimate", headers=_auth(admin))

    assert r_a.status_code == 200 and r_b.status_code == 200
    conf_sim = r_a.json()["confidence_score"]
    conf_cop = r_b.json()["confidence_score"]
    assert conf_cop > conf_sim, (
        f"Copernicus confidence ({conf_cop:.3f}) must exceed simulated ({conf_sim:.3f})"
    )


# ── 31. SOC informational_only still True in Phase 13 ────────────────────────

def test_soc_informational_phase13(client, setup, db):
    farm, cycle = setup["farm"], setup["cycle"]
    _make_satellite_observations(db, farm, cycle, count=5)

    r1 = client.get(f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
                    headers=_auth(setup["farmer"]))
    assert r1.json()["is_informational_only"] is True

    r2 = client.get(f"/soc/farms/{farm.id}/overview",
                    headers=_auth(setup["farmer"]))
    assert r2.json()["is_informational_only"] is True

    r3 = client.get(f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/combined",
                    headers=_auth(setup["farmer"]))
    comb = r3.json()
    assert comb["mintable_credits"] == comb["methane_credits"]


# ── 32. Overview source_label present when estimate exists ────────────────────

def test_overview_source_label(client, setup, db):
    farm, cycle = setup["farm"], setup["cycle"]
    _make_satellite_observations(db, farm, cycle, count=5)

    r = client.get(f"/soc/farms/{farm.id}/overview",
                   headers=_auth(setup["farmer"]))
    d = r.json()
    assert d["data_status"] == "LIVE_ESTIMATE"
    assert "source_label" in d
    assert isinstance(d["source_label"], str) and d["source_label"] != ""


# ── 33. Payment status endpoint — safe flags, no secrets ──────────────────────

def test_payment_status_safe(client, setup):
    r = client.get("/system/payment-status",
                   headers=_auth(setup["admin"]))
    assert r.status_code == 200, r.text
    d = r.json()
    for key in ("provider", "mode", "configured", "execution_enabled"):
        assert key in d, f"Missing key in payment-status: {key}"
    # Secrets must NEVER appear
    raw = str(d)
    assert "rzp_" not in raw.lower()         # no Razorpay key prefixes
    for forbidden in ("key_secret", "razorpay_secret", "webhook_secret"):
        assert forbidden not in d, f"Secret field {forbidden!r} must not appear in response"
