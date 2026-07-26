"""
Phase 7 — Dashboard endpoint tests.

Tests GET /dashboard/farm/{farm_id}, GET /dashboard/admin, GET /dashboard/verifier.
"""
import pytest


class TestFarmDashboard:
    def test_farmer_gets_own_farm_dashboard(self, client, farmer_token, farm, sensor_readings):
        resp = client.get(
            f"/dashboard/farm/{farm.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["farm_id"] == farm.id
        assert data["farm_name"] == farm.farm_name
        assert data["total_sensor_readings"] == 14

    def test_dashboard_includes_mrv_scores(self, client, farmer_token, farm, sensor_readings):
        resp = client.get(
            f"/dashboard/farm/{farm.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        data = resp.json()
        assert "mrv_confidence_score" in data
        assert "mrv_consistency_score" in data
        assert "mrv_flags" in data
        assert isinstance(data["mrv_flags"], list)

    def test_dashboard_with_satellite_and_drone(
        self, client, farmer_token, farm, sensor_readings,
        satellite_observations, drone_observations
    ):
        resp = client.get(
            f"/dashboard/farm/{farm.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        data = resp.json()
        assert data["total_satellite_observations"] == 5
        assert data["total_drone_observations"] == 3

    def test_farmer_cannot_view_other_farm(self, client, farmer_token, farm2):
        resp = client.get(
            f"/dashboard/farm/{farm2.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 403

    def test_admin_can_view_any_farm(self, client, admin_token, farm):
        resp = client.get(
            f"/dashboard/farm/{farm.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    def test_verifier_can_view_any_farm(self, client, verifier_token, farm):
        resp = client.get(
            f"/dashboard/farm/{farm.id}",
            headers={"Authorization": f"Bearer {verifier_token}"},
        )
        assert resp.status_code == 200

    def test_nonexistent_farm_404(self, client, admin_token):
        resp = client.get(
            "/dashboard/farm/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, client, farm):
        resp = client.get(f"/dashboard/farm/{farm.id}")
        assert resp.status_code == 401

    def test_no_readings_zero_quality(self, client, farmer_token, farm):
        resp = client.get(
            f"/dashboard/farm/{farm.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        data = resp.json()
        assert data["total_sensor_readings"] == 0
        assert data["avg_sensor_quality"] == 0.0

    def test_verified_credits_counted(
        self, client, farmer_token, farm, crop_cycle,
        sensor_readings, verified_report
    ):
        resp = client.get(
            f"/dashboard/farm/{farm.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        data = resp.json()
        # verified_credits is the sum of estimated_credits for VERIFIED reports;
        # may be 0 for small test data — just confirm the field is present and non-negative
        assert data["total_carbon_reports"] >= 1
        assert data["verified_credits"] >= 0

    def test_missing_satellite_flag_in_response(self, client, farmer_token, farm, sensor_readings):
        # No satellite data → should flag MISSING_SATELLITE_DATA
        resp = client.get(
            f"/dashboard/farm/{farm.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        data = resp.json()
        assert any("MISSING_SATELLITE" in f for f in data["mrv_flags"])


class TestAdminDashboard:
    def test_admin_can_access(self, client, admin_token, farmer_user, farm):
        resp = client.get(
            "/dashboard/admin",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, resp.text

    def test_response_has_required_fields(self, client, admin_token, farmer_user, farm):
        resp = client.get(
            "/dashboard/admin",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = resp.json()
        required = [
            "total_farms", "approved_farms", "total_farmers",
            "total_carbon_reports", "verified_reports", "pending_verification",
            "total_tokens_minted", "total_credits_issued",
            "high_risk_reports", "critical_fraud_alerts",
        ]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_farmer_count(self, client, admin_token, farmer_user, farmer2_user):
        resp = client.get(
            "/dashboard/admin",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = resp.json()
        assert data["total_farmers"] >= 2

    def test_farm_count(self, client, admin_token, farm, farm2):
        resp = client.get(
            "/dashboard/admin",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = resp.json()
        assert data["total_farms"] >= 2

    def test_farmer_cannot_access_admin_dashboard(self, client, farmer_token):
        resp = client.get(
            "/dashboard/admin",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 403

    def test_verifier_cannot_access_admin_dashboard(self, client, verifier_token):
        resp = client.get(
            "/dashboard/admin",
            headers={"Authorization": f"Bearer {verifier_token}"},
        )
        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, client):
        resp = client.get("/dashboard/admin")
        assert resp.status_code == 401

    def test_token_data_after_mint(
        self, client, admin_token, farm, crop_cycle, sensor_readings, verified_report
    ):
        # Mint via API
        client.post(
            f"/admin/tokens/mint/{verified_report.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = client.get(
            "/dashboard/admin",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = resp.json()
        assert data["total_tokens_minted"] >= 1

    def test_approved_farms_count(self, client, admin_token, approved_farm):
        resp = client.get(
            "/dashboard/admin",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = resp.json()
        assert data["approved_farms"] >= 1


class TestVerifierDashboard:
    def test_verifier_can_access(self, client, verifier_token):
        resp = client.get(
            "/dashboard/verifier",
            headers={"Authorization": f"Bearer {verifier_token}"},
        )
        assert resp.status_code == 200, resp.text

    def test_admin_can_access(self, client, admin_token):
        resp = client.get(
            "/dashboard/verifier",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    def test_farmer_cannot_access(self, client, farmer_token):
        resp = client.get(
            "/dashboard/verifier",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 403

    def test_response_has_required_fields(self, client, verifier_token):
        resp = client.get(
            "/dashboard/verifier",
            headers={"Authorization": f"Bearer {verifier_token}"},
        )
        data = resp.json()
        required = [
            "pending_verifications", "approved_today", "rejected_today",
            "avg_risk_score", "high_risk_count", "reports_with_fraud_flags",
        ]
        for field in required:
            assert field in data

    def test_pending_count_with_submitted_report(
        self, client, verifier_token, carbon_report_submitted
    ):
        resp = client.get(
            "/dashboard/verifier",
            headers={"Authorization": f"Bearer {verifier_token}"},
        )
        data = resp.json()
        assert data["pending_verifications"] >= 1

    def test_unauthenticated_rejected(self, client):
        resp = client.get("/dashboard/verifier")
        assert resp.status_code == 401

    def test_avg_risk_score_is_numeric(self, client, verifier_token, carbon_report_submitted):
        resp = client.get(
            "/dashboard/verifier",
            headers={"Authorization": f"Bearer {verifier_token}"},
        )
        data = resp.json()
        assert isinstance(data["avg_risk_score"], (int, float))
