"""
Phase 3 — Sensor API tests
Covers: POST /sensors/simulate, GET /sensors/farm/{farm_id},
        GET /sensors/crop-cycle/{crop_cycle_id}, GET /sensors/summary/{crop_cycle_id}
"""
import pytest

AUTH = lambda t: {"Authorization": f"Bearer {t}"}

SIMULATE_PAYLOAD = lambda farm_id, cycle_id, days=7: {
    "farm_id": farm_id,
    "crop_cycle_id": cycle_id,
    "number_of_days": days,
}


# ── Helper: create a crop cycle via API ────────────────────────────────────────
CYCLE_PAYLOAD = dict(
    crop_type="Paddy",
    season="Kharif",
    start_date="2024-06-01",
    baseline_method="AWD",
    reduction_practice="SRI",
)


def _create_cycle(client, token, farm_id):
    resp = client.post(
        f"/farms/{farm_id}/crop-cycles",
        json=CYCLE_PAYLOAD,
        headers=AUTH(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ═════════════════════════════════════════════════════════════════════════════
class TestSimulateEndpoint:
    def test_farmer_can_simulate_own_farm(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        resp = client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm.id, cycle_id, 10),
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["generated_readings"] == 10
        assert data["farm_id"] == farm.id
        assert data["crop_cycle_id"] == cycle_id

    def test_readings_saved_to_db(self, client, farmer_token, farm, db):
        from app.models.sensor import SensorReading
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm.id, cycle_id, 5),
            headers=AUTH(farmer_token),
        )
        count = db.query(SensorReading).filter(
            SensorReading.crop_cycle_id == cycle_id
        ).count()
        assert count == 5

    def test_fpo_can_simulate_linked_farm(self, client, fpo_token, fpo_profile,
                                          farmer_token, farm_with_fpo):
        cycle_id = _create_cycle(client, farmer_token, farm_with_fpo.id)
        resp = client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm_with_fpo.id, cycle_id, 3),
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 201
        assert resp.json()["generated_readings"] == 3

    def test_admin_can_simulate_any_farm(self, client, admin_token, admin_user,
                                         farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        resp = client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm.id, cycle_id, 4),
            headers=AUTH(admin_token),
        )
        assert resp.status_code == 201
        assert resp.json()["generated_readings"] == 4

    def test_verifier_cannot_simulate(self, client, verifier_token, verifier_user,
                                      farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        resp = client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm.id, cycle_id, 5),
            headers=AUTH(verifier_token),
        )
        assert resp.status_code == 403

    def test_farmer_cannot_simulate_other_farm(self, client, farmer2_token,
                                               farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        resp = client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm.id, cycle_id, 5),
            headers=AUTH(farmer2_token),
        )
        assert resp.status_code == 403

    def test_fpo_cannot_simulate_unlinked_farm(self, client, fpo_token, fpo_profile,
                                               farmer_token, farm):
        # farm is not linked to fpo_profile
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        resp = client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm.id, cycle_id, 5),
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 403

    def test_invalid_farm_id_returns_404(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        resp = client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(99999, cycle_id, 5),
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 404

    def test_invalid_cycle_id_returns_404(self, client, farmer_token, farm):
        resp = client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm.id, 99999, 5),
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 404

    def test_cycle_not_belonging_to_farm_rejected(self, client, farmer_token,
                                                  farm, farm2, farmer2_token):
        # cycle created under farm2
        cycle_id = _create_cycle(client, farmer2_token, farm2.id)
        resp = client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm.id, cycle_id, 5),
            headers=AUTH(farmer_token),
        )
        assert resp.status_code in (400, 403, 404)

    def test_zero_days_rejected(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        resp = client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm.id, cycle_id, 0),
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 422

    def test_negative_days_rejected(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        resp = client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm.id, cycle_id, -5),
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 422

    def test_over_365_days_rejected(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        resp = client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm.id, cycle_id, 400),
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 422

    def test_unauthenticated_rejected(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        resp = client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm.id, cycle_id, 5),
        )
        assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
class TestGetReadingsByFarm:
    def _seed(self, client, token, farm_id, days=5):
        cycle_id = _create_cycle(client, token, farm_id)
        client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm_id, cycle_id, days),
            headers=AUTH(token),
        )
        return cycle_id

    def test_farmer_gets_own_readings(self, client, farmer_token, farm):
        self._seed(client, farmer_token, farm.id, 8)
        resp = client.get(f"/sensors/farm/{farm.id}", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 8

    def test_farmer_cannot_get_other_farm_readings(self, client, farmer_token, farm2):
        resp = client.get(f"/sensors/farm/{farm2.id}", headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_fpo_gets_linked_farm_readings(self, client, farmer_token, fpo_token,
                                           fpo_profile, farm_with_fpo):
        self._seed(client, farmer_token, farm_with_fpo.id, 4)
        resp = client.get(f"/sensors/farm/{farm_with_fpo.id}", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 4

    def test_admin_gets_any_farm_readings(self, client, farmer_token, admin_token,
                                          admin_user, farm):
        self._seed(client, farmer_token, farm.id, 3)
        resp = client.get(f"/sensors/farm/{farm.id}", headers=AUTH(admin_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_reading_fields_present(self, client, farmer_token, farm):
        self._seed(client, farmer_token, farm.id, 1)
        resp = client.get(f"/sensors/farm/{farm.id}", headers=AUTH(farmer_token))
        r = resp.json()[0]
        for field in [
            "id", "farm_id", "crop_cycle_id", "reading_time",
            "soil_moisture", "water_depth_cm", "temperature_c", "humidity",
            "rainfall_mm", "estimated_methane", "data_quality_score",
            "source_type", "created_at",
        ]:
            assert field in r, f"Missing field: {field}"

    def test_farm_not_found(self, client, farmer_token):
        resp = client.get("/sensors/farm/99999", headers=AUTH(farmer_token))
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client, farm):
        resp = client.get(f"/sensors/farm/{farm.id}")
        assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
class TestGetReadingsByCropCycle:
    def test_returns_readings_for_cycle(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm.id, cycle_id, 6),
            headers=AUTH(farmer_token),
        )
        resp = client.get(f"/sensors/crop-cycle/{cycle_id}", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 6

    def test_cycle_not_found(self, client, farmer_token):
        resp = client.get("/sensors/crop-cycle/99999", headers=AUTH(farmer_token))
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client, farmer_token, farm):
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        resp = client.get(f"/sensors/crop-cycle/{cycle_id}")
        assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
class TestSensorSummary:
    def _seed(self, client, token, farm_id, days):
        cycle_id = _create_cycle(client, token, farm_id)
        client.post(
            "/sensors/simulate",
            json=SIMULATE_PAYLOAD(farm_id, cycle_id, days),
            headers=AUTH(token),
        )
        return cycle_id

    def test_summary_returns_correct_count(self, client, farmer_token, farm):
        cycle_id = self._seed(client, farmer_token, farm.id, 15)
        resp = client.get(f"/sensors/summary/{cycle_id}", headers=AUTH(farmer_token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total_readings"] == 15
        assert data["crop_cycle_id"] == cycle_id

    def test_summary_has_all_fields(self, client, farmer_token, farm):
        cycle_id = self._seed(client, farmer_token, farm.id, 5)
        resp = client.get(f"/sensors/summary/{cycle_id}", headers=AUTH(farmer_token))
        data = resp.json()
        for field in [
            "crop_cycle_id", "total_readings",
            "avg_soil_moisture", "avg_water_depth_cm", "avg_temperature_c",
            "avg_humidity", "avg_methane", "avg_data_quality_score",
        ]:
            assert field in data, f"Missing field: {field}"

    def test_summary_averages_in_expected_ranges(self, client, farmer_token, farm):
        cycle_id = self._seed(client, farmer_token, farm.id, 30)
        resp = client.get(f"/sensors/summary/{cycle_id}", headers=AUTH(farmer_token))
        data = resp.json()
        assert 0  <= data["avg_soil_moisture"]   <= 100
        assert 0  <= data["avg_water_depth_cm"]  <= 30
        assert 15 <= data["avg_temperature_c"]   <= 45
        assert 20 <= data["avg_humidity"]         <= 100
        assert data["avg_methane"] >= 0

    def test_summary_zero_readings(self, client, farmer_token, farm):
        # Cycle exists but no simulation run
        cycle_id = _create_cycle(client, farmer_token, farm.id)
        resp = client.get(f"/sensors/summary/{cycle_id}", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        assert resp.json()["total_readings"] == 0

    def test_summary_cycle_not_found(self, client, farmer_token):
        resp = client.get("/sensors/summary/99999", headers=AUTH(farmer_token))
        assert resp.status_code == 404

    def test_summary_farmer_cannot_access_other_farm_cycle(
        self, client, farmer2_token, farmer_token, farm
    ):
        cycle_id = self._seed(client, farmer_token, farm.id, 5)
        resp = client.get(f"/sensors/summary/{cycle_id}", headers=AUTH(farmer2_token))
        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, client, farmer_token, farm):
        cycle_id = self._seed(client, farmer_token, farm.id, 3)
        resp = client.get(f"/sensors/summary/{cycle_id}")
        assert resp.status_code == 401
