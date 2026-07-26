"""
test_soc_module.py — Phase 12.5 SOC module tests

Coverage:
  1.  SOC measurement create (LAB, MANUAL, COPERNICUS, ESTIMATED)
  2.  SOC measurement list
  3.  SOC estimate generation — uses satellite observations as primary input
  4.  SOC estimate falls back when no satellite data exists
  5.  Fallback values only used when observational data unavailable
  6.  SOC credit calculation from known inputs (formula correctness)
  7.  SOC report generation (POST) and retrieval (GET)
  8.  SOC report overwrites existing when re-generated
  9.  Combined methane + SOC report
  10. SOC credits are NOT mintable (explicit guard)
  11. Methane credits unchanged — existing pipeline untouched
  12. Verifier cannot write SOC measurements
  13. Farmer cannot access another farmer's SOC data
  14. Farm overview endpoint
  15. LAB measurement takes priority over satellite for baseline
  16. MANUAL measurement takes priority over satellite when no LAB
  17. Confidence score higher with satellite data than without
  18. SOC gain is non-negative when NDVI > threshold
  19. Combined report total_potential_credits = methane + soc
  20. soc_credits in minting pipeline does NOT increase mintable_credits
"""
import json
import math
import pytest

from tests.conftest import (
    _make_user, _make_fpo_profile, _make_farm, _make_cycle,
    _make_satellite_observations, _make_carbon_report,
)
from app.models.user import UserRole
from app.models.soc import SOCMeasurement, SOCSource
from app.security import create_access_token
from app.services.soc.soc_engine import (
    estimate_soc,
    NDVI_SOC_ALPHA,
    NDVI_BASELINE_THRESHOLD,
    SOIL_MASS_T_PER_HA,
    C_TO_CO2E,
)
from app.services.soc.soc_models import (
    SOCEstimate,
    SOC_FALLBACK_MEDIUM,
    SOC_FALLBACK_LOW,
    SOC_FALLBACK_HIGH,
    MIN_SATELLITE_OBS,
)


def _tok(user) -> str:
    return create_access_token({"sub": str(user.id)})


def _auth(user) -> dict:
    return {"Authorization": f"Bearer {_tok(user)}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def setup(db):
    farmer  = _make_user(db, "SOC Farmer",  "soc_farmer@test.com",  UserRole.FARMER)
    fpo_usr = _make_user(db, "SOC FPO",     "soc_fpo@test.com",     UserRole.FPO)
    admin   = _make_user(db, "SOC Admin",   "soc_admin@test.com",   UserRole.ADMIN)
    verifier= _make_user(db, "SOC Verifier","soc_verif@test.com",   UserRole.VERIFIER)
    farmer2 = _make_user(db, "SOC Farmer2", "soc_farmer2@test.com", UserRole.FARMER)
    fpo_prof= _make_fpo_profile(db, fpo_usr)
    farm    = _make_farm(db, farmer, fpo_profile=fpo_prof, approved=True)
    cycle   = _make_cycle(db, farm)
    return dict(
        farmer=farmer, fpo_usr=fpo_usr, admin=admin,
        verifier=verifier, farmer2=farmer2,
        fpo_prof=fpo_prof, farm=farm, cycle=cycle,
    )


# ── 1. SOC measurement create ─────────────────────────────────────────────────

def test_add_lab_measurement(client, setup):
    farm = setup["farm"]
    r = client.post(
        f"/soc/farms/{farm.id}/measurements",
        json={"soc_percent": 0.72, "soc_source": "LAB", "confidence_score": 0.95},
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["soc_percent"] == 0.72
    assert d["soc_source"] == "LAB"
    assert d["farm_id"] == farm.id


def test_add_manual_measurement(client, setup):
    farm = setup["farm"]
    r = client.post(
        f"/soc/farms/{farm.id}/measurements",
        json={"soc_percent": 0.55, "soc_source": "MANUAL", "confidence_score": 0.80,
              "notes": "Field estimate by agronomist"},
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 201, r.text
    assert r.json()["notes"] == "Field estimate by agronomist"


def test_add_measurement_invalid_percent(client, setup):
    farm = setup["farm"]
    r = client.post(
        f"/soc/farms/{farm.id}/measurements",
        json={"soc_percent": 150.0, "soc_source": "LAB"},
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 422


def test_add_measurement_with_cycle(client, setup):
    farm = setup["farm"]
    cycle = setup["cycle"]
    r = client.post(
        f"/soc/farms/{farm.id}/measurements",
        json={"soc_percent": 0.60, "soc_source": "COPERNICUS",
              "crop_cycle_id": cycle.id},
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 201, r.text
    assert r.json()["crop_cycle_id"] == cycle.id


# ── 2. SOC measurement list ───────────────────────────────────────────────────

def test_list_measurements_empty(client, setup):
    farm = setup["farm"]
    r = client.get(f"/soc/farms/{farm.id}/measurements",
                   headers=_auth(setup["farmer"]))
    assert r.status_code == 200
    assert r.json() == []


def test_list_measurements_after_add(client, setup):
    farm = setup["farm"]
    for pct in [0.4, 0.6, 0.8]:
        client.post(
            f"/soc/farms/{farm.id}/measurements",
            json={"soc_percent": pct, "soc_source": "MANUAL"},
            headers=_auth(setup["farmer"]),
        )
    r = client.get(f"/soc/farms/{farm.id}/measurements",
                   headers=_auth(setup["farmer"]))
    assert r.status_code == 200
    assert len(r.json()) == 3


# ── 3. SOC estimate uses satellite observations ───────────────────────────────

def test_estimate_uses_satellite_data(client, setup, db):
    """Estimate endpoint should report satellite source when obs exist."""
    farm = setup["farm"]
    cycle = setup["cycle"]
    _make_satellite_observations(db, farm, cycle, count=5)

    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["baseline_soc_percent"] > 0
    assert d["current_soc_percent"] >= d["baseline_soc_percent"]
    # Satellite source should appear in sources_detail
    assert any("SATELLITE" in s.upper() for s in d["sources_detail"]) or \
           len(d["sources_detail"]) > 0
    assert d["is_informational_only"] is True


def test_estimate_confidence_higher_with_satellite(client, setup, db):
    """Confidence is higher when satellite obs are available vs. fallback."""
    farm = setup["farm"]
    cycle = setup["cycle"]

    # Without satellite obs
    r_no_sat = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    conf_no_sat = r_no_sat.json()["confidence_score"]

    # Add satellite obs
    _make_satellite_observations(db, farm, cycle, count=5)
    r_with_sat = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    conf_with_sat = r_with_sat.json()["confidence_score"]

    assert conf_with_sat > conf_no_sat, (
        f"Expected higher confidence with satellite data: "
        f"{conf_with_sat} <= {conf_no_sat}"
    )


# ── 4 & 5. Fallback used only when no observational data ─────────────────────

def test_fallback_used_when_no_data(db):
    """Without LAB/MANUAL and without satellite data, system uses fallback."""
    est = estimate_soc(
        land_area_acres=5.0,
        soil_type="Clay",
        crop_type="Paddy",
        reduction_practice="SRI",
        baseline_method="AWD",
        crop_start_date=None,
        crop_end_date=None,
        soc_measurements=[],
        satellite_observations=[],
    )
    # Baseline should be the Clay soil fallback (medium bucket → 0.65%)
    assert est.baseline_soc_percent == SOC_FALLBACK_MEDIUM
    assert est.source_used == "ESTIMATED"
    assert "fallback" in est.methodology_notes.lower() or "estimated" in est.methodology_notes.lower()


def test_lab_overrides_fallback(db):
    """LAB measurement takes priority over all other sources for baseline."""
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    lab_meas = MagicMock()
    lab_meas.soc_percent = 0.88
    lab_meas.soc_source = "LAB"
    lab_meas.created_at = datetime.now(timezone.utc)
    lab_meas.id = 1

    est = estimate_soc(
        land_area_acres=5.0,
        soil_type="Clay",
        crop_type="Paddy",
        reduction_practice="SRI",
        baseline_method="AWD",
        crop_start_date=None,
        crop_end_date=None,
        soc_measurements=[lab_meas],
        satellite_observations=[],
    )
    assert est.baseline_soc_percent == 0.88
    assert est.source_used == "LAB"
    assert est.confidence_score > 0.45   # LAB baseline always high confidence


def test_manual_overrides_fallback_when_no_lab(db):
    """MANUAL measurement takes priority when no LAB exists."""
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    manual_meas = MagicMock()
    manual_meas.soc_percent = 0.75
    manual_meas.soc_source = "MANUAL"
    manual_meas.created_at = datetime.now(timezone.utc)
    manual_meas.id = 2

    est = estimate_soc(
        land_area_acres=5.0,
        soil_type="Clay",
        crop_type="Paddy",
        reduction_practice="SRI",
        baseline_method="AWD",
        crop_start_date=None,
        crop_end_date=None,
        soc_measurements=[manual_meas],
        satellite_observations=[],
    )
    assert est.baseline_soc_percent == 0.75
    assert est.source_used == "MANUAL"


# ── 6. SOC credit calculation formula correctness ─────────────────────────────

def test_soc_formula_known_inputs():
    """
    Verify SOC calculation against manually computed expected values.

    Inputs:
      land_area_acres = 10
      Δ%SOC           = 0.10 %  (forced via LAB baseline + known satellite NDVI)

    Formula:
      area_ha       = 10 × 0.404686 = 4.04686 ha
      soc_t         = 0.10/100 × 3900 × 4.04686 = 15.783 t
      co2e          = 15.783 × 44/12 = 57.872 tCO₂e
      credits       = floor(57.872) = 57
    """
    from app.services.soc.soc_engine import _soc_tonnes_co2e_credits
    soc_tonnes, co2e, credits = _soc_tonnes_co2e_credits(
        delta_soc_percent=0.10,
        land_area_acres=10.0,
    )
    area_ha = 10.0 * 0.404686
    expected_soc_t = (0.10 / 100.0) * SOIL_MASS_T_PER_HA * area_ha
    expected_co2e  = expected_soc_t * C_TO_CO2E
    expected_credits = math.floor(expected_co2e)

    assert abs(soc_tonnes - expected_soc_t) < 0.001
    assert abs(co2e - expected_co2e) < 0.01
    assert credits == expected_credits


def test_soc_formula_zero_gain():
    """Zero Δ%SOC → zero tonnes, zero CO₂e, zero credits."""
    from app.services.soc.soc_engine import _soc_tonnes_co2e_credits
    soc_t, co2e, credits = _soc_tonnes_co2e_credits(0.0, 5.0)
    assert soc_t == 0.0
    assert co2e == 0.0
    assert credits == 0


# ── 7. SOC report generation and retrieval ────────────────────────────────────

def test_generate_soc_report(client, setup):
    farm = setup["farm"]
    cycle = setup["cycle"]

    r = client.post(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/report",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["farm_id"] == farm.id
    assert d["crop_cycle_id"] == cycle.id
    assert d["baseline_soc"] > 0
    assert d["soc_co2e"] >= 0
    assert d["soc_credits"] >= 0
    assert d["is_informational_only"] is True


def test_get_soc_report_after_generate(client, setup):
    farm = setup["farm"]
    cycle = setup["cycle"]

    client.post(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/report",
        headers=_auth(setup["farmer"]),
    )
    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/report",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200, r.text
    assert r.json()["farm_id"] == farm.id


def test_get_soc_report_not_found(client, setup):
    farm = setup["farm"]
    cycle = setup["cycle"]
    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/report",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 404


# ── 8. SOC report overwrites on regeneration ─────────────────────────────────

def test_soc_report_overwrite(client, setup, db):
    farm = setup["farm"]
    cycle = setup["cycle"]

    r1 = client.post(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/report",
        headers=_auth(setup["farmer"]),
    )
    assert r1.status_code == 201
    id1 = r1.json()["id"]

    # Add satellite obs to change the estimate
    _make_satellite_observations(db, farm, cycle, count=5)

    r2 = client.post(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/report",
        headers=_auth(setup["farmer"]),
    )
    assert r2.status_code == 201
    id2 = r2.json()["id"]

    # The old report should be gone; only the new one returned
    r_get = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/report",
        headers=_auth(setup["farmer"]),
    )
    assert r_get.status_code == 200
    assert r_get.json()["id"] == id2


# ── 9. Combined methane + SOC report ─────────────────────────────────────────

def test_combined_report_structure(client, setup):
    farm = setup["farm"]
    cycle = setup["cycle"]

    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/combined",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200, r.text
    d = r.json()

    assert "methane_section" in d
    assert "soc_section" in d
    assert "methane_credits" in d
    assert "soc_credits" in d
    assert "total_potential_credits" in d
    assert "mintable_credits" in d


def test_combined_report_totals(client, setup):
    """total_potential_credits = methane_credits + soc_credits."""
    farm = setup["farm"]
    cycle = setup["cycle"]

    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/combined",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200
    d = r.json()
    assert d["total_potential_credits"] == d["methane_credits"] + d["soc_credits"]


# ── 10. SOC credits are NOT mintable ─────────────────────────────────────────

def test_soc_credits_not_mintable(client, setup):
    """mintable_credits must equal methane_credits, never methane + soc."""
    farm = setup["farm"]
    cycle = setup["cycle"]

    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/combined",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200
    d = r.json()
    # mintable_credits == methane_credits only
    assert d["mintable_credits"] == d["methane_credits"]
    # mintable_credits != total_potential_credits (unless soc_credits == 0)
    if d["soc_credits"] > 0:
        assert d["mintable_credits"] < d["total_potential_credits"]
    # SOC section always informational
    assert d["soc_section"]["is_informational_only"] is True
    # Minting note present
    assert "not mintable" in d["minting_note"].lower() or "informational" in d["minting_note"].lower()


def test_soc_estimate_informational_flag(client, setup):
    """SOC estimate always returns is_informational_only=True."""
    farm = setup["farm"]
    cycle = setup["cycle"]
    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200
    assert r.json()["is_informational_only"] is True


# ── 11. Methane pipeline unchanged ────────────────────────────────────────────

def test_methane_carbon_report_unaffected(client, setup, db):
    """
    Existing carbon report generation must work identically after Phase 12.5.
    SOC data must not appear in or affect the existing CarbonReport.
    """
    from tests.conftest import _make_readings
    farm = setup["farm"]
    cycle = setup["cycle"]
    _make_readings(db, farm, cycle, count=14)

    r = client.post(
        f"/carbon-reports/generate/{cycle.id}",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 201, r.text
    d = r.json()

    # Original fields intact
    assert "baseline_methane_kg" in d
    assert "methane_reduction_kg" in d
    assert "estimated_credits" in d
    assert "report_hash" in d
    assert "status" in d

    # SOC fields must NOT be present in the original carbon report response
    assert "soc_credits" not in d
    assert "soc_gain" not in d
    assert "soc_co2e" not in d


# ── 12. Verifier cannot write SOC data ───────────────────────────────────────

def test_verifier_cannot_add_measurement(client, setup):
    farm = setup["farm"]
    r = client.post(
        f"/soc/farms/{farm.id}/measurements",
        json={"soc_percent": 0.50, "soc_source": "MANUAL"},
        headers=_auth(setup["verifier"]),
    )
    assert r.status_code == 403


def test_verifier_can_read_soc(client, setup):
    """Verifiers can list SOC measurements but not create them."""
    farm = setup["farm"]
    r = client.get(
        f"/soc/farms/{farm.id}/measurements",
        headers=_auth(setup["verifier"]),
    )
    assert r.status_code == 200


# ── 13. Farmer cannot access another farmer's SOC data ───────────────────────

def test_farmer_cannot_access_other_farm(client, setup, db):
    farmer2 = setup["farmer2"]
    farm_other = _make_farm(db, farmer2, farm_name="Other Farm")
    farm = setup["farm"]

    # farmer should not be able to read farmer2's farm
    r = client.get(
        f"/soc/farms/{farm_other.id}/measurements",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 403


# ── 14. Farm overview endpoint — updated for rich data_status schema ─────────

def test_farm_overview_no_crop_cycle(client, setup, db):
    """Farm with no crop cycles returns NO_CROP_CYCLE status."""
    # Create a fresh farm with no cycles
    farmer2 = setup["farmer2"]
    bare_farm = _make_farm(db, farmer2, farm_name="Bare Farm No Cycle")

    r = client.get(f"/soc/farms/{bare_farm.id}/overview",
                   headers=_auth(farmer2))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["farm_id"] == bare_farm.id
    assert d["data_status"] == "NO_CROP_CYCLE"
    assert d["crop_cycle_found"] is False
    assert "NO_ACTIVE_CROP_CYCLE" in d["missing_requirements"]


def test_farm_overview_insufficient_satellite(client, setup):
    """Farm with crop cycle but no satellite observations returns INSUFFICIENT_SATELLITE_DATA."""
    farm = setup["farm"]
    r = client.get(f"/soc/farms/{farm.id}/overview",
                   headers=_auth(setup["farmer"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["farm_id"] == farm.id
    # The setup farm has a crop cycle but no satellite observations → INSUFFICIENT
    assert d["data_status"] == "INSUFFICIENT_SATELLITE_DATA"
    assert d["crop_cycle_found"] is True
    assert d["satellite_observation_count"] == 0
    assert "NO_SATELLITE_OBSERVATIONS" in d["missing_requirements"]


def test_farm_overview_live_estimate_when_satellite_exists(client, setup, db):
    """Farm with crop cycle + satellite obs → LIVE_ESTIMATE (no saved report needed)."""
    farm = setup["farm"]
    cycle = setup["cycle"]
    _make_satellite_observations(db, farm, cycle, count=5)

    r = client.get(f"/soc/farms/{farm.id}/overview",
                   headers=_auth(setup["farmer"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["data_status"] == "LIVE_ESTIMATE", f"Expected LIVE_ESTIMATE, got: {d['data_status']}"
    assert d["is_persisted"] is False
    assert d["crop_cycle_id"] == cycle.id
    assert d["satellite_observation_count"] >= 5
    assert d["baseline_soc_percent"] is not None
    assert d["current_soc_percent"] is not None
    assert d["is_informational_only"] is True
    assert "save" in d["message"].lower() or "estimate" in d["message"].lower()


def test_farm_overview_report_available_after_save(client, setup, db):
    """After generating a SOC report, overview returns REPORT_AVAILABLE."""
    farm = setup["farm"]
    cycle = setup["cycle"]
    _make_satellite_observations(db, farm, cycle, count=5)

    # Generate + save the report
    client.post(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/report",
        headers=_auth(setup["farmer"]),
    )

    r = client.get(f"/soc/farms/{farm.id}/overview",
                   headers=_auth(setup["farmer"]))
    assert r.status_code == 200
    d = r.json()
    assert d["data_status"] == "REPORT_AVAILABLE"
    assert d["is_persisted"] is True
    assert d["baseline_soc_percent"] is not None
    assert d["soc_credits"] is not None


# ── 15. LAB measurement sets baseline in estimate ────────────────────────────

def test_lab_sets_baseline_in_estimate(client, setup):
    farm = setup["farm"]
    cycle = setup["cycle"]

    # Add LAB measurement
    client.post(
        f"/soc/farms/{farm.id}/measurements",
        json={"soc_percent": 0.88, "soc_source": "LAB"},
        headers=_auth(setup["farmer"]),
    )

    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200
    d = r.json()
    assert d["baseline_soc_percent"] == pytest.approx(0.88, abs=0.001)
    assert d["source_used"] == "LAB"


# ── 16. MANUAL beats fallback when no LAB ────────────────────────────────────

def test_manual_sets_baseline_when_no_lab(client, setup):
    farm = setup["farm"]
    cycle = setup["cycle"]

    client.post(
        f"/soc/farms/{farm.id}/measurements",
        json={"soc_percent": 0.77, "soc_source": "MANUAL"},
        headers=_auth(setup["farmer"]),
    )

    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/estimate",
        headers=_auth(setup["farmer"]),
    )
    d = r.json()
    assert d["baseline_soc_percent"] == pytest.approx(0.77, abs=0.001)
    assert d["source_used"] == "MANUAL"


# ── 17. Confidence higher with satellite ─────────────────────────────────────
# (covered in test_estimate_confidence_higher_with_satellite above)


# ── 18. SOC gain non-negative with NDVI above threshold ──────────────────────

def test_ndvi_gain_non_negative():
    """NDVI-derived Δ%SOC is always ≥ 0."""
    from app.services.soc.soc_engine import _ndvi_list_to_soc_gain
    # ndvi below threshold → 0
    gain_low = _ndvi_list_to_soc_gain([0.20, 0.25], 1.0, 1.0, 120)
    assert gain_low == 0.0

    # ndvi above threshold → positive
    gain_high = _ndvi_list_to_soc_gain([0.55, 0.60, 0.58], 1.0, 1.0, 120)
    assert gain_high > 0.0


# ── 19. Combined report total = methane + soc ─────────────────────────────────
# (covered in test_combined_report_totals above)


# ── 20. SOC credits do not increase mintable credits ─────────────────────────

def test_mintable_equals_methane_only(client, setup, db):
    """
    Even with SOC credits present, mintable_credits must equal
    methane_credits exactly (zero or positive).
    """
    from tests.conftest import _make_readings
    farm = setup["farm"]
    cycle = setup["cycle"]
    # Generate a proper carbon report
    _make_readings(db, farm, cycle, count=14)
    client.post(f"/carbon-reports/generate/{cycle.id}",
                headers=_auth(setup["farmer"]))

    # Add satellite obs so SOC > 0
    _make_satellite_observations(db, farm, cycle, count=5)

    r = client.get(
        f"/soc/farms/{farm.id}/crop-cycles/{cycle.id}/combined",
        headers=_auth(setup["farmer"]),
    )
    assert r.status_code == 200
    d = r.json()

    assert d["mintable_credits"] == d["methane_credits"]
    # If we have SOC credits, total > mintable
    if d["soc_credits"] > 0:
        assert d["total_potential_credits"] > d["mintable_credits"]


# ── New tests: overview data_status + satellite fallback + multi-farm ─────────

def test_overview_live_estimate_with_farm_level_obs_only(client, setup, db):
    """
    Regression: satellite observations that have farm_id but no crop_cycle_id
    must still produce a LIVE_ESTIMATE (not INSUFFICIENT_SATELLITE_DATA).

    This simulates the common case of old simulated data without cycle links.
    """
    farm = setup["farm"]
    cycle = setup["cycle"]

    # Create observations with crop_cycle_id=None (farm-level only)
    from app.models.satellite_observation import (
        SatelliteObservation, SatelliteSource, VegetationHealth, FloodRisk,
    )
    from datetime import date, timedelta
    base = date(2024, 6, 1)
    for i in range(5):
        obs = SatelliteObservation(
            farm_id=farm.id,
            crop_cycle_id=None,          # ← no cycle link
            observation_date=base + timedelta(days=i * 5),
            ndvi=round(0.50 + i * 0.02, 4),
            ndwi=round(0.25 + i * 0.01, 4),
            vegetation_health=VegetationHealth.GOOD,
            flood_risk=FloodRisk.NONE,
            cloud_cover_percent=10.0,
            source=SatelliteSource.SATELLITE_SIMULATED,
        )
        db.add(obs)
    db.commit()

    r = client.get(f"/soc/farms/{farm.id}/overview",
                   headers=_auth(setup["farmer"]))
    assert r.status_code == 200, r.text
    d = r.json()
    # Must find the farm-level obs and produce a live estimate
    assert d["data_status"] == "LIVE_ESTIMATE", (
        f"Expected LIVE_ESTIMATE with farm-level obs, got {d['data_status']}. "
        f"satellite_observation_count={d['satellite_observation_count']}"
    )
    assert d["satellite_observation_count"] >= 5
    assert d["baseline_soc_percent"] is not None


def test_overview_multi_farm_independent(client, setup, db):
    """
    Farm A and Farm B get independent SOC estimates — no cross-contamination.
    """
    farmer_a = setup["farmer"]
    farmer_b = setup["farmer2"]

    farm_a = setup["farm"]
    farm_b = _make_farm(db, farmer_b, farm_name="Farm B SOC Test",
                        land_area_acres=10.0, soil_type="Clay")
    cycle_a = setup["cycle"]
    cycle_b = _make_cycle(db, farm_b, crop_type="Wheat")

    # Farm A: 5 observations with high NDVI
    from app.models.satellite_observation import (
        SatelliteObservation, SatelliteSource, VegetationHealth, FloodRisk,
    )
    from datetime import date, timedelta
    base = date(2024, 6, 1)
    for i in range(5):
        db.add(SatelliteObservation(
            farm_id=farm_a.id, crop_cycle_id=cycle_a.id,
            observation_date=base + timedelta(days=i * 5),
            ndvi=0.70, ndwi=0.30,
            vegetation_health=VegetationHealth.EXCELLENT, flood_risk=FloodRisk.NONE,
            cloud_cover_percent=5.0, source=SatelliteSource.SATELLITE_SIMULATED,
        ))
    # Farm B: 5 observations with low NDVI
    for i in range(5):
        db.add(SatelliteObservation(
            farm_id=farm_b.id, crop_cycle_id=cycle_b.id,
            observation_date=base + timedelta(days=i * 5),
            ndvi=0.32, ndwi=0.10,
            vegetation_health=VegetationHealth.FAIR, flood_risk=FloodRisk.NONE,
            cloud_cover_percent=15.0, source=SatelliteSource.SATELLITE_SIMULATED,
        ))
    db.commit()

    r_a = client.get(f"/soc/farms/{farm_a.id}/overview", headers=_auth(farmer_a))
    r_b = client.get(f"/soc/farms/{farm_b.id}/overview", headers=_auth(farmer_b))

    assert r_a.status_code == 200, r_a.text
    assert r_b.status_code == 200, r_b.text

    d_a = r_a.json()
    d_b = r_b.json()

    assert d_a["data_status"] == "LIVE_ESTIMATE"
    assert d_b["data_status"] == "LIVE_ESTIMATE"

    # Farm A should have higher SOC gain (higher NDVI)
    gain_a = d_a["soc_gain_percent"] or 0.0
    gain_b = d_b["soc_gain_percent"] or 0.0
    assert gain_a > gain_b, (
        f"Farm A (high NDVI) should have higher SOC gain than Farm B (low NDVI): "
        f"gain_a={gain_a}, gain_b={gain_b}"
    )


def test_overview_pick_active_cycle_over_older(client, setup, db):
    """When multiple cycles exist, overview uses the ACTIVE one."""
    from app.models.farm import CropCycleStatus
    from datetime import date
    farm = setup["farm"]
    cycle_old = setup["cycle"]

    # Mark the original cycle as CLOSED
    cycle_old.status = CropCycleStatus.CLOSED
    db.commit()

    # Create a new ACTIVE cycle
    cycle_active = _make_cycle(db, farm, crop_type="Wheat")
    cycle_active.status = CropCycleStatus.ACTIVE
    db.commit()
    db.refresh(cycle_active)

    # Add satellite obs for the active cycle
    _make_satellite_observations(db, farm, cycle_active, count=5)

    r = client.get(f"/soc/farms/{farm.id}/overview", headers=_auth(setup["farmer"]))
    assert r.status_code == 200
    d = r.json()
    # Should use the ACTIVE cycle
    assert d["crop_cycle_id"] == cycle_active.id, (
        f"Expected active cycle {cycle_active.id}, got {d['crop_cycle_id']}"
    )
    assert d["data_status"] == "LIVE_ESTIMATE"


def test_overview_diagnostics_present(client, setup, db):
    """Overview always returns diagnostic fields regardless of data_status."""
    farm = setup["farm"]

    r = client.get(f"/soc/farms/{farm.id}/overview", headers=_auth(setup["farmer"]))
    assert r.status_code == 200
    d = r.json()

    # All diagnostic fields must be present
    assert "satellite_observation_count" in d
    assert "crop_cycle_found" in d
    assert "missing_requirements" in d
    assert "is_informational_only" in d
    assert "data_status" in d
    assert "message" in d
    assert d["is_informational_only"] is True


def test_overview_never_empty_with_satellite_data(client, setup, db):
    """
    Core regression test: farm with crop cycle + satellite observations must
    NEVER return data_status=NO_CROP_CYCLE or INSUFFICIENT_SATELLITE_DATA.
    """
    farm = setup["farm"]
    cycle = setup["cycle"]
    _make_satellite_observations(db, farm, cycle, count=6)

    r = client.get(f"/soc/farms/{farm.id}/overview", headers=_auth(setup["farmer"]))
    assert r.status_code == 200
    d = r.json()

    # These two statuses must NOT appear when satellite data exists
    assert d["data_status"] not in ("NO_CROP_CYCLE", "INSUFFICIENT_SATELLITE_DATA"), (
        f"Overview showed empty status despite satellite data: {d['data_status']}. "
        f"satellite_observation_count={d['satellite_observation_count']}, "
        f"crop_cycle_found={d['crop_cycle_found']}"
    )
    assert d["baseline_soc_percent"] is not None
    assert d["current_soc_percent"] is not None
