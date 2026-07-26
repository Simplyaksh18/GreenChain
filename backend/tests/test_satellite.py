"""
Phase 7 — Satellite observation tests.

Tests POST /satellite/simulate and GET /satellite/{farm_id}.
"""
import pytest


class TestSatelliteSimulate:
    def test_farmer_can_simulate_own_farm(self, client, farmer_token, farm):
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": farm.id, "number_of_observations": 3},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["created"] == 3
        assert len(data["observations"]) == 3

    def test_observation_fields_present(self, client, farmer_token, farm):
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": farm.id, "number_of_observations": 1},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        obs = resp.json()["observations"][0]
        assert "ndvi" in obs
        assert "ndwi" in obs
        assert "vegetation_health" in obs
        assert "flood_risk" in obs
        assert "cloud_cover_percent" in obs
        assert obs["source"] == "SATELLITE_SIMULATED"
        assert obs["farm_id"] == farm.id

    def test_ndvi_in_range(self, client, farmer_token, farm):
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": farm.id, "number_of_observations": 5},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        for obs in resp.json()["observations"]:
            assert -1.0 <= obs["ndvi"] <= 1.0
            assert -1.0 <= obs["ndwi"] <= 1.0

    def test_fpo_can_simulate_linked_farm(self, client, fpo_token, farm_with_fpo):
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": farm_with_fpo.id, "number_of_observations": 2},
            headers={"Authorization": f"Bearer {fpo_token}"},
        )
        assert resp.status_code == 201

    def test_admin_can_simulate_any_farm(self, client, admin_token, farm):
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": farm.id, "number_of_observations": 4},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201

    def test_farmer_cannot_simulate_other_farm(self, client, farmer_token, farm2):
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": farm2.id, "number_of_observations": 2},
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, client, farm):
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": farm.id, "number_of_observations": 2},
        )
        assert resp.status_code == 401

    def test_nonexistent_farm_returns_404(self, client, admin_token):
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": 99999, "number_of_observations": 1},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    def test_with_crop_cycle_id(self, client, farmer_token, farm, crop_cycle):
        resp = client.post(
            "/satellite/simulate",
            json={
                "farm_id": farm.id,
                "crop_cycle_id": crop_cycle.id,
                "number_of_observations": 2,
            },
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 201
        for obs in resp.json()["observations"]:
            assert obs["crop_cycle_id"] == crop_cycle.id

    def test_verifier_can_simulate(self, client, verifier_token, farm):
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": farm.id, "number_of_observations": 2},
            headers={"Authorization": f"Bearer {verifier_token}"},
        )
        assert resp.status_code == 201


class TestSatelliteList:
    def test_list_returns_created_observations(
        self, client, farmer_token, farm, satellite_observations
    ):
        resp = client.get(
            f"/satellite/{farm.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5

    def test_list_sorted_by_date(self, client, farmer_token, farm, satellite_observations):
        resp = client.get(
            f"/satellite/{farm.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        dates = [o["observation_date"] for o in resp.json()]
        assert dates == sorted(dates)

    def test_list_empty_when_none(self, client, farmer_token, farm):
        resp = client.get(
            f"/satellite/{farm.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_admin_can_list_any_farm(self, client, admin_token, farm, satellite_observations):
        resp = client.get(
            f"/satellite/{farm.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    def test_farmer_cannot_list_other_farm(self, client, farmer_token, farm2):
        resp = client.get(
            f"/satellite/{farm2.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 403

    def test_nonexistent_farm_404(self, client, admin_token):
        resp = client.get(
            "/satellite/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404
