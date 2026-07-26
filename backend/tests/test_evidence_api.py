"""
Phase 4 — Evidence API tests
Covers: POST /evidence, GET /evidence/farm/{id}, GET /evidence/crop-cycle/{id}

Role rules (enforced in _assert_upload_access):
  ADMIN   — can upload to any farm
  FPO     — can upload to their linked farms only
  FARMER  — BLOCKED (403) on all upload endpoints; view-only
  VERIFIER— BLOCKED (403) on all upload endpoints; view-only
"""
import pytest

AUTH = lambda t: {"Authorization": f"Bearer {t}"}

VALID_EVIDENCE = dict(
    file_url="https://example.com/field-photo.jpg",
    file_type="IMAGE",
    description="Paddy field showing AWD water level",
)


def _payload(farm_id, cycle_id, **overrides):
    return {"farm_id": farm_id, "crop_cycle_id": cycle_id, **VALID_EVIDENCE, **overrides}


class TestUploadEvidence:
    def test_farmer_cannot_upload_evidence(self, client, farmer_user, farmer_token,
                                           farm, crop_cycle):
        """FARMER role is blocked from all upload endpoints (view-only)."""
        resp = client.post("/evidence", json=_payload(farm.id, crop_cycle.id),
                           headers=AUTH(farmer_token))
        assert resp.status_code == 403, resp.text
        assert "Farmers cannot upload" in resp.json()["detail"]

    def test_fpo_can_upload_linked_farm_evidence(self, client, farmer_token, fpo_token,
                                                  fpo_profile, farm_with_fpo, crop_cycle):
        # crop_cycle belongs to farm (not farm_with_fpo), create one for farm_with_fpo
        resp_cycle = client.post(
            f"/farms/{farm_with_fpo.id}/crop-cycles",
            json=dict(crop_type="Paddy", season="Kharif", start_date="2024-06-01",
                      baseline_method="AWD", reduction_practice="SRI"),
            headers=AUTH(farmer_token),
        )
        assert resp_cycle.status_code == 201
        cycle_id = resp_cycle.json()["id"]
        resp = client.post("/evidence", json=_payload(farm_with_fpo.id, cycle_id),
                           headers=AUTH(fpo_token))
        assert resp.status_code == 201

    def test_admin_can_upload_any_farm_evidence(self, client, admin_token, admin_user,
                                                 farm, crop_cycle):
        resp = client.post("/evidence", json=_payload(farm.id, crop_cycle.id),
                           headers=AUTH(admin_token))
        assert resp.status_code == 201

    def test_verifier_cannot_upload_evidence(self, client, verifier_token, verifier_user,
                                              farm, crop_cycle):
        resp = client.post("/evidence", json=_payload(farm.id, crop_cycle.id),
                           headers=AUTH(verifier_token))
        assert resp.status_code == 403

    def test_farmer_cannot_upload_other_farm_evidence(self, client, farmer2_token,
                                                       farm, crop_cycle):
        """Farmer is blocked regardless of which farm — role check fires first."""
        resp = client.post("/evidence", json=_payload(farm.id, crop_cycle.id),
                           headers=AUTH(farmer2_token))
        assert resp.status_code == 403

    def test_invalid_farm_id_rejected(self, client, admin_token, crop_cycle):
        """Admin used here — farmer would 403 before the farm lookup."""
        resp = client.post("/evidence", json=_payload(99999, crop_cycle.id),
                           headers=AUTH(admin_token))
        assert resp.status_code == 404

    def test_invalid_crop_cycle_id_rejected(self, client, admin_token, farm):
        """Admin used here — farmer would 403 before the cycle lookup."""
        resp = client.post("/evidence", json=_payload(farm.id, 99999),
                           headers=AUTH(admin_token))
        assert resp.status_code == 404

    def test_cycle_not_belonging_to_farm_rejected(self, client, admin_token,
                                                   farm, crop_cycle2):
        """Admin used here — farmer would 403 before the cross-farm check."""
        # crop_cycle2 belongs to farm2
        resp = client.post("/evidence", json=_payload(farm.id, crop_cycle2.id),
                           headers=AUTH(admin_token))
        assert resp.status_code == 400

    def test_unauthenticated_rejected(self, client, farm, crop_cycle):
        resp = client.post("/evidence", json=_payload(farm.id, crop_cycle.id))
        assert resp.status_code == 401

    def test_empty_file_url_rejected(self, client, admin_token, farm, crop_cycle):
        """Admin used here — farmer would 403 before schema validation."""
        resp = client.post("/evidence",
                           json=_payload(farm.id, crop_cycle.id, file_url="   "),
                           headers=AUTH(admin_token))
        assert resp.status_code == 422

    def test_multiple_evidence_files_allowed(self, client, admin_token, farm, crop_cycle):
        """Admin uploads multiple files — farmer cannot upload at all."""
        for i in range(3):
            r = client.post("/evidence",
                            json=_payload(farm.id, crop_cycle.id,
                                         file_url=f"https://example.com/photo{i}.jpg"),
                            headers=AUTH(admin_token))
            assert r.status_code == 201


class TestGetEvidenceByFarm:
    def test_farmer_gets_own_farm_evidence(self, client, admin_token, farmer_token,
                                           farm, crop_cycle):
        """Evidence is seeded by admin (farmer cannot upload); farmer can still view."""
        client.post("/evidence", json=_payload(farm.id, crop_cycle.id),
                    headers=AUTH(admin_token))
        resp = client.get(f"/evidence/farm/{farm.id}", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_farmer_cannot_get_other_farm_evidence(self, client, farmer2_token, farm):
        resp = client.get(f"/evidence/farm/{farm.id}", headers=AUTH(farmer2_token))
        assert resp.status_code == 403

    def test_verifier_can_get_any_farm_evidence(self, client, verifier_token, verifier_user,
                                                  admin_token, farm, crop_cycle):
        """Evidence seeded by admin; verifier reads it."""
        client.post("/evidence", json=_payload(farm.id, crop_cycle.id),
                    headers=AUTH(admin_token))
        resp = client.get(f"/evidence/farm/{farm.id}", headers=AUTH(verifier_token))
        assert resp.status_code == 200

    def test_admin_can_get_any_farm_evidence(self, client, admin_token, admin_user,
                                               farm, crop_cycle):
        """Admin uploads and reads back."""
        client.post("/evidence", json=_payload(farm.id, crop_cycle.id),
                    headers=AUTH(admin_token))
        resp = client.get(f"/evidence/farm/{farm.id}", headers=AUTH(admin_token))
        assert resp.status_code == 200

    def test_farm_not_found(self, client, farmer_token):
        resp = client.get("/evidence/farm/99999", headers=AUTH(farmer_token))
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client, farm):
        resp = client.get(f"/evidence/farm/{farm.id}")
        assert resp.status_code == 401


class TestGetEvidenceByCropCycle:
    def test_farmer_gets_own_cycle_evidence(self, client, admin_token, farmer_token,
                                            farm, crop_cycle):
        """Evidence seeded by admin; farmer reads own cycle."""
        client.post("/evidence", json=_payload(farm.id, crop_cycle.id),
                    headers=AUTH(admin_token))
        resp = client.get(f"/evidence/crop-cycle/{crop_cycle.id}", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_farmer_cannot_access_other_cycle(self, client, farmer2_token, crop_cycle):
        resp = client.get(f"/evidence/crop-cycle/{crop_cycle.id}", headers=AUTH(farmer2_token))
        assert resp.status_code == 403

    def test_verifier_can_access_any_cycle_evidence(self, client, verifier_token, verifier_user,
                                                      crop_cycle):
        resp = client.get(f"/evidence/crop-cycle/{crop_cycle.id}", headers=AUTH(verifier_token))
        assert resp.status_code == 200

    def test_cycle_not_found(self, client, farmer_token):
        resp = client.get("/evidence/crop-cycle/99999", headers=AUTH(farmer_token))
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client, crop_cycle):
        resp = client.get(f"/evidence/crop-cycle/{crop_cycle.id}")
        assert resp.status_code == 401
