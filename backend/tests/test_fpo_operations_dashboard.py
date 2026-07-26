"""
Phase 15 — FPO Operations Dashboard tests
GET /fpo/operations-dashboard
"""
import pytest

AUTH = lambda t: {"Authorization": f"Bearer {t}"}


class TestFPOOperationsDashboard:
    def test_fpo_gets_dashboard(self, client, fpo_token, fpo_profile):
        resp = client.get("/fpo/operations-dashboard", headers=AUTH(fpo_token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "fpo_id" in data
        assert "fpo_name" in data
        assert "summary" in data
        assert "action_queue" in data
        assert "recent_evidence" in data
        assert "risk_alerts" in data

    def test_summary_keys_present(self, client, fpo_token, fpo_profile):
        resp = client.get("/fpo/operations-dashboard", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        summary = resp.json()["summary"]
        for key in ("total_farmers", "total_farms", "total_crop_cycles",
                    "total_reports", "total_tokens", "total_payouts"):
            assert key in summary, f"Missing key: {key}"

    def test_action_queue_keys_present(self, client, fpo_token, fpo_profile):
        resp = client.get("/fpo/operations-dashboard", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        aq = resp.json()["action_queue"]
        assert "farms_pending_approval" in aq
        assert "mintable_reports" in aq
        assert "initiated_payouts" in aq

    def test_farmer_cannot_access_dashboard(self, client, farmer_token):
        resp = client.get("/fpo/operations-dashboard", headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_verifier_cannot_access_dashboard(self, client, verifier_token):
        resp = client.get("/fpo/operations-dashboard", headers=AUTH(verifier_token))
        assert resp.status_code == 403

    def test_unauthenticated_cannot_access_dashboard(self, client):
        resp = client.get("/fpo/operations-dashboard")
        assert resp.status_code == 401

    def test_fpo_without_profile_gets_404(self, client, fpo2_token):
        """FPO user with no profile should get 404."""
        resp = client.get("/fpo/operations-dashboard", headers=AUTH(fpo2_token))
        assert resp.status_code == 404

    def test_fpo_name_matches_profile(self, client, fpo_token, fpo_profile):
        resp = client.get("/fpo/operations-dashboard", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["fpo_id"] == fpo_profile.id
        assert data["fpo_name"] == fpo_profile.organization_name

    def test_farm_pending_approval_appears_in_action_queue(
        self, client, fpo_token, fpo_profile, farmer_user, farmer_token
    ):
        """A farm in PENDING_APPROVAL status should appear in farms_pending_approval."""
        # Register a farm linked to this FPO (starts as DRAFT → farmer submits → PENDING_APPROVAL)
        farm_resp = client.post("/farms/", json={
            "farm_name": "Dashboard Test Farm",
            "village": "Testville",
            "district": "Pune",
            "state": "Maharashtra",
            "land_area_acres": 3.0,
            "latitude": 18.52,
            "longitude": 73.85,
            "soil_type": "Clay",
            "water_source": "Canal",
            "fpo_id": fpo_profile.id,
        }, headers=AUTH(farmer_token))
        assert farm_resp.status_code == 201, farm_resp.text
        farm_id = farm_resp.json()["id"]
        # Farm linked to fpo_id starts in PENDING_APPROVAL automatically

        # Dashboard should include this farm
        dash_resp = client.get("/fpo/operations-dashboard", headers=AUTH(fpo_token))
        assert dash_resp.status_code == 200
        pending = dash_resp.json()["action_queue"]["farms_pending_approval"]
        farm_ids_in_queue = [f["id"] for f in pending]
        assert farm_id in farm_ids_in_queue

    def test_summary_counts_reflect_approved_farms(
        self, client, fpo_token, fpo_profile, farmer_user, farmer_token
    ):
        """Total farms in summary includes all farms linked to FPO."""
        # Get baseline
        baseline = client.get("/fpo/operations-dashboard", headers=AUTH(fpo_token)).json()
        baseline_farms = baseline["summary"]["total_farms"]

        # Add a new farm
        farm_resp = client.post("/farms/", json={
            "farm_name": "Count Test Farm",
            "village": "Countville",
            "district": "Nashik",
            "state": "Maharashtra",
            "land_area_acres": 2.5,
            "latitude": 19.99,
            "longitude": 73.79,
            "soil_type": "Loam",
            "water_source": "Borewell",
            "fpo_id": fpo_profile.id,
        }, headers=AUTH(farmer_token))
        assert farm_resp.status_code == 201, farm_resp.text

        # Dashboard total_farms should increase by 1
        dash_resp = client.get("/fpo/operations-dashboard", headers=AUTH(fpo_token))
        assert dash_resp.status_code == 200
        new_total = dash_resp.json()["summary"]["total_farms"]
        assert new_total == baseline_farms + 1
