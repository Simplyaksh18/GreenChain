"""
Phase 8 — System status endpoint tests.

Tests GET /system/status (no auth required).
"""
import pytest


class TestSystemStatus:
    def test_status_returns_200_no_auth(self, client):
        resp = client.get("/system/status")
        assert resp.status_code == 200, resp.text

    def test_status_fields_present(self, client):
        data = client.get("/system/status").json()
        required = [
            "api_status",
            "database_status",
            "blockchain_mode",
            "blockchain_configured",
            "total_routes",
            "timestamp",
        ]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_api_status_ok(self, client):
        data = client.get("/system/status").json()
        assert data["api_status"] == "ok"

    def test_database_status_ok(self, client):
        data = client.get("/system/status").json()
        assert data["database_status"] == "ok"

    def test_blockchain_mode_is_mock_by_default(self, client):
        data = client.get("/system/status").json()
        assert data["blockchain_mode"] == "mock"

    def test_blockchain_configured_true_for_mock(self, client):
        data = client.get("/system/status").json()
        assert data["blockchain_configured"] is True

    def test_total_routes_positive(self, client):
        data = client.get("/system/status").json()
        assert data["total_routes"] > 0

    def test_timestamp_is_string(self, client):
        data = client.get("/system/status").json()
        assert isinstance(data["timestamp"], str)
        # Should be parseable as ISO datetime
        from datetime import datetime
        dt = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        assert dt is not None
