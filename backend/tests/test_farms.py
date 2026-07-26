"""
Phase 2 — Farm tests
Covers: POST /farms, GET /farms, GET /farms/{farm_id}
        and role-based visibility.
"""
import pytest

AUTH = lambda t: {"Authorization": f"Bearer {t}"}

VALID_FARM = dict(
    farm_name="Green Paddy Farm",
    land_area_acres=4.5,
    latitude=18.52,
    longitude=73.85,
    village="Shivpur",
    district="Pune",
    state="Maharashtra",
    soil_type="Loamy",
    water_source="Canal",
)


class TestCreateFarm:
    def test_farmer_can_create_farm(self, client, farmer_user, farmer_token):
        resp = client.post("/farms", json=VALID_FARM, headers=AUTH(farmer_token))
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["farmer_id"] == farmer_user.id
        assert data["farm_name"] == "Green Paddy Farm"
        assert data["is_approved"] is False
        assert data["fpo_id"] is None
        assert "id" in data and "created_at" in data

    def test_farm_defaults_not_approved(self, client, farmer_token):
        resp = client.post("/farms", json=VALID_FARM, headers=AUTH(farmer_token))
        assert resp.status_code == 201
        assert resp.json()["is_approved"] is False

    def test_farmer_can_create_farm_with_fpo(self, client, farmer_token, fpo_profile):
        payload = {**VALID_FARM, "fpo_id": fpo_profile.id}
        resp = client.post("/farms", json=payload, headers=AUTH(farmer_token))
        assert resp.status_code == 201
        assert resp.json()["fpo_id"] == fpo_profile.id

    def test_invalid_fpo_id_rejected(self, client, farmer_token):
        payload = {**VALID_FARM, "fpo_id": 99999}
        resp = client.post("/farms", json=payload, headers=AUTH(farmer_token))
        assert resp.status_code == 400

    def test_fpo_cannot_create_farm(self, client, fpo_token, fpo_profile):
        resp = client.post("/farms", json=VALID_FARM, headers=AUTH(fpo_token))
        assert resp.status_code == 403

    def test_admin_cannot_create_farm(self, client, admin_token, admin_user):
        resp = client.post("/farms", json=VALID_FARM, headers=AUTH(admin_token))
        assert resp.status_code == 403

    def test_unauthenticated_cannot_create_farm(self, client):
        resp = client.post("/farms", json=VALID_FARM)
        assert resp.status_code == 401

    def test_invalid_land_area_zero(self, client, farmer_token):
        payload = {**VALID_FARM, "land_area_acres": 0}
        resp = client.post("/farms", json=payload, headers=AUTH(farmer_token))
        assert resp.status_code == 422

    def test_invalid_land_area_negative(self, client, farmer_token):
        payload = {**VALID_FARM, "land_area_acres": -3.0}
        resp = client.post("/farms", json=payload, headers=AUTH(farmer_token))
        assert resp.status_code == 422

    def test_invalid_latitude_too_high(self, client, farmer_token):
        payload = {**VALID_FARM, "latitude": 91.0}
        resp = client.post("/farms", json=payload, headers=AUTH(farmer_token))
        assert resp.status_code == 422

    def test_invalid_latitude_too_low(self, client, farmer_token):
        payload = {**VALID_FARM, "latitude": -91.0}
        resp = client.post("/farms", json=payload, headers=AUTH(farmer_token))
        assert resp.status_code == 422

    def test_invalid_longitude_too_high(self, client, farmer_token):
        payload = {**VALID_FARM, "longitude": 181.0}
        resp = client.post("/farms", json=payload, headers=AUTH(farmer_token))
        assert resp.status_code == 422

    def test_invalid_longitude_too_low(self, client, farmer_token):
        payload = {**VALID_FARM, "longitude": -181.0}
        resp = client.post("/farms", json=payload, headers=AUTH(farmer_token))
        assert resp.status_code == 422

    def test_missing_required_field(self, client, farmer_token):
        payload = {k: v for k, v in VALID_FARM.items() if k != "farm_name"}
        resp = client.post("/farms", json=payload, headers=AUTH(farmer_token))
        assert resp.status_code == 422


class TestListFarms:
    def test_farmer_sees_only_own_farms(self, client, farmer_token, farmer_user,
                                        farm, farm2):
        resp = client.get("/farms", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        ids = [f["id"] for f in resp.json()]
        assert farm.id in ids
        assert farm2.id not in ids

    def test_farmer2_sees_only_own_farms(self, client, farmer2_token, farmer2_user,
                                         farm, farm2):
        resp = client.get("/farms", headers=AUTH(farmer2_token))
        assert resp.status_code == 200
        ids = [f["id"] for f in resp.json()]
        assert farm2.id in ids
        assert farm.id not in ids

    def test_fpo_sees_only_linked_farms(self, client, fpo_token, fpo_profile,
                                        farm_with_fpo, farm):
        resp = client.get("/farms", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        ids = [f["id"] for f in resp.json()]
        assert farm_with_fpo.id in ids
        assert farm.id not in ids     # farm has no FPO

    def test_fpo_without_profile_returns_empty(self, client, fpo_user, fpo_token):
        resp = client.get("/farms", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_admin_sees_all_farms(self, client, admin_token, admin_user,
                                  farm, farm2, farm_with_fpo):
        resp = client.get("/farms", headers=AUTH(admin_token))
        assert resp.status_code == 200
        ids = [f["id"] for f in resp.json()]
        assert farm.id in ids
        assert farm2.id in ids
        assert farm_with_fpo.id in ids

    def test_unauthenticated_cannot_list_farms(self, client):
        resp = client.get("/farms")
        assert resp.status_code == 401

    def test_verifier_cannot_list_farms(self, client, verifier_token, verifier_user):
        resp = client.get("/farms", headers=AUTH(verifier_token))
        assert resp.status_code == 403


class TestGetSingleFarm:
    def test_farmer_can_view_own_farm(self, client, farmer_token, farm):
        resp = client.get(f"/farms/{farm.id}", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        assert resp.json()["id"] == farm.id

    def test_farmer_cannot_view_other_farm(self, client, farmer_token, farm2):
        resp = client.get(f"/farms/{farm2.id}", headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_fpo_can_view_linked_farm(self, client, fpo_token, fpo_profile, farm_with_fpo):
        resp = client.get(f"/farms/{farm_with_fpo.id}", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        assert resp.json()["id"] == farm_with_fpo.id

    def test_fpo_cannot_view_unlinked_farm(self, client, fpo_token, fpo_profile, farm2):
        resp = client.get(f"/farms/{farm2.id}", headers=AUTH(fpo_token))
        assert resp.status_code == 403

    def test_admin_can_view_any_farm(self, client, admin_token, admin_user, farm2):
        resp = client.get(f"/farms/{farm2.id}", headers=AUTH(admin_token))
        assert resp.status_code == 200

    def test_farm_not_found(self, client, farmer_token):
        resp = client.get("/farms/99999", headers=AUTH(farmer_token))
        assert resp.status_code == 404
