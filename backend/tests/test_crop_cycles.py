"""
Phase 2 — Crop cycle tests
Covers: POST /farms/{farm_id}/crop-cycles, GET /farms/{farm_id}/crop-cycles
"""
import pytest

AUTH = lambda t: {"Authorization": f"Bearer {t}"}

VALID_CYCLE = dict(
    crop_type="Paddy",
    season="Kharif",
    start_date="2024-06-01",
    baseline_method="AWD",
    reduction_practice="SRI",
)


class TestCreateCropCycle:
    def test_farmer_can_create_cycle_for_own_farm(self, client, farmer_token, farmer_user, farm):
        resp = client.post(f"/farms/{farm.id}/crop-cycles", json=VALID_CYCLE,
                           headers=AUTH(farmer_token))
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["farm_id"] == farm.id
        assert data["crop_type"] == "Paddy"
        assert data["season"] == "Kharif"
        assert data["status"] == "ACTIVE"
        assert data["end_date"] is None
        assert "id" in data and "created_at" in data

    def test_farmer_can_set_end_date(self, client, farmer_token, farm):
        payload = {**VALID_CYCLE, "end_date": "2024-11-30"}
        resp = client.post(f"/farms/{farm.id}/crop-cycles", json=payload,
                           headers=AUTH(farmer_token))
        assert resp.status_code == 201
        assert resp.json()["end_date"] == "2024-11-30"

    def test_farmer_cannot_create_cycle_for_other_farm(self, client, farmer_token, farm2):
        # farm2 belongs to farmer2, not farmer
        resp = client.post(f"/farms/{farm2.id}/crop-cycles", json=VALID_CYCLE,
                           headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_fpo_cannot_create_crop_cycle(self, client, fpo_token, fpo_profile, farm_with_fpo):
        resp = client.post(f"/farms/{farm_with_fpo.id}/crop-cycles", json=VALID_CYCLE,
                           headers=AUTH(fpo_token))
        assert resp.status_code == 403

    def test_admin_cannot_create_crop_cycle(self, client, admin_token, admin_user, farm):
        resp = client.post(f"/farms/{farm.id}/crop-cycles", json=VALID_CYCLE,
                           headers=AUTH(admin_token))
        assert resp.status_code == 403

    def test_unauthenticated_cannot_create_cycle(self, client, farm):
        resp = client.post(f"/farms/{farm.id}/crop-cycles", json=VALID_CYCLE)
        assert resp.status_code == 401

    def test_crop_cycle_farm_not_found(self, client, farmer_token):
        resp = client.post("/farms/99999/crop-cycles", json=VALID_CYCLE,
                           headers=AUTH(farmer_token))
        assert resp.status_code == 404

    def test_missing_crop_type(self, client, farmer_token, farm):
        payload = {k: v for k, v in VALID_CYCLE.items() if k != "crop_type"}
        resp = client.post(f"/farms/{farm.id}/crop-cycles", json=payload,
                           headers=AUTH(farmer_token))
        assert resp.status_code == 422

    def test_missing_season(self, client, farmer_token, farm):
        payload = {k: v for k, v in VALID_CYCLE.items() if k != "season"}
        resp = client.post(f"/farms/{farm.id}/crop-cycles", json=payload,
                           headers=AUTH(farmer_token))
        assert resp.status_code == 422

    def test_missing_start_date(self, client, farmer_token, farm):
        payload = {k: v for k, v in VALID_CYCLE.items() if k != "start_date"}
        resp = client.post(f"/farms/{farm.id}/crop-cycles", json=payload,
                           headers=AUTH(farmer_token))
        assert resp.status_code == 422

    def test_missing_baseline_method(self, client, farmer_token, farm):
        payload = {k: v for k, v in VALID_CYCLE.items() if k != "baseline_method"}
        resp = client.post(f"/farms/{farm.id}/crop-cycles", json=payload,
                           headers=AUTH(farmer_token))
        assert resp.status_code == 422

    def test_missing_reduction_practice(self, client, farmer_token, farm):
        payload = {k: v for k, v in VALID_CYCLE.items() if k != "reduction_practice"}
        resp = client.post(f"/farms/{farm.id}/crop-cycles", json=payload,
                           headers=AUTH(farmer_token))
        assert resp.status_code == 422

    def test_invalid_date_format(self, client, farmer_token, farm):
        payload = {**VALID_CYCLE, "start_date": "01-06-2024"}
        resp = client.post(f"/farms/{farm.id}/crop-cycles", json=payload,
                           headers=AUTH(farmer_token))
        assert resp.status_code == 422

    def test_farmer_can_create_multiple_cycles(self, client, farmer_token, farm):
        resp1 = client.post(f"/farms/{farm.id}/crop-cycles", json=VALID_CYCLE,
                            headers=AUTH(farmer_token))
        payload2 = {**VALID_CYCLE, "season": "Rabi", "start_date": "2024-11-01"}
        resp2 = client.post(f"/farms/{farm.id}/crop-cycles", json=payload2,
                            headers=AUTH(farmer_token))
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["id"] != resp2.json()["id"]


class TestListCropCycles:
    def _seed_cycle(self, client, farmer_token, farm_id):
        resp = client.post(f"/farms/{farm_id}/crop-cycles", json=VALID_CYCLE,
                           headers=AUTH(farmer_token))
        assert resp.status_code == 201
        return resp.json()

    def test_farmer_can_list_own_crop_cycles(self, client, farmer_token, farm):
        self._seed_cycle(client, farmer_token, farm.id)
        resp = client.get(f"/farms/{farm.id}/crop-cycles", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_farmer_cannot_list_other_farm_cycles(self, client, farmer_token, farm2):
        resp = client.get(f"/farms/{farm2.id}/crop-cycles", headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_fpo_can_list_linked_farm_cycles(self, client, farmer_token, fpo_token,
                                              fpo_profile, farm_with_fpo):
        self._seed_cycle(client, farmer_token, farm_with_fpo.id)
        resp = client.get(f"/farms/{farm_with_fpo.id}/crop-cycles", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_fpo_cannot_list_unlinked_farm_cycles(self, client, fpo_token, fpo_profile, farm):
        resp = client.get(f"/farms/{farm.id}/crop-cycles", headers=AUTH(fpo_token))
        assert resp.status_code == 403

    def test_admin_can_list_any_crop_cycles(self, client, farmer_token, admin_token,
                                            admin_user, farm):
        self._seed_cycle(client, farmer_token, farm.id)
        resp = client.get(f"/farms/{farm.id}/crop-cycles", headers=AUTH(admin_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_unauthenticated_cannot_list_cycles(self, client, farm):
        resp = client.get(f"/farms/{farm.id}/crop-cycles")
        assert resp.status_code == 401

    def test_list_cycles_farm_not_found(self, client, farmer_token):
        resp = client.get("/farms/99999/crop-cycles", headers=AUTH(farmer_token))
        assert resp.status_code == 404


class TestFarmerRoutes:
    def test_get_farmer_me(self, client, farmer_user, farmer_token):
        resp = client.get("/farmers/me", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == farmer_user.id
        assert data["role"] == "FARMER"

    def test_fpo_cannot_access_farmer_me(self, client, fpo_token):
        resp = client.get("/farmers/me", headers=AUTH(fpo_token))
        assert resp.status_code == 403

    def test_get_my_farms(self, client, farmer_token, farm):
        resp = client.get("/farmers/my-farms", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        ids = [f["id"] for f in resp.json()]
        assert farm.id in ids

    def test_my_farms_excludes_other_farmer(self, client, farmer_token, farm2):
        resp = client.get("/farmers/my-farms", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        ids = [f["id"] for f in resp.json()]
        assert farm2.id not in ids

    def test_fpo_cannot_access_my_farms(self, client, fpo_token):
        resp = client.get("/farmers/my-farms", headers=AUTH(fpo_token))
        assert resp.status_code == 403
