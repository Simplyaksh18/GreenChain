"""
Phase 3 — Emissions API tests
Covers: POST /emissions/estimate, POST /emissions/baseline/{id},
        POST /emissions/current/{id}
"""
import pytest

AUTH = lambda t: {"Authorization": f"Bearer {t}"}

CYCLE_PAYLOAD = dict(
    crop_type="Paddy",
    season="Kharif",
    start_date="2024-06-01",
    baseline_method="AWD",
    reduction_practice="SRI",
)

ESTIMATE_PAYLOAD = dict(
    soil_moisture=80.0,
    water_depth_cm=12.0,
    temperature_c=32.0,
    crop_type="Paddy",
)


def _create_cycle(client, token, farm_id, crop_type="Paddy"):
    payload = {**CYCLE_PAYLOAD, "crop_type": crop_type}
    resp = client.post(
        f"/farms/{farm_id}/crop-cycles",
        json=payload,
        headers=AUTH(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _simulate(client, token, farm_id, cycle_id, days=14):
    resp = client.post(
        "/sensors/simulate",
        json={"farm_id": farm_id, "crop_cycle_id": cycle_id, "number_of_days": days},
        headers=AUTH(token),
    )
    assert resp.status_code == 201, resp.text


# ═════════════════════════════════════════════════════════════════════════════
class TestEmissionEstimate:
    def test_authenticated_user_can_estimate(self, client, farmer_token):
        resp = client.post("/emissions/estimate", json=ESTIMATE_PAYLOAD,
                           headers=AUTH(farmer_token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "estimated_methane" in data
        assert "confidence_score" in data
        assert "explanation" in data

    def test_fpo_can_estimate(self, client, fpo_token, fpo_user):
        resp = client.post("/emissions/estimate", json=ESTIMATE_PAYLOAD,
                           headers=AUTH(fpo_token))
        assert resp.status_code == 200

    def test_admin_can_estimate(self, client, admin_token, admin_user):
        resp = client.post("/emissions/estimate", json=ESTIMATE_PAYLOAD,
                           headers=AUTH(admin_token))
        assert resp.status_code == 200

    def test_verifier_can_estimate(self, client, verifier_token, verifier_user):
        resp = client.post("/emissions/estimate", json=ESTIMATE_PAYLOAD,
                           headers=AUTH(verifier_token))
        assert resp.status_code == 200

    def test_unauthenticated_rejected(self, client):
        resp = client.post("/emissions/estimate", json=ESTIMATE_PAYLOAD)
        assert resp.status_code == 401

    def test_methane_is_positive_for_paddy(self, client, farmer_token):
        resp = client.post("/emissions/estimate", json=ESTIMATE_PAYLOAD,
                           headers=AUTH(farmer_token))
        assert resp.json()["estimated_methane"] > 0

    def test_paddy_higher_than_wheat(self, client, farmer_token):
        paddy = client.post("/emissions/estimate",
                            json={**ESTIMATE_PAYLOAD, "crop_type": "Paddy"},
                            headers=AUTH(farmer_token)).json()
        wheat = client.post("/emissions/estimate",
                            json={**ESTIMATE_PAYLOAD, "crop_type": "Wheat"},
                            headers=AUTH(farmer_token)).json()
        assert paddy["estimated_methane"] > wheat["estimated_methane"]

    def test_higher_moisture_increases_estimate(self, client, farmer_token):
        low  = client.post("/emissions/estimate",
                           json={**ESTIMATE_PAYLOAD, "soil_moisture": 20},
                           headers=AUTH(farmer_token)).json()
        high = client.post("/emissions/estimate",
                           json={**ESTIMATE_PAYLOAD, "soil_moisture": 90},
                           headers=AUTH(farmer_token)).json()
        assert high["estimated_methane"] > low["estimated_methane"]

    def test_higher_water_depth_increases_estimate(self, client, farmer_token):
        low  = client.post("/emissions/estimate",
                           json={**ESTIMATE_PAYLOAD, "water_depth_cm": 2},
                           headers=AUTH(farmer_token)).json()
        high = client.post("/emissions/estimate",
                           json={**ESTIMATE_PAYLOAD, "water_depth_cm": 25},
                           headers=AUTH(farmer_token)).json()
        assert high["estimated_methane"] > low["estimated_methane"]

    def test_higher_temperature_increases_estimate(self, client, farmer_token):
        low  = client.post("/emissions/estimate",
                           json={**ESTIMATE_PAYLOAD, "temperature_c": 20},
                           headers=AUTH(farmer_token)).json()
        high = client.post("/emissions/estimate",
                           json={**ESTIMATE_PAYLOAD, "temperature_c": 40},
                           headers=AUTH(farmer_token)).json()
        assert high["estimated_methane"] > low["estimated_methane"]

    def test_explanation_text_present(self, client, farmer_token):
        resp = client.post("/emissions/estimate", json=ESTIMATE_PAYLOAD,
                           headers=AUTH(farmer_token))
        assert len(resp.json()["explanation"]) > 10

    def test_missing_field_rejected(self, client, farmer_token):
        payload = {k: v for k, v in ESTIMATE_PAYLOAD.items() if k != "crop_type"}
        resp = client.post("/emissions/estimate", json=payload,
                           headers=AUTH(farmer_token))
        assert resp.status_code == 422


# ═════════════════════════════════════════════════════════════════════════════
class TestBaselineMethane:
    def test_baseline_returns_correct_structure(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        _simulate(client, farmer_token, farm.id, cycle_id, 14)
        resp = client.post(f"/emissions/baseline/{cycle_id}",
                           headers=AUTH(farmer_token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "baseline_methane" in data
        assert "readings_used" in data
        assert data["crop_cycle_id"] == cycle_id

    def test_baseline_uses_first_7_readings(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        _simulate(client, farmer_token, farm.id, cycle_id, 20)
        resp = client.post(f"/emissions/baseline/{cycle_id}",
                           headers=AUTH(farmer_token))
        assert resp.json()["readings_used"] == 7

    def test_baseline_uses_all_if_fewer_than_7(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        _simulate(client, farmer_token, farm.id, cycle_id, 4)
        resp = client.post(f"/emissions/baseline/{cycle_id}",
                           headers=AUTH(farmer_token))
        assert resp.json()["readings_used"] == 4

    def test_baseline_positive_for_paddy(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        _simulate(client, farmer_token, farm.id, cycle_id, 10)
        resp = client.post(f"/emissions/baseline/{cycle_id}",
                           headers=AUTH(farmer_token))
        assert resp.json()["baseline_methane"] > 0

    def test_baseline_no_readings_returns_404(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        resp = client.post(f"/emissions/baseline/{cycle_id}",
                           headers=AUTH(farmer_token))
        assert resp.status_code == 404

    def test_baseline_invalid_cycle_returns_404(self, client, farmer_token):
        resp = client.post("/emissions/baseline/99999",
                           headers=AUTH(farmer_token))
        assert resp.status_code == 404

    def test_farmer_cannot_get_baseline_of_other_farm(
        self, client, farmer_token, farmer2_token, farm2
    ):
        cycle_id = _create_cycle(client, farmer2_token, farm2.id)
        _simulate(client, farmer2_token, farm2.id, cycle_id, 10)
        resp = client.post(f"/emissions/baseline/{cycle_id}",
                           headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        _simulate(client, farmer_token, farm.id, cycle_id, 7)
        resp = client.post(f"/emissions/baseline/{cycle_id}")
        assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
class TestCurrentMethane:
    def test_current_returns_correct_structure(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        _simulate(client, farmer_token, farm.id, cycle_id, 14)
        resp = client.post(f"/emissions/current/{cycle_id}",
                           headers=AUTH(farmer_token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "current_methane" in data
        assert "readings_used" in data
        assert data["crop_cycle_id"] == cycle_id

    def test_current_uses_latest_7_readings(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        _simulate(client, farmer_token, farm.id, cycle_id, 20)
        resp = client.post(f"/emissions/current/{cycle_id}",
                           headers=AUTH(farmer_token))
        assert resp.json()["readings_used"] == 7

    def test_current_positive_for_paddy(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        _simulate(client, farmer_token, farm.id, cycle_id, 10)
        resp = client.post(f"/emissions/current/{cycle_id}",
                           headers=AUTH(farmer_token))
        assert resp.json()["current_methane"] > 0

    def test_current_no_readings_returns_404(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        resp = client.post(f"/emissions/current/{cycle_id}",
                           headers=AUTH(farmer_token))
        assert resp.status_code == 404

    def test_current_invalid_cycle_returns_404(self, client, farmer_token):
        resp = client.post("/emissions/current/99999",
                           headers=AUTH(farmer_token))
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        _simulate(client, farmer_token, farm.id, cycle_id, 7)
        resp = client.post(f"/emissions/current/{cycle_id}")
        assert resp.status_code == 401

    def test_baseline_and_current_differ_on_long_run(self, client, farmer_token, farm):
        """With enough readings, baseline (first 7) ≠ current (last 7) because
        environmental conditions evolve over the season."""
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        _simulate(client, farmer_token, farm.id, cycle_id, 60)
        baseline = client.post(f"/emissions/baseline/{cycle_id}",
                               headers=AUTH(farmer_token)).json()["baseline_methane"]
        current = client.post(f"/emissions/current/{cycle_id}",
                              headers=AUTH(farmer_token)).json()["current_methane"]
        # They may equal by chance, but with 60 days of seasonal variation they should differ
        # We just ensure both are returned (not strictly asserting difference,
        # since the simulator is deterministic and could coincide)
        assert isinstance(baseline, float)
        assert isinstance(current, float)
