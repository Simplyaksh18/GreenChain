"""
Phase 9C MRV tests — soft delete, PATCH crop cycle, manual MRV observations.

Tests:
- patch_crop_cycle_own_farm_works
- patch_crop_cycle_another_farmer_blocked
- delete_farm_own_farm_works
- deleted_farm_hidden_from_lists
- manual_sensor_reading_validation
- manual_satellite_observation_validation
- manual_drone_observation_validation
- future_dates_blocked
- unauthorized_access_blocked
"""
import pytest
from datetime import date, datetime, timezone, timedelta

AUTH = lambda t: {"Authorization": f"Bearer {t}"}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
VALID_FARM = dict(
    farm_name="Test MRV Farm",
    land_area_acres=3.0,
    latitude=18.52,
    longitude=73.85,
    village="Testpur",
    district="Pune",
    state="Maharashtra",
    soil_type="Loamy",
    water_source="Rain",
)

VALID_CYCLE = dict(
    crop_type="Paddy",
    season="Kharif",
    start_date="2026-01-01",
    baseline_method="AWD",
    reduction_practice="SRI",
)


def create_farm(client, token, **extra):
    payload = {**VALID_FARM, **extra}
    r = client.post("/farms", json=payload, headers=AUTH(token))
    assert r.status_code == 201, r.text
    return r.json()


def create_cycle(client, token, farm_id, **extra):
    payload = {**VALID_CYCLE, **extra}
    r = client.post(f"/farms/{farm_id}/crop-cycles", json=payload, headers=AUTH(token))
    assert r.status_code == 201, r.text
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /farms/{farm_id}/crop-cycles/{cycle_id}
# ─────────────────────────────────────────────────────────────────────────────
class TestPatchCropCycle:
    def test_patch_own_farm_works(self, client, farmer_token):
        farm = create_farm(client, farmer_token)
        cycle = create_cycle(client, farmer_token, farm["id"])

        r = client.patch(
            f"/farms/{farm['id']}/crop-cycles/{cycle['id']}",
            json={"crop_type": "Wheat", "season": "Rabi"},
            headers=AUTH(farmer_token),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["crop_type"] == "Wheat"
        assert data["season"] == "Rabi"

    def test_patch_another_farmers_cycle_blocked(self, client, farmer_token, farmer2_token):
        # farmer creates farm + cycle
        farm = create_farm(client, farmer_token)
        cycle = create_cycle(client, farmer_token, farm["id"])

        # farmer2 tries to patch it
        r = client.patch(
            f"/farms/{farm['id']}/crop-cycles/{cycle['id']}",
            json={"crop_type": "Maize"},
            headers=AUTH(farmer2_token),
        )
        assert r.status_code in (403, 404)

    def test_patch_partial_update(self, client, farmer_token):
        farm = create_farm(client, farmer_token)
        cycle = create_cycle(client, farmer_token, farm["id"])

        r = client.patch(
            f"/farms/{farm['id']}/crop-cycles/{cycle['id']}",
            json={"end_date": "2026-11-30"},
            headers=AUTH(farmer_token),
        )
        assert r.status_code == 200
        assert r.json()["end_date"] == "2026-11-30"
        # original crop_type unchanged
        assert r.json()["crop_type"] == VALID_CYCLE["crop_type"]

    def test_patch_invalid_date_range_rejected(self, client, farmer_token):
        farm = create_farm(client, farmer_token)
        cycle = create_cycle(client, farmer_token, farm["id"], start_date="2026-03-01")

        r = client.patch(
            f"/farms/{farm['id']}/crop-cycles/{cycle['id']}",
            json={"end_date": "2026-02-01"},  # before start_date
            headers=AUTH(farmer_token),
        )
        assert r.status_code == 400

    def test_patch_empty_string_rejected(self, client, farmer_token):
        farm = create_farm(client, farmer_token)
        cycle = create_cycle(client, farmer_token, farm["id"])

        r = client.patch(
            f"/farms/{farm['id']}/crop-cycles/{cycle['id']}",
            json={"crop_type": ""},
            headers=AUTH(farmer_token),
        )
        assert r.status_code == 422

    def test_patch_fpo_blocked(self, client, farmer_token, fpo_token):
        farm = create_farm(client, farmer_token)
        cycle = create_cycle(client, farmer_token, farm["id"])

        r = client.patch(
            f"/farms/{farm['id']}/crop-cycles/{cycle['id']}",
            json={"crop_type": "Wheat"},
            headers=AUTH(fpo_token),
        )
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /farms/{farm_id}  (soft delete)
# ─────────────────────────────────────────────────────────────────────────────
class TestDeleteFarm:
    def test_delete_own_farm_works(self, client, farmer_token):
        farm = create_farm(client, farmer_token, farm_name="To Delete Farm")
        r = client.delete(f"/farms/{farm['id']}", headers=AUTH(farmer_token))
        assert r.status_code == 200
        assert "deleted" in r.json()["message"].lower()

    def test_deleted_farm_hidden_from_list(self, client, farmer_token):
        farm = create_farm(client, farmer_token, farm_name="Hidden Farm")
        client.delete(f"/farms/{farm['id']}", headers=AUTH(farmer_token))

        r = client.get("/farms", headers=AUTH(farmer_token))
        assert r.status_code == 200
        ids = [f["id"] for f in r.json()]
        assert farm["id"] not in ids

    def test_deleted_farm_returns_404_on_get(self, client, farmer_token):
        farm = create_farm(client, farmer_token, farm_name="404 After Delete")
        client.delete(f"/farms/{farm['id']}", headers=AUTH(farmer_token))

        r = client.get(f"/farms/{farm['id']}", headers=AUTH(farmer_token))
        assert r.status_code == 404

    def test_delete_another_farmers_farm_blocked(self, client, farmer_token, farmer2_token):
        farm = create_farm(client, farmer_token)
        r = client.delete(f"/farms/{farm['id']}", headers=AUTH(farmer2_token))
        assert r.status_code in (403, 404)

    def test_delete_fpo_blocked(self, client, farmer_token, fpo_token):
        farm = create_farm(client, farmer_token)
        r = client.delete(f"/farms/{farm['id']}", headers=AUTH(fpo_token))
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# POST /sensors/readings  (manual)
# ─────────────────────────────────────────────────────────────────────────────
class TestManualSensorReading:
    def _valid_reading(self, farm_id, cycle_id):
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return dict(
            farm_id=farm_id,
            crop_cycle_id=cycle_id,
            reading_time=yesterday,
            soil_moisture=55.0,
            water_depth_cm=8.0,
            temperature_c=30.0,
            humidity=70.0,
            rainfall_mm=12.0,
            data_quality_score=85.0,
        )

    def test_farmer_can_submit_manual_reading(self, client, farmer_token):
        farm = create_farm(client, farmer_token)
        cycle = create_cycle(client, farmer_token, farm["id"])
        payload = self._valid_reading(farm["id"], cycle["id"])

        r = client.post("/sensors/readings", json=payload, headers=AUTH(farmer_token))
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["source_type"] == "MANUAL"
        assert data["farm_id"] == farm["id"]
        assert "estimated_methane" in data

    def test_future_reading_time_blocked(self, client, farmer_token):
        farm = create_farm(client, farmer_token)
        cycle = create_cycle(client, farmer_token, farm["id"])
        payload = self._valid_reading(farm["id"], cycle["id"])
        future = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        payload["reading_time"] = future

        r = client.post("/sensors/readings", json=payload, headers=AUTH(farmer_token))
        assert r.status_code == 422

    def test_soil_moisture_out_of_range(self, client, farmer_token):
        farm = create_farm(client, farmer_token)
        cycle = create_cycle(client, farmer_token, farm["id"])
        payload = self._valid_reading(farm["id"], cycle["id"])
        payload["soil_moisture"] = 150.0

        r = client.post("/sensors/readings", json=payload, headers=AUTH(farmer_token))
        assert r.status_code == 422

    def test_temperature_out_of_range(self, client, farmer_token):
        farm = create_farm(client, farmer_token)
        cycle = create_cycle(client, farmer_token, farm["id"])
        payload = self._valid_reading(farm["id"], cycle["id"])
        payload["temperature_c"] = 60.0

        r = client.post("/sensors/readings", json=payload, headers=AUTH(farmer_token))
        assert r.status_code == 422

    def test_verifier_blocked(self, client, verifier_token, farm, crop_cycle):
        payload = self._valid_reading(farm.id, crop_cycle.id)
        r = client.post("/sensors/readings", json=payload, headers=AUTH(verifier_token))
        assert r.status_code == 403

    def test_other_farmer_blocked(self, client, farmer2_token, farm, crop_cycle):
        payload = self._valid_reading(farm.id, crop_cycle.id)
        r = client.post("/sensors/readings", json=payload, headers=AUTH(farmer2_token))
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# POST /satellite/observations  (manual)
# ─────────────────────────────────────────────────────────────────────────────
class TestManualSatelliteObservation:
    def _valid_obs(self, farm_id, cycle_id=None):
        today = datetime.now(timezone.utc).date().isoformat()
        return dict(
            farm_id=farm_id,
            crop_cycle_id=cycle_id,
            observation_date=today,
            ndvi=0.55,
            ndwi=0.12,
            vegetation_health="GOOD",
            flood_risk="NONE",
            cloud_cover_percent=10.0,
        )

    def test_farmer_can_submit_observation(self, client, farmer_token):
        farm = create_farm(client, farmer_token)
        payload = self._valid_obs(farm["id"])
        r = client.post("/satellite/observations", json=payload, headers=AUTH(farmer_token))
        assert r.status_code == 201, r.text
        assert r.json()["source"] == "SATELLITE_MANUAL"

    def test_future_observation_date_blocked(self, client, farmer_token):
        farm = create_farm(client, farmer_token)
        payload = self._valid_obs(farm["id"])
        future = (datetime.now(timezone.utc).date() + timedelta(days=3)).isoformat()
        payload["observation_date"] = future
        r = client.post("/satellite/observations", json=payload, headers=AUTH(farmer_token))
        assert r.status_code == 422

    def test_ndvi_out_of_range(self, client, farmer_token):
        farm = create_farm(client, farmer_token)
        payload = self._valid_obs(farm["id"])
        payload["ndvi"] = 1.5
        r = client.post("/satellite/observations", json=payload, headers=AUTH(farmer_token))
        assert r.status_code == 422

    def test_verifier_blocked(self, client, verifier_token, farm):
        payload = self._valid_obs(farm.id)
        r = client.post("/satellite/observations", json=payload, headers=AUTH(verifier_token))
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# POST /drone/observations  (manual)
# ─────────────────────────────────────────────────────────────────────────────
class TestManualDroneObservation:
    def _valid_obs(self, farm_id, cycle_id=None):
        today = datetime.now(timezone.utc).date().isoformat()
        return dict(
            farm_id=farm_id,
            crop_cycle_id=cycle_id,
            observation_date=today,
            vegetation_cover_percent=72.0,
            standing_water_percent=18.0,
            anomaly_score=5.0,
        )

    def test_farmer_can_submit_observation(self, client, farmer_token):
        farm = create_farm(client, farmer_token)
        payload = self._valid_obs(farm["id"])
        r = client.post("/drone/observations", json=payload, headers=AUTH(farmer_token))
        assert r.status_code == 201, r.text
        assert r.json()["source"] == "DRONE_MANUAL"

    def test_future_observation_date_blocked(self, client, farmer_token):
        farm = create_farm(client, farmer_token)
        payload = self._valid_obs(farm["id"])
        future = (datetime.now(timezone.utc).date() + timedelta(days=3)).isoformat()
        payload["observation_date"] = future
        r = client.post("/drone/observations", json=payload, headers=AUTH(farmer_token))
        assert r.status_code == 422

    def test_vegetation_cover_out_of_range(self, client, farmer_token):
        farm = create_farm(client, farmer_token)
        payload = self._valid_obs(farm["id"])
        payload["vegetation_cover_percent"] = 150.0
        r = client.post("/drone/observations", json=payload, headers=AUTH(farmer_token))
        assert r.status_code == 422

    def test_verifier_blocked(self, client, verifier_token, farm):
        payload = self._valid_obs(farm.id)
        r = client.post("/drone/observations", json=payload, headers=AUTH(verifier_token))
        assert r.status_code == 403
