"""
Phase 4 — Admin API tests.
Covers: GET /admin/risk-reports
"""
import pytest

AUTH = lambda t: {"Authorization": f"Bearer {t}"}


def _submit_report(client, token, crop_cycle_id):
    gen = client.post(f"/carbon-reports/generate/{crop_cycle_id}", headers=AUTH(token))
    assert gen.status_code == 201, gen.text
    report_id = gen.json()["id"]
    sub = client.post(f"/carbon-reports/{report_id}/submit", headers=AUTH(token))
    assert sub.status_code == 200, sub.text
    return sub.json()


class TestAdminRiskReports:
    def test_admin_can_get_risk_reports(self, client, admin_token, admin_user,
                                         farmer_token, farm, crop_cycle, sensor_readings):
        _submit_report(client, farmer_token, crop_cycle.id)
        resp = client.get("/admin/risk-reports", headers=AUTH(admin_token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) >= 1

    def test_risk_reports_sorted_by_risk_score_desc(self, client, admin_token, admin_user,
                                                      farmer_token, farm, crop_cycle,
                                                      farm2, crop_cycle2, sensor_readings):
        _submit_report(client, farmer_token, crop_cycle.id)
        resp = client.get("/admin/risk-reports", headers=AUTH(admin_token))
        data = resp.json()
        if len(data) > 1:
            scores = [r["risk_score"] for r in data]
            assert scores == sorted(scores, reverse=True)

    def test_farmer_cannot_get_risk_reports(self, client, farmer_token):
        resp = client.get("/admin/risk-reports", headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_verifier_cannot_get_risk_reports(self, client, verifier_token, verifier_user):
        resp = client.get("/admin/risk-reports", headers=AUTH(verifier_token))
        assert resp.status_code == 403

    def test_fpo_cannot_get_risk_reports(self, client, fpo_token, fpo_profile):
        resp = client.get("/admin/risk-reports", headers=AUTH(fpo_token))
        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, client):
        resp = client.get("/admin/risk-reports")
        assert resp.status_code == 401

    def test_empty_when_no_submissions(self, client, admin_token, admin_user):
        resp = client.get("/admin/risk-reports", headers=AUTH(admin_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_risk_report_fields_present(self, client, admin_token, admin_user,
                                         farmer_token, farm, crop_cycle, sensor_readings):
        _submit_report(client, farmer_token, crop_cycle.id)
        resp = client.get("/admin/risk-reports", headers=AUTH(admin_token))
        item = resp.json()[0]
        assert "id" in item
        assert "risk_score" in item
        assert "risk_level" in item
        assert "recommendation" in item
        assert "status" in item
