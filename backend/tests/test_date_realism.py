"""
Date Realism Regression Tests — Phase 9B+

Verifies that simulated sensor, satellite, and drone data:
  1. Never has future-dated readings/observations.
  2. Respects crop_cycle.start_date as the earliest allowed date.
  3. Blocks simulation when crop_cycle.start_date is in the future.
  4. Caps sensor readings at today when number_of_days exceeds available range.
"""
import pytest
from datetime import date, datetime, timedelta, timezone

AUTH = lambda t: {"Authorization": f"Bearer {t}"}

# ── helpers ───────────────────────────────────────────────────────────────────
# All date helpers use UTC so they agree with the router's datetime.now(timezone.utc).date()

def _utc_today():
    return datetime.now(timezone.utc).date()


def _create_cycle_with_start(client, token, farm_id, start_date: str):
    resp = client.post(
        f"/farms/{farm_id}/crop-cycles",
        json={
            "crop_type": "Paddy",
            "season": "Kharif",
            "start_date": start_date,
            "baseline_method": "AWD",
            "reduction_practice": "SRI",
        },
        headers=AUTH(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _today_str() -> str:
    return _utc_today().isoformat()


def _yesterday_str() -> str:
    return (_utc_today() - timedelta(days=1)).isoformat()


def _tomorrow_str() -> str:
    return (_utc_today() + timedelta(days=1)).isoformat()


def _past_str(days_ago: int = 5) -> str:
    return (_utc_today() - timedelta(days=days_ago)).isoformat()


# ═══════════════════════════════════════════════════════════════════════════════
class TestSensorDateRealism:
    """POST /sensors/simulate must never generate future-dated readings."""

    def test_readings_never_in_future_with_recent_cycle(self, client, farmer_token, farm):
        """Cycle starts yesterday → all readings ≤ today."""
        cycle_id = _create_cycle_with_start(client, farmer_token, farm.id, _yesterday_str())
        resp = client.post(
            "/sensors/simulate",
            json={"farm_id": farm.id, "crop_cycle_id": cycle_id, "number_of_days": 30},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        # Should be capped to available days (yesterday + today = 2 days)
        assert data["generated_readings"] == 2
        assert data["capped_at_today"] is True
        assert data["requested_days"] == 30

    def test_readings_never_in_future_with_today_cycle(self, client, farmer_token, farm):
        """Cycle starts today → only 1 day available."""
        cycle_id = _create_cycle_with_start(client, farmer_token, farm.id, _today_str())
        resp = client.post(
            "/sensors/simulate",
            json={"farm_id": farm.id, "crop_cycle_id": cycle_id, "number_of_days": 10},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["generated_readings"] == 1
        assert data["capped_at_today"] is True

    def test_future_cycle_start_date_is_rejected(self, client, farmer_token, farm):
        """Cycle starts tomorrow → simulate must return 400."""
        cycle_id = _create_cycle_with_start(client, farmer_token, farm.id, _tomorrow_str())
        resp = client.post(
            "/sensors/simulate",
            json={"farm_id": farm.id, "crop_cycle_id": cycle_id, "number_of_days": 5},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 400
        assert "future" in resp.json()["detail"].lower()

    def test_old_cycle_not_capped(self, client, farmer_token, farm):
        """Cycle starts over 1 year ago → requesting ≤365 days is not capped."""
        old_start = (date.today() - timedelta(days=400)).isoformat()
        cycle_id = _create_cycle_with_start(client, farmer_token, farm.id, old_start)
        resp = client.post(
            "/sensors/simulate",
            json={"farm_id": farm.id, "crop_cycle_id": cycle_id, "number_of_days": 30},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["generated_readings"] == 30
        assert data["capped_at_today"] is False

    def test_reading_times_are_not_in_future(self, client, farmer_token, farm):
        """All reading_time values returned via GET must be ≤ now."""
        cycle_id = _create_cycle_with_start(client, farmer_token, farm.id, _past_str(5))
        client.post(
            "/sensors/simulate",
            json={"farm_id": farm.id, "crop_cycle_id": cycle_id, "number_of_days": 10},
            headers=AUTH(farmer_token),
        )
        resp = client.get(f"/sensors/farm/{farm.id}", headers=AUTH(farmer_token))
        assert resp.status_code == 200
        now_iso = datetime.now(timezone.utc).isoformat()
        for reading in resp.json():
            assert reading["reading_time"] <= now_iso, (
                f"Future reading: {reading['reading_time']}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
class TestSatelliteDateRealism:
    """POST /satellite/simulate must never generate future or year-2024 dates."""

    def test_observations_not_in_future(self, client, farmer_token, farm):
        """Simulate without crop_cycle → all obs ≤ today."""
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": farm.id, "number_of_observations": 5},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 201, resp.text
        today_str = date.today().isoformat()
        for obs in resp.json()["observations"]:
            assert obs["observation_date"] <= today_str, (
                f"Future satellite obs: {obs['observation_date']}"
            )

    def test_observations_not_in_2024(self, client, farmer_token, farm):
        """Observations must not be hardcoded to 2024."""
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": farm.id, "number_of_observations": 3},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 201, resp.text
        for obs in resp.json()["observations"]:
            assert not obs["observation_date"].startswith("2024"), (
                f"Hardcoded 2024 date: {obs['observation_date']}"
            )

    def test_observations_with_recent_crop_cycle(self, client, farmer_token, farm):
        """With a crop cycle starting yesterday, obs must be ≤ today and ≥ cycle start."""
        cycle_id = _create_cycle_with_start(client, farmer_token, farm.id, _yesterday_str())
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": farm.id, "crop_cycle_id": cycle_id, "number_of_observations": 5},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        today_str = date.today().isoformat()
        yesterday_str = _yesterday_str()
        for obs in data["observations"]:
            assert obs["observation_date"] >= yesterday_str, "Before crop cycle start"
            assert obs["observation_date"] <= today_str, "Future observation"

    def test_observations_with_old_crop_cycle(self, client, farmer_token, farm):
        """Old cycle (30 days ago) → N observations in that range."""
        old_start = _past_str(30)
        cycle_id = _create_cycle_with_start(client, farmer_token, farm.id, old_start)
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": farm.id, "crop_cycle_id": cycle_id, "number_of_observations": 5},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        today_str = date.today().isoformat()
        for obs in data["observations"]:
            assert obs["observation_date"] >= old_start, "Before crop cycle start"
            assert obs["observation_date"] <= today_str, "Future observation"


# ═══════════════════════════════════════════════════════════════════════════════
class TestDroneDateRealism:
    """POST /drone/simulate must never generate future or year-2024 dates."""

    def test_observations_not_in_future(self, client, farmer_token, farm):
        """Simulate without crop_cycle → all obs ≤ today."""
        resp = client.post(
            "/drone/simulate",
            json={"farm_id": farm.id, "number_of_observations": 3},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 201, resp.text
        today_str = date.today().isoformat()
        for obs in resp.json()["observations"]:
            assert obs["observation_date"] <= today_str, (
                f"Future drone obs: {obs['observation_date']}"
            )

    def test_observations_not_in_2024(self, client, farmer_token, farm):
        """Observations must not be hardcoded to 2024."""
        resp = client.post(
            "/drone/simulate",
            json={"farm_id": farm.id, "number_of_observations": 3},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 201, resp.text
        for obs in resp.json()["observations"]:
            assert not obs["observation_date"].startswith("2024"), (
                f"Hardcoded 2024 date: {obs['observation_date']}"
            )

    def test_observations_with_recent_crop_cycle(self, client, farmer_token, farm):
        """With a crop cycle starting yesterday, obs must be ≤ today."""
        cycle_id = _create_cycle_with_start(client, farmer_token, farm.id, _yesterday_str())
        resp = client.post(
            "/drone/simulate",
            json={"farm_id": farm.id, "crop_cycle_id": cycle_id, "number_of_observations": 5},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 201, resp.text
        today_str = date.today().isoformat()
        yesterday_str = _yesterday_str()
        for obs in resp.json()["observations"]:
            assert obs["observation_date"] >= yesterday_str, "Before crop cycle start"
            assert obs["observation_date"] <= today_str, "Future observation"

    def test_observations_with_old_crop_cycle(self, client, farmer_token, farm):
        """Old cycle (30 days ago) → N observations in that range."""
        old_start = _past_str(30)
        cycle_id = _create_cycle_with_start(client, farmer_token, farm.id, old_start)
        resp = client.post(
            "/drone/simulate",
            json={"farm_id": farm.id, "crop_cycle_id": cycle_id, "number_of_observations": 4},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 201, resp.text
        today_str = date.today().isoformat()
        for obs in resp.json()["observations"]:
            assert obs["observation_date"] >= old_start, "Before crop cycle start"
            assert obs["observation_date"] <= today_str, "Future observation"

    def test_future_cycle_blocked_gracefully(self, client, farmer_token, farm):
        """Drone sim with future crop cycle: should generate 0 observations (obs capped at today)."""
        cycle_id = _create_cycle_with_start(client, farmer_token, farm.id, _tomorrow_str())
        resp = client.post(
            "/drone/simulate",
            json={"farm_id": farm.id, "crop_cycle_id": cycle_id, "number_of_observations": 3},
            headers=AUTH(farmer_token),
        )
        assert resp.status_code == 201, resp.text
        # base_date = tomorrow (> today), so the loop breaks immediately
        assert resp.json()["created"] == 0
