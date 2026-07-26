"""
Phase 2 — FPO farm approval tests
Covers: POST /fpo/farms/{farm_id}/approve
"""
import pytest

AUTH = lambda t: {"Authorization": f"Bearer {t}"}


class TestFPOApproval:
    def test_fpo_can_approve_linked_farm(self, client, fpo_token, fpo_profile, farm_with_fpo):
        # farm_with_fpo starts as not approved
        assert farm_with_fpo.is_approved is False
        resp = client.post(f"/fpo/farms/{farm_with_fpo.id}/approve", headers=AUTH(fpo_token))
        assert resp.status_code == 200, resp.text
        assert resp.json()["is_approved"] is True

    def test_fpo_cannot_approve_unlinked_farm(self, client, fpo_token, fpo_profile, farm):
        # farm is not linked to fpo_profile
        resp = client.post(f"/fpo/farms/{farm.id}/approve", headers=AUTH(fpo_token))
        assert resp.status_code == 403

    def test_fpo2_cannot_approve_fpo1_farm(self, client, fpo2_token, fpo2_profile, farm_with_fpo):
        # farm_with_fpo belongs to fpo_profile, not fpo2_profile
        resp = client.post(f"/fpo/farms/{farm_with_fpo.id}/approve", headers=AUTH(fpo2_token))
        assert resp.status_code == 403

    def test_farmer_cannot_approve_farm(self, client, farmer_token, farm_with_fpo):
        resp = client.post(f"/fpo/farms/{farm_with_fpo.id}/approve", headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_admin_cannot_use_fpo_approve_route(self, client, admin_token, admin_user, farm_with_fpo):
        resp = client.post(f"/fpo/farms/{farm_with_fpo.id}/approve", headers=AUTH(admin_token))
        assert resp.status_code == 403

    def test_verifier_cannot_approve_farm(self, client, verifier_token, verifier_user, farm_with_fpo):
        resp = client.post(f"/fpo/farms/{farm_with_fpo.id}/approve", headers=AUTH(verifier_token))
        assert resp.status_code == 403

    def test_unauthenticated_cannot_approve(self, client, farm_with_fpo):
        resp = client.post(f"/fpo/farms/{farm_with_fpo.id}/approve")
        assert resp.status_code == 401

    def test_approve_nonexistent_farm(self, client, fpo_token, fpo_profile):
        resp = client.post("/fpo/farms/99999/approve", headers=AUTH(fpo_token))
        assert resp.status_code == 404

    def test_double_approve_remains_approved(self, client, fpo_token, fpo_profile, farm_with_fpo):
        client.post(f"/fpo/farms/{farm_with_fpo.id}/approve", headers=AUTH(fpo_token))
        resp = client.post(f"/fpo/farms/{farm_with_fpo.id}/approve", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        assert resp.json()["is_approved"] is True

    def test_fpo_without_profile_cannot_approve(self, client, fpo2_user, fpo2_token,
                                                fpo_profile, farm_with_fpo):
        # fpo2_user exists but has NO FPO profile — trying to approve should return 404
        # farm_with_fpo is linked to fpo_profile (owned by fpo_user, not fpo2_user)
        resp = client.post(f"/fpo/farms/{farm_with_fpo.id}/approve", headers=AUTH(fpo2_token))
        assert resp.status_code == 404
