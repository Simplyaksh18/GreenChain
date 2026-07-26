"""
Phase 8 — Mobile dashboard tests.

Tests GET /mobile/dashboard for all four roles.
"""
import pytest


class TestMobileDashboardFarmer:
    def test_farmer_gets_dashboard(self, client, farmer_token, farm):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        assert "data" in body
        data = body["data"]
        assert data["role"] == "FARMER"
        assert "data" in data

    def test_farmer_dashboard_fields(self, client, farmer_token, farm, sensor_readings):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        inner = resp.json()["data"]["data"]
        required = [
            "my_farms_count",
            "approved_farms_count",
            "active_crop_cycles",
            "total_sensor_readings",
            "avg_sensor_quality",
            "total_carbon_reports",
            "verified_reports",
            "token_count",
            "total_credits",
            "latest_mrv_confidence",
        ]
        for field in required:
            assert field in inner, f"Missing field: {field}"

    def test_farmer_farm_count(self, client, farmer_token, farm):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        inner = resp.json()["data"]["data"]
        assert inner["my_farms_count"] >= 1

    def test_farmer_sensor_count(self, client, farmer_token, farm, sensor_readings):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        inner = resp.json()["data"]["data"]
        assert inner["total_sensor_readings"] == 14

    def test_farmer_token_count(
        self, client, farmer_token, farm, crop_cycle, sensor_readings,
        verified_report, minted_token
    ):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        inner = resp.json()["data"]["data"]
        assert inner["token_count"] >= 1

    def test_farmer_no_farms_zero_counts(self, client, farmer2_token):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {farmer2_token}"},
        )
        inner = resp.json()["data"]["data"]
        assert inner["my_farms_count"] == 0
        assert inner["total_sensor_readings"] == 0

    def test_farmer_mrv_confidence_with_satellite(
        self, client, farmer_token, farm, sensor_readings, satellite_observations
    ):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        inner = resp.json()["data"]["data"]
        assert inner["latest_mrv_confidence"] is not None
        assert 0 <= inner["latest_mrv_confidence"] <= 100


class TestMobileDashboardFPO:
    def test_fpo_gets_dashboard(self, client, fpo_token, fpo_profile):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {fpo_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["role"] == "FPO"

    def test_fpo_dashboard_fields(self, client, fpo_token, fpo_profile):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {fpo_token}"},
        )
        inner = resp.json()["data"]["data"]
        required = [
            "linked_farms_count",
            "approved_linked_farms",
            "farmers_count",
            "pending_reports",
            "high_risk_farms",
        ]
        for field in required:
            assert field in inner

    def test_fpo_linked_farm_count(self, client, fpo_token, fpo_profile, farm_with_fpo):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {fpo_token}"},
        )
        inner = resp.json()["data"]["data"]
        assert inner["linked_farms_count"] >= 1

    def test_fpo_no_profile_zero_counts(self, client, fpo2_token):
        # fpo2 has no farms linked
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {fpo2_token}"},
        )
        inner = resp.json()["data"]["data"]
        assert inner["linked_farms_count"] == 0


class TestMobileDashboardVerifier:
    def test_verifier_gets_dashboard(self, client, verifier_token):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {verifier_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["role"] == "VERIFIER"

    def test_verifier_dashboard_fields(self, client, verifier_token):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {verifier_token}"},
        )
        inner = resp.json()["data"]["data"]
        required = [
            "pending_verifications",
            "high_risk_reports",
            "approved_today",
            "rejected_today",
        ]
        for field in required:
            assert field in inner

    def test_verifier_pending_count(self, client, verifier_token, carbon_report_submitted):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {verifier_token}"},
        )
        inner = resp.json()["data"]["data"]
        assert inner["pending_verifications"] >= 1


class TestMobileDashboardAdmin:
    def test_admin_gets_dashboard(self, client, admin_token):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["role"] == "ADMIN"

    def test_admin_dashboard_fields(self, client, admin_token):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        inner = resp.json()["data"]["data"]
        required = [
            "total_farms",
            "total_users",
            "total_reports",
            "verified_reports",
            "total_tokens",
            "total_credits",
            "high_risk_reports",
        ]
        for field in required:
            assert field in inner

    def test_admin_farm_count(self, client, admin_token, farm, farm2):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        inner = resp.json()["data"]["data"]
        assert inner["total_farms"] >= 2

    def test_admin_total_users(self, client, admin_token, farmer_user, fpo_user, verifier_user):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        inner = resp.json()["data"]["data"]
        assert inner["total_users"] >= 4  # admin + farmer + fpo + verifier


class TestMobileDashboardAuth:
    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/mobile/dashboard")
        assert resp.status_code == 401

    def test_response_has_standard_envelope(self, client, farmer_token):
        resp = client.get(
            "/mobile/dashboard",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        body = resp.json()
        assert "success" in body
        assert "message" in body
        assert "data" in body
        assert body["success"] is True
