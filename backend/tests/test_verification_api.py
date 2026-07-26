"""
Phase 4 — Verification API tests.
Covers: GET /verification/pending,
        GET /verification/{id},
        POST /verification/{id}/approve,
        POST /verification/{id}/reject
"""
import pytest

AUTH = lambda t: {"Authorization": f"Bearer {t}"}


def _submit_report(client, token, crop_cycle_id):
    """Helper: generate + submit a carbon report, return report data."""
    gen = client.post(f"/carbon-reports/generate/{crop_cycle_id}", headers=AUTH(token))
    assert gen.status_code == 201, gen.text
    report_id = gen.json()["id"]
    sub = client.post(f"/carbon-reports/{report_id}/submit", headers=AUTH(token))
    assert sub.status_code == 200, sub.text
    return sub.json()


class TestGetPendingVerifications:
    def test_verifier_sees_pending_requests(self, client, verifier_token, verifier_user,
                                             farmer_token, farm, crop_cycle, sensor_readings):
        _submit_report(client, farmer_token, crop_cycle.id)
        resp = client.get("/verification/pending", headers=AUTH(verifier_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert all(r["status"] == "PENDING" for r in data)

    def test_farmer_cannot_see_pending(self, client, farmer_token):
        resp = client.get("/verification/pending", headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_admin_cannot_see_pending(self, client, admin_token, admin_user):
        resp = client.get("/verification/pending", headers=AUTH(admin_token))
        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, client):
        resp = client.get("/verification/pending")
        assert resp.status_code == 401

    def test_empty_when_no_submissions(self, client, verifier_token, verifier_user):
        resp = client.get("/verification/pending", headers=AUTH(verifier_token))
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetVerificationById:
    def test_verifier_can_get_verification(self, client, verifier_token, verifier_user,
                                            farmer_token, farm, crop_cycle, sensor_readings):
        _submit_report(client, farmer_token, crop_cycle.id)
        pending = client.get("/verification/pending", headers=AUTH(verifier_token))
        vr_id = pending.json()[0]["id"]
        resp = client.get(f"/verification/{vr_id}", headers=AUTH(verifier_token))
        assert resp.status_code == 200
        assert resp.json()["id"] == vr_id

    def test_admin_can_get_verification(self, client, admin_token, admin_user,
                                         verifier_token, verifier_user,
                                         farmer_token, farm, crop_cycle, sensor_readings):
        _submit_report(client, farmer_token, crop_cycle.id)
        pending = client.get("/verification/pending", headers=AUTH(verifier_token))
        vr_id = pending.json()[0]["id"]
        resp = client.get(f"/verification/{vr_id}", headers=AUTH(admin_token))
        assert resp.status_code == 200

    def test_farmer_cannot_get_verification(self, client, farmer_token, verifier_token,
                                              verifier_user, farm, crop_cycle, sensor_readings):
        _submit_report(client, farmer_token, crop_cycle.id)
        pending = client.get("/verification/pending", headers=AUTH(verifier_token))
        vr_id = pending.json()[0]["id"]
        resp = client.get(f"/verification/{vr_id}", headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_not_found(self, client, verifier_token, verifier_user):
        resp = client.get("/verification/99999", headers=AUTH(verifier_token))
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client):
        resp = client.get("/verification/1")
        assert resp.status_code == 401


class TestApproveVerification:
    def test_verifier_can_approve(self, client, verifier_token, verifier_user,
                                   farmer_token, farm, crop_cycle, sensor_readings):
        report = _submit_report(client, farmer_token, crop_cycle.id)
        pending = client.get("/verification/pending", headers=AUTH(verifier_token))
        vr_id = pending.json()[0]["id"]
        resp = client.post(f"/verification/{vr_id}/approve", headers=AUTH(verifier_token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "APPROVED"
        # report status should be VERIFIED
        rep = client.get(f"/carbon-reports/{report['id']}", headers=AUTH(verifier_token))
        assert rep.json()["status"] == "VERIFIED"

    def test_farmer_cannot_approve(self, client, farmer_token, verifier_token, verifier_user,
                                    farm, crop_cycle, sensor_readings):
        _submit_report(client, farmer_token, crop_cycle.id)
        pending = client.get("/verification/pending", headers=AUTH(verifier_token))
        vr_id = pending.json()[0]["id"]
        resp = client.post(f"/verification/{vr_id}/approve", headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_admin_cannot_approve(self, client, admin_token, admin_user, verifier_token,
                                   verifier_user, farmer_token, farm, crop_cycle, sensor_readings):
        _submit_report(client, farmer_token, crop_cycle.id)
        pending = client.get("/verification/pending", headers=AUTH(verifier_token))
        vr_id = pending.json()[0]["id"]
        resp = client.post(f"/verification/{vr_id}/approve", headers=AUTH(admin_token))
        assert resp.status_code == 403

    def test_cannot_approve_already_approved(self, client, verifier_token, verifier_user,
                                              farmer_token, farm, crop_cycle, sensor_readings):
        _submit_report(client, farmer_token, crop_cycle.id)
        pending = client.get("/verification/pending", headers=AUTH(verifier_token))
        vr_id = pending.json()[0]["id"]
        client.post(f"/verification/{vr_id}/approve", headers=AUTH(verifier_token))
        resp = client.post(f"/verification/{vr_id}/approve", headers=AUTH(verifier_token))
        assert resp.status_code == 400

    def test_not_found_approve(self, client, verifier_token, verifier_user):
        resp = client.post("/verification/99999/approve", headers=AUTH(verifier_token))
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client):
        resp = client.post("/verification/1/approve")
        assert resp.status_code == 401


class TestRejectVerification:
    def test_verifier_can_reject_with_remarks(self, client, verifier_token, verifier_user,
                                               farmer_token, farm, crop_cycle, sensor_readings):
        report = _submit_report(client, farmer_token, crop_cycle.id)
        pending = client.get("/verification/pending", headers=AUTH(verifier_token))
        vr_id = pending.json()[0]["id"]
        resp = client.post(f"/verification/{vr_id}/reject",
                           json={"remarks": "Data quality too low"},
                           headers=AUTH(verifier_token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "REJECTED"
        assert "Data quality" in data["remarks"]
        # report should be REJECTED
        rep = client.get(f"/carbon-reports/{report['id']}", headers=AUTH(verifier_token))
        assert rep.json()["status"] == "REJECTED"

    def test_reject_without_remarks_rejected(self, client, verifier_token, verifier_user,
                                              farmer_token, farm, crop_cycle, sensor_readings):
        _submit_report(client, farmer_token, crop_cycle.id)
        pending = client.get("/verification/pending", headers=AUTH(verifier_token))
        vr_id = pending.json()[0]["id"]
        resp = client.post(f"/verification/{vr_id}/reject",
                           json={},
                           headers=AUTH(verifier_token))
        assert resp.status_code == 422

    def test_farmer_cannot_reject(self, client, farmer_token, verifier_token, verifier_user,
                                   farm, crop_cycle, sensor_readings):
        _submit_report(client, farmer_token, crop_cycle.id)
        pending = client.get("/verification/pending", headers=AUTH(verifier_token))
        vr_id = pending.json()[0]["id"]
        resp = client.post(f"/verification/{vr_id}/reject",
                           json={"remarks": "bad"},
                           headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_cannot_reject_already_processed(self, client, verifier_token, verifier_user,
                                              farmer_token, farm, crop_cycle, sensor_readings):
        _submit_report(client, farmer_token, crop_cycle.id)
        pending = client.get("/verification/pending", headers=AUTH(verifier_token))
        vr_id = pending.json()[0]["id"]
        client.post(f"/verification/{vr_id}/approve", headers=AUTH(verifier_token))
        resp = client.post(f"/verification/{vr_id}/reject",
                           json={"remarks": "late rejection"},
                           headers=AUTH(verifier_token))
        assert resp.status_code == 400

    def test_not_found_reject(self, client, verifier_token, verifier_user):
        resp = client.post("/verification/99999/reject",
                           json={"remarks": "not found"},
                           headers=AUTH(verifier_token))
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client):
        resp = client.post("/verification/1/reject", json={"remarks": "x"})
        assert resp.status_code == 401
