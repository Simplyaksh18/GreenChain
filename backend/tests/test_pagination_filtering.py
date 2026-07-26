"""
Phase 8 — Pagination and filtering tests.

Tests pagination on:
  GET /farms
  GET /sensors/farm/{farm_id}
  GET /sensors/crop-cycle/{crop_cycle_id}
  GET /carbon-reports/farm/{farm_id}
  GET /tokens/my-wallet
  GET /satellite/{farm_id}
  GET /drone/{farm_id}

Tests filtering on:
  GET /farms  (district, state, is_approved)
  GET /carbon-reports/farm/{farm_id}  (status)
  GET /tokens/my-wallet  (status)
  GET /satellite/{farm_id}  (crop_cycle_id)
  GET /drone/{farm_id}  (crop_cycle_id)
"""
import pytest


# ── /farms pagination & filtering ─────────────────────────────────────────────

class TestFarmsPagination:
    def test_limit_reduces_results(self, client, admin_token, farm, farm2):
        resp = client.get(
            "/farms?limit=1",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_offset_skips_records(self, client, admin_token, farm, farm2):
        all_resp = client.get(
            "/farms",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        total = len(all_resp.json())

        resp = client.get(
            f"/farms?offset={total}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.json() == []

    def test_default_returns_all_farms(self, client, admin_token, farm, farm2):
        resp = client.get(
            "/farms",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert len(resp.json()) >= 2

    def test_limit_offset_pagination(self, client, admin_token, farm, farm2):
        page1 = client.get(
            "/farms?limit=1&offset=0",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()
        page2 = client.get(
            "/farms?limit=1&offset=1",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()
        if len(page1) > 0 and len(page2) > 0:
            assert page1[0]["id"] != page2[0]["id"]


class TestFarmsFiltering:
    def test_filter_by_district(self, client, admin_token, farm):
        resp = client.get(
            f"/farms?district=Pune",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        for f in resp.json():
            assert "pune" in f["district"].lower()

    def test_filter_by_state(self, client, admin_token, farm):
        resp = client.get(
            "/farms?state=Maharashtra",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        for f in resp.json():
            assert "maharashtra" in f["state"].lower()

    def test_filter_by_is_approved_false(self, client, admin_token, farm):
        """Unapproved farm fixture."""
        resp = client.get(
            "/farms?is_approved=false",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        for f in resp.json():
            assert f["is_approved"] is False

    def test_filter_by_is_approved_true(self, client, admin_token, approved_farm):
        resp = client.get(
            "/farms?is_approved=true",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        for f in resp.json():
            assert f["is_approved"] is True

    def test_filter_nonexistent_district_returns_empty(self, client, admin_token, farm):
        resp = client.get(
            "/farms?district=NowhereAtAll",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_no_filter_returns_all(self, client, admin_token, farm, approved_farm):
        resp = client.get(
            "/farms",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert len(resp.json()) >= 2


# ── /sensors pagination ───────────────────────────────────────────────────────

class TestSensorsPagination:
    def test_farm_readings_limit(self, client, farmer_token, farm, sensor_readings):
        resp = client.get(
            f"/sensors/farm/{farm.id}?limit=5",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 5

    def test_farm_readings_offset(self, client, farmer_token, farm, sensor_readings):
        all_resp = client.get(
            f"/sensors/farm/{farm.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        all_ids = [r["id"] for r in all_resp.json()]

        resp = client.get(
            f"/sensors/farm/{farm.id}?offset=5&limit=5",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        page_ids = [r["id"] for r in resp.json()]
        # page should not overlap with first 5
        assert not set(page_ids).intersection(set(all_ids[:5]))

    def test_crop_cycle_readings_limit(self, client, farmer_token, crop_cycle, sensor_readings):
        resp = client.get(
            f"/sensors/crop-cycle/{crop_cycle.id}?limit=3",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_offset_beyond_total_returns_empty(self, client, farmer_token, farm, sensor_readings):
        resp = client.get(
            f"/sensors/farm/{farm.id}?offset=9999",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ── /carbon-reports filtering + pagination ────────────────────────────────────

class TestCarbonReportsFilter:
    def test_filter_by_draft_status(
        self, client, farmer_token, farm, crop_cycle, sensor_readings, carbon_report_draft
    ):
        resp = client.get(
            f"/carbon-reports/farm/{farm.id}?status=DRAFT",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        for r in resp.json():
            assert r["status"] == "DRAFT"

    def test_filter_by_submitted_status(
        self, client, farmer_token, farm, crop_cycle, sensor_readings, carbon_report_submitted
    ):
        resp = client.get(
            f"/carbon-reports/farm/{farm.id}?status=SUBMITTED",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        for r in resp.json():
            assert r["status"] == "SUBMITTED"

    def test_filter_by_verified_status(
        self, client, farmer_token, farm, crop_cycle, sensor_readings, verified_report
    ):
        resp = client.get(
            f"/carbon-reports/farm/{farm.id}?status=VERIFIED",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        for r in resp.json():
            assert r["status"] == "VERIFIED"

    def test_no_filter_returns_all(
        self, client, farmer_token, farm, crop_cycle, sensor_readings, carbon_report_draft
    ):
        resp = client.get(
            f"/carbon-reports/farm/{farm.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_carbon_reports_pagination(
        self, client, farmer_token, farm, crop_cycle, sensor_readings, carbon_report_draft
    ):
        resp = client.get(
            f"/carbon-reports/farm/{farm.id}?limit=1&offset=0",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ── /tokens/my-wallet filtering + pagination ─────────────────────────────────

class TestTokensFilter:
    def test_filter_by_minted_status(
        self, client, farmer_token, farm, crop_cycle,
        sensor_readings, verified_report, minted_token
    ):
        resp = client.get(
            "/tokens/my-wallet?status=MINTED",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        for t in resp.json():
            assert t["status"] == "MINTED"

    def test_filter_by_nonexistent_status_returns_empty(
        self, client, farmer_token, farm, crop_cycle,
        sensor_readings, verified_report, minted_token
    ):
        resp = client.get(
            "/tokens/my-wallet?status=RETIRED",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_no_filter_returns_all(
        self, client, farmer_token, farm, crop_cycle,
        sensor_readings, verified_report, minted_token
    ):
        resp = client.get(
            "/tokens/my-wallet",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_wallet_pagination_limit(
        self, client, farmer_token, farm, crop_cycle,
        sensor_readings, verified_report, minted_token
    ):
        resp = client.get(
            "/tokens/my-wallet?limit=1",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert len(resp.json()) == 1

    def test_wallet_pagination_offset_beyond(
        self, client, farmer_token, farm, crop_cycle,
        sensor_readings, verified_report, minted_token
    ):
        resp = client.get(
            "/tokens/my-wallet?offset=9999",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.json() == []


# ── /satellite filtering + pagination ────────────────────────────────────────

class TestSatelliteFilter:
    def test_filter_by_crop_cycle_id(
        self, client, farmer_token, farm, crop_cycle, satellite_observations
    ):
        resp = client.get(
            f"/satellite/{farm.id}?crop_cycle_id={crop_cycle.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        for obs in resp.json():
            assert obs["crop_cycle_id"] == crop_cycle.id

    def test_filter_by_nonexistent_crop_cycle(
        self, client, farmer_token, farm, satellite_observations
    ):
        resp = client.get(
            f"/satellite/{farm.id}?crop_cycle_id=99999",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_no_filter_returns_all(
        self, client, farmer_token, farm, satellite_observations
    ):
        resp = client.get(
            f"/satellite/{farm.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert len(resp.json()) == 5

    def test_satellite_pagination_limit(
        self, client, farmer_token, farm, satellite_observations
    ):
        resp = client.get(
            f"/satellite/{farm.id}?limit=2",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert len(resp.json()) == 2

    def test_satellite_pagination_offset(
        self, client, farmer_token, farm, satellite_observations
    ):
        all_ids = [o["id"] for o in client.get(
            f"/satellite/{farm.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        ).json()]
        page2 = client.get(
            f"/satellite/{farm.id}?offset=3",
            headers={"Authorization": f"Bearer {farmer_token}"},
        ).json()
        for obs in page2:
            assert obs["id"] not in all_ids[:3]


# ── /drone filtering + pagination ─────────────────────────────────────────────

class TestDroneFilter:
    def test_filter_by_crop_cycle_id(
        self, client, farmer_token, farm, crop_cycle, drone_observations
    ):
        resp = client.get(
            f"/drone/{farm.id}?crop_cycle_id={crop_cycle.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.status_code == 200
        for obs in resp.json():
            assert obs["crop_cycle_id"] == crop_cycle.id

    def test_filter_by_nonexistent_crop_cycle(
        self, client, farmer_token, farm, drone_observations
    ):
        resp = client.get(
            f"/drone/{farm.id}?crop_cycle_id=99999",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.json() == []

    def test_no_filter_returns_all(
        self, client, farmer_token, farm, drone_observations
    ):
        resp = client.get(
            f"/drone/{farm.id}",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert len(resp.json()) == 3

    def test_drone_pagination_limit(
        self, client, farmer_token, farm, drone_observations
    ):
        resp = client.get(
            f"/drone/{farm.id}?limit=1",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert len(resp.json()) == 1

    def test_drone_offset_beyond_returns_empty(
        self, client, farmer_token, farm, drone_observations
    ):
        resp = client.get(
            f"/drone/{farm.id}?offset=9999",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert resp.json() == []
