"""
Phase 2 — FPO profile tests
Covers: POST /fpo/profile, GET /fpo/profile, GET /fpo/farms, GET /fpo/farmers
"""
import pytest


AUTH = lambda t: {"Authorization": f"Bearer {t}"}


class TestCreateFPOProfile:
    def test_fpo_can_create_profile(self, client, fpo_user, fpo_token):
        resp = client.post("/fpo/profile", json={
            "organization_name": "GreenFPO",
            "registration_number": "REG-001",
            "district": "Pune",
            "state": "Maharashtra",
        }, headers=AUTH(fpo_token))
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["user_id"] == fpo_user.id
        assert data["organization_name"] == "GreenFPO"
        assert data["registration_number"] == "REG-001"
        assert data["district"] == "Pune"
        assert data["state"] == "Maharashtra"
        assert "id" in data
        assert "created_at" in data

    def test_fpo_cannot_create_duplicate_profile(self, client, fpo_user, fpo_token, fpo_profile):
        resp = client.post("/fpo/profile", json={
            "organization_name": "GreenFPO2",
            "registration_number": "REG-999",
            "district": "Mumbai",
            "state": "Maharashtra",
        }, headers=AUTH(fpo_token))
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    def test_duplicate_registration_number_rejected(self, client, fpo_user, fpo_token, fpo_profile,
                                                    fpo2_user, fpo2_token):
        resp = client.post("/fpo/profile", json={
            "organization_name": "AnotherFPO",
            "registration_number": "REG001",   # same as fixture
            "district": "Nagpur",
            "state": "Maharashtra",
        }, headers=AUTH(fpo2_token))
        assert resp.status_code == 400
        assert "registration number" in resp.json()["detail"].lower()

    def test_farmer_cannot_create_fpo_profile(self, client, farmer_token):
        resp = client.post("/fpo/profile", json={
            "organization_name": "X",
            "registration_number": "R1",
            "district": "D",
            "state": "S",
        }, headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_verifier_cannot_create_fpo_profile(self, client, verifier_user, verifier_token):
        resp = client.post("/fpo/profile", json={
            "organization_name": "X",
            "registration_number": "R2",
            "district": "D",
            "state": "S",
        }, headers=AUTH(verifier_token))
        assert resp.status_code == 403

    def test_admin_cannot_create_fpo_profile(self, client, admin_user, admin_token):
        resp = client.post("/fpo/profile", json={
            "organization_name": "X",
            "registration_number": "R3",
            "district": "D",
            "state": "S",
        }, headers=AUTH(admin_token))
        assert resp.status_code == 403

    def test_unauthenticated_cannot_create_fpo_profile(self, client):
        resp = client.post("/fpo/profile", json={
            "organization_name": "X",
            "registration_number": "R4",
            "district": "D",
            "state": "S",
        })
        assert resp.status_code == 401


class TestGetFPOProfile:
    def test_fpo_can_get_own_profile(self, client, fpo_user, fpo_token, fpo_profile):
        resp = client.get("/fpo/profile", headers=AUTH(fpo_token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["user_id"] == fpo_user.id
        assert data["id"] == fpo_profile.id

    def test_fpo_no_profile_returns_404(self, client, fpo_user, fpo_token):
        resp = client.get("/fpo/profile", headers=AUTH(fpo_token))
        assert resp.status_code == 404

    def test_farmer_cannot_get_fpo_profile(self, client, farmer_token):
        resp = client.get("/fpo/profile", headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_unauthenticated_cannot_get_fpo_profile(self, client):
        resp = client.get("/fpo/profile")
        assert resp.status_code == 401


class TestFPOFarmsList:
    def test_fpo_sees_linked_farms(self, client, fpo_token, fpo_profile, farm_with_fpo):
        resp = client.get("/fpo/farms", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == farm_with_fpo.id

    def test_fpo_does_not_see_unlinked_farms(self, client, fpo_token, fpo_profile, farm):
        # farm has no FPO linked
        resp = client.get("/fpo/farms", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_fpo_no_profile_returns_404(self, client, fpo_user, fpo_token):
        resp = client.get("/fpo/farms", headers=AUTH(fpo_token))
        assert resp.status_code == 404

    def test_farmer_cannot_list_fpo_farms(self, client, farmer_token):
        resp = client.get("/fpo/farms", headers=AUTH(farmer_token))
        assert resp.status_code == 403


class TestFPOFarmersList:
    def test_fpo_sees_farmers_of_linked_farms(self, client, fpo_token, fpo_profile,
                                              farmer_user, farm_with_fpo):
        resp = client.get("/fpo/farmers", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == farmer_user.id

    def test_fpo_empty_if_no_farms(self, client, fpo_token, fpo_profile):
        resp = client.get("/fpo/farmers", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_farmer_cannot_list_fpo_farmers(self, client, farmer_token):
        resp = client.get("/fpo/farmers", headers=AUTH(farmer_token))
        assert resp.status_code == 403
