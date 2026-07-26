"""
MRV Demo High-Emission Tests — Phase 10A

Tests:
- Standard drone/satellite simulate works with recent cycle start_date
- POST /mrv/demo/high-emission creates sensor + satellite + drone records
- Each scenario produces expected credit range from carbon calculator
- EDGE_CERTIFICATE_ONLY produces 0 credits but positive co2e
- POST /carbon-reports/generate/{crop_cycle_id} after high-emission data → real credits
- Unknown scenario returns 400
- Access control: only farmer (own farm) or admin
- Response contains demo_label = "DEMO_HIGH_EMISSION"
"""
import math
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.farm import Farm, CropCycle
from app.models.sensor import SensorReading, SensorSourceType
from app.models.satellite_observation import SatelliteObservation, SatelliteSource
from app.models.drone_observation import DroneObservation, DroneSource
from app.security import hash_password


# ── Helper fixtures ───────────────────────────────────────────────────────────

def _make_user(db, name, email, role):
    u = User(
        name=name,
        email=email,
        password_hash=hash_password("pass123"),
        role=role,
        is_active=True,
        is_approved=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _login(client, email, password="pass123"):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def farmer_a(db):
    return _make_user(db, "Farmer A", "farmer_a@mrvtest.example.com", UserRole.FARMER)


@pytest.fixture
def farmer_b(db):
    return _make_user(db, "Farmer B", "farmer_b@mrvtest.example.com", UserRole.FARMER)


@pytest.fixture
def admin_user(db):
    return _make_user(db, "Admin", "admin@mrvtest.example.com", UserRole.ADMIN)


@pytest.fixture
def fpo_user(db):
    return _make_user(db, "FPO User", "fpo@mrvtest.example.com", UserRole.FPO)


@pytest.fixture
def farm_a(db, farmer_a):
    f = Farm(
        farmer_id=farmer_a.id,
        farm_name="MRV Test Farm",
        land_area_acres=5.0,
        latitude=18.52,
        longitude=73.85,
        village="TestVillage",
        district="Pune",
        state="Maharashtra",
        soil_type="Loamy",
        water_source="Canal",
        is_approved=True,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


@pytest.fixture
def cycle_recent(db, farm_a):
    """Crop cycle with start_date = today (tests the 'recent cycle' bug)."""
    today = datetime.now(timezone.utc).date()
    c = CropCycle(
        farm_id=farm_a.id,
        crop_type="Mixed Livestock",
        season="Annual",
        start_date=today,
        baseline_method="IPCC_TIER1",
        reduction_practice="BIODIGESTER",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def cycle_old(db, farm_a):
    """Crop cycle with start_date 365 days ago (normal historical cycle)."""
    past = datetime.now(timezone.utc).date() - timedelta(days=365)
    c = CropCycle(
        farm_id=farm_a.id,
        crop_type="Mixed Livestock",
        season="Annual",
        start_date=past,
        baseline_method="IPCC_TIER1",
        reduction_practice="BIODIGESTER",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ── Fix 1: Drone/satellite simulate with recent start_date ────────────────────

class TestDroneSimulateWithRecentCycle:
    """Verify drone simulate generates all N observations even with recent start_date."""

    def test_drone_simulate_4_obs_recent_cycle(self, client, db, farmer_a, farm_a, cycle_recent):
        """With start_date=today, drone simulate should still produce 4 observations."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = client.post(
            "/drone/simulate",
            json={"farm_id": farm_a.id, "crop_cycle_id": cycle_recent.id, "number_of_observations": 4},
            headers=headers,
        )
        assert resp.status_code == 201, f"Drone simulate failed: {resp.text}"
        data = resp.json()
        assert data["created"] == 4, f"Expected 4 drone obs, got {data['created']}"

    def test_satellite_simulate_6_obs_recent_cycle(self, client, db, farmer_a, farm_a, cycle_recent):
        """With start_date=today, satellite simulate should produce 6 observations."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": farm_a.id, "crop_cycle_id": cycle_recent.id, "number_of_observations": 6},
            headers=headers,
        )
        assert resp.status_code == 201, f"Satellite simulate failed: {resp.text}"
        data = resp.json()
        assert data["created"] == 6, f"Expected 6 satellite obs, got {data['created']}"

    def test_drone_obs_dates_are_not_future(self, client, db, farmer_a, farm_a, cycle_recent):
        """All generated drone observations must have dates <= today."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = client.post(
            "/drone/simulate",
            json={"farm_id": farm_a.id, "crop_cycle_id": cycle_recent.id, "number_of_observations": 4},
            headers=headers,
        )
        assert resp.status_code == 201
        today_str = datetime.now(timezone.utc).date().isoformat()
        for obs in resp.json()["observations"]:
            assert obs["observation_date"] <= today_str, (
                f"Drone obs date {obs['observation_date']} is in the future!"
            )

    def test_satellite_obs_dates_are_not_future(self, client, db, farmer_a, farm_a, cycle_recent):
        """All generated satellite observations must have dates <= today."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = client.post(
            "/satellite/simulate",
            json={"farm_id": farm_a.id, "crop_cycle_id": cycle_recent.id, "number_of_observations": 6},
            headers=headers,
        )
        assert resp.status_code == 201
        today_str = datetime.now(timezone.utc).date().isoformat()
        for obs in resp.json()["observations"]:
            assert obs["observation_date"] <= today_str


# ── Fix 2: High-emission demo endpoint ───────────────────────────────────────

class TestHighEmissionDemoEndpoint:
    """Tests for POST /mrv/demo/high-emission."""

    def _generate(self, client, farm_id, cycle_id, scenario, headers, days=30):
        return client.post(
            "/mrv/demo/high-emission",
            json={
                "farm_id": farm_id,
                "crop_cycle_id": cycle_id,
                "scenario": scenario,
                "days": days,
            },
            headers=headers,
        )

    def test_dairy_biodigester_creates_records(self, client, db, farmer_a, farm_a, cycle_old):
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = self._generate(client, farm_a.id, cycle_old.id, "DAIRY_BIODIGESTER", headers)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["sensor_readings_generated"] >= 14
        assert data["satellite_observations_generated"] >= 1
        assert data["drone_observations_generated"] >= 1
        assert data["demo_label"] == "DEMO_HIGH_EMISSION"

    def test_dairy_biodigester_expected_credits(self, client, db, farmer_a, farm_a, cycle_old):
        """DAIRY_BIODIGESTER produces 12–16 credits (target: 14)."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = self._generate(client, farm_a.id, cycle_old.id, "DAIRY_BIODIGESTER", headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["expected_credits"] >= 12, f"Got {data['expected_credits']} credits"
        assert data["expected_credits"] <= 16, f"Got {data['expected_credits']} credits"
        assert data["expected_co2e_reduction_tonnes"] >= 12.0

    def test_dairy_sri_low_expected_credits(self, client, db, farmer_a, farm_a, cycle_old):
        """DAIRY_SRI_LOW produces 5–7 credits (target: 6)."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = self._generate(client, farm_a.id, cycle_old.id, "DAIRY_SRI_LOW", headers)
        assert resp.status_code == 201
        data = resp.json()
        assert 5 <= data["expected_credits"] <= 7

    def test_mixed_livestock_biochar_expected_credits(self, client, db, farmer_a, farm_a, cycle_old):
        """MIXED_LIVESTOCK_BIOCHAR produces 14–18 credits (target: 16)."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = self._generate(client, farm_a.id, cycle_old.id, "MIXED_LIVESTOCK_BIOCHAR", headers)
        assert resp.status_code == 201
        data = resp.json()
        assert 14 <= data["expected_credits"] <= 18

    def test_buffalo_biodigester_expected_credits(self, client, db, farmer_a, farm_a, cycle_old):
        """BUFFALO_BIODIGESTER produces 10–13 credits (target: 11)."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = self._generate(client, farm_a.id, cycle_old.id, "BUFFALO_BIODIGESTER", headers)
        assert resp.status_code == 201
        data = resp.json()
        assert 10 <= data["expected_credits"] <= 13

    def test_edge_certificate_only_zero_credits(self, client, db, farmer_a, farm_a, cycle_old):
        """EDGE_CERTIFICATE_ONLY produces 0 credits but positive co2e."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = self._generate(client, farm_a.id, cycle_old.id, "EDGE_CERTIFICATE_ONLY", headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["expected_credits"] == 0
        assert data["expected_co2e_reduction_tonnes"] > 0.0
        assert data["expected_co2e_reduction_tonnes"] < 1.0

    def test_unknown_scenario_returns_400(self, client, db, farmer_a, farm_a, cycle_old):
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = self._generate(client, farm_a.id, cycle_old.id, "INVALID_SCENARIO", headers)
        assert resp.status_code == 400

    def test_sensor_readings_labeled_high_emission_demo(self, client, db, farmer_a, farm_a, cycle_old):
        """Sensor readings must have source_type = HIGH_EMISSION_DEMO."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = self._generate(client, farm_a.id, cycle_old.id, "DAIRY_BIODIGESTER", headers)
        assert resp.status_code == 201
        readings = db.query(SensorReading).filter(
            SensorReading.crop_cycle_id == cycle_old.id
        ).all()
        assert len(readings) > 0
        for r in readings:
            assert r.source_type == SensorSourceType.HIGH_EMISSION_DEMO, (
                f"Expected HIGH_EMISSION_DEMO, got {r.source_type}"
            )

    def test_high_emission_with_recent_cycle(self, client, db, farmer_a, farm_a, cycle_recent):
        """High-emission demo returns 201 for a cycle with start_date=today (tested separately for count)."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = self._generate(client, farm_a.id, cycle_recent.id, "DAIRY_BIODIGESTER", headers, days=30)
        assert resp.status_code == 201, resp.text

    def test_other_farmer_cannot_access(self, client, db, farmer_b, farm_a, cycle_old):
        """Farmer B cannot generate demo data on Farmer A's farm."""
        headers = _login(client, "farmer_b@mrvtest.example.com")
        resp = client.post(
            "/mrv/demo/high-emission",
            json={"farm_id": farm_a.id, "crop_cycle_id": cycle_old.id, "scenario": "DAIRY_BIODIGESTER"},
            headers=headers,
        )
        assert resp.status_code == 403

    def test_fpo_cannot_access_high_emission_demo(self, client, db, fpo_user, farm_a, cycle_old):
        """FPO role cannot generate high-emission demo (only farmer/admin)."""
        headers = _login(client, "fpo@mrvtest.example.com")
        resp = client.post(
            "/mrv/demo/high-emission",
            json={"farm_id": farm_a.id, "crop_cycle_id": cycle_old.id, "scenario": "DAIRY_BIODIGESTER"},
            headers=headers,
        )
        assert resp.status_code == 403

    def test_admin_can_generate_on_any_farm(self, client, db, admin_user, farm_a, cycle_old):
        """Admin can generate high-emission demo on any farm."""
        headers = _login(client, "admin@mrvtest.example.com")
        resp = self._generate(client, farm_a.id, cycle_old.id, "BUFFALO_BIODIGESTER", headers)
        assert resp.status_code == 201

    def test_response_schema_has_all_required_fields(self, client, db, farmer_a, farm_a, cycle_old):
        """Response must have every field the mobile UI reads — no undefined values."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = self._generate(client, farm_a.id, cycle_old.id, "DAIRY_BIODIGESTER", headers)
        assert resp.status_code == 201
        data = resp.json()
        # These are the exact field names the mobile TypeScript interface expects
        required_fields = [
            "success",
            "scenario",
            "scenario_description",
            "farm_id",
            "crop_cycle_id",
            "sensor_readings_generated",
            "satellite_observations_generated",
            "drone_observations_generated",
            "expected_co2e_reduction_tonnes",
            "expected_credits",
            "demo_label",
            "message",
            "warning",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: '{field}'"
            assert data[field] is not None, f"Field '{field}' is None"
        # Verify numeric counts are actual integers > 0
        assert isinstance(data["sensor_readings_generated"], int)
        assert isinstance(data["satellite_observations_generated"], int)
        assert isinstance(data["drone_observations_generated"], int)
        assert data["sensor_readings_generated"] > 0
        assert data["satellite_observations_generated"] > 0
        assert data["drone_observations_generated"] > 0
        assert data["success"] is True
        assert data["demo_label"] == "DEMO_HIGH_EMISSION"

    def test_high_emission_with_recent_cycle_generates_full_readings(
        self, client, db, farmer_a, farm_a, cycle_recent
    ):
        """With start_date=today, high-emission demo still generates full 30 readings."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = self._generate(client, farm_a.id, cycle_recent.id, "DAIRY_BIODIGESTER", headers, days=30)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        # After Phase 10A date-floor fix, all 30 days are generated regardless of cycle.start_date
        assert data["sensor_readings_generated"] == 30, (
            f"Expected 30 sensor readings, got {data['sensor_readings_generated']}"
        )
        assert data["satellite_observations_generated"] == 6
        assert data["drone_observations_generated"] == 4

    def test_scenarios_list_endpoint(self, client, db, farmer_a):
        """GET /mrv/demo/scenarios returns all 5 scenarios."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        resp = client.get("/mrv/demo/scenarios", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        keys = {sc["key"] for sc in data}
        assert "DAIRY_BIODIGESTER" in keys
        assert "EDGE_CERTIFICATE_ONLY" in keys


# ── Fix 3: Carbon report generation after high-emission data ─────────────────

class TestCarbonReportAfterHighEmission:
    """
    End-to-end: generate high-emission demo data → run carbon report generation
    → verify co2e and credits match expected range.
    """

    def test_report_produces_real_credits_from_high_emission_data(
        self, client, db, farmer_a, farm_a, cycle_old
    ):
        """
        After generating DAIRY_BIODIGESTER demo data, POST /carbon-reports/generate
        produces a report with estimated_credits >= 12.
        """
        headers = _login(client, "farmer_a@mrvtest.example.com")

        # 1. Generate high-emission demo data
        demo_resp = client.post(
            "/mrv/demo/high-emission",
            json={
                "farm_id": farm_a.id,
                "crop_cycle_id": cycle_old.id,
                "scenario": "DAIRY_BIODIGESTER",
                "days": 30,
            },
            headers=headers,
        )
        assert demo_resp.status_code == 201, demo_resp.text
        expected_credits = demo_resp.json()["expected_credits"]
        assert expected_credits >= 12

        # 2. Generate carbon report
        report_resp = client.post(
            f"/carbon-reports/generate/{cycle_old.id}",
            headers=headers,
        )
        assert report_resp.status_code == 201, report_resp.text
        report = report_resp.json()
        assert report["status"] == "DRAFT"
        assert report["co2e_reduction_tonnes"] >= 12.0, (
            f"Expected co2e >= 12, got {report['co2e_reduction_tonnes']}"
        )
        assert report["estimated_credits"] >= 12, (
            f"Expected credits >= 12, got {report['estimated_credits']}"
        )

    def test_edge_cert_report_has_zero_credits(self, client, db, farmer_a, farm_a, cycle_old):
        """EDGE_CERTIFICATE_ONLY → report has estimated_credits = 0 but co2e > 0."""
        headers = _login(client, "farmer_a@mrvtest.example.com")

        client.post(
            "/mrv/demo/high-emission",
            json={"farm_id": farm_a.id, "crop_cycle_id": cycle_old.id, "scenario": "EDGE_CERTIFICATE_ONLY", "days": 30},
            headers=headers,
        )

        report_resp = client.post(f"/carbon-reports/generate/{cycle_old.id}", headers=headers)
        assert report_resp.status_code == 201
        report = report_resp.json()
        assert report["estimated_credits"] == 0
        assert report["co2e_reduction_tonnes"] > 0.0

    def test_high_emission_report_co2e_in_range_5_to_20(self, client, db, farmer_a, farm_a, cycle_old):
        """All non-edge-case scenarios produce 5–20 tCO₂e."""
        headers = _login(client, "farmer_a@mrvtest.example.com")
        for scenario in ["DAIRY_SRI_LOW", "DAIRY_BIODIGESTER", "MIXED_LIVESTOCK_BIOCHAR", "BUFFALO_BIODIGESTER"]:
            # Need a fresh cycle per scenario to avoid mixing readings
            past = datetime.now(timezone.utc).date() - timedelta(days=365)
            fresh_cycle = CropCycle(
                farm_id=farm_a.id,
                crop_type="Mixed Livestock",
                season="Annual",
                start_date=past,
                baseline_method="IPCC_TIER1",
                reduction_practice="BIODIGESTER",
            )
            db.add(fresh_cycle)
            db.commit()
            db.refresh(fresh_cycle)

            client.post(
                "/mrv/demo/high-emission",
                json={"farm_id": farm_a.id, "crop_cycle_id": fresh_cycle.id, "scenario": scenario, "days": 30},
                headers=headers,
            )
            report_resp = client.post(f"/carbon-reports/generate/{fresh_cycle.id}", headers=headers)
            assert report_resp.status_code == 201, f"{scenario}: {report_resp.text}"
            report = report_resp.json()
            assert 5.0 <= report["co2e_reduction_tonnes"] <= 20.0, (
                f"{scenario}: co2e={report['co2e_reduction_tonnes']:.3f} out of [5,20] range"
            )
            assert report["estimated_credits"] >= 5, (
                f"{scenario}: only {report['estimated_credits']} credits"
            )


# ── Regression: DroneSource enum gap (Phase 10A bug fix) ─────────────────────

class TestDroneObservationInsert:
    """
    Regression tests for the dronesource / native_enum bug.

    Root cause (Phase 10A):
      - Migration 007 created drone_observations WITHOUT a source column.
      - Migration 010 added source as VARCHAR(20) — not a PostgreSQL native enum.
      - Python model used SAEnum(DroneSource) with native_enum=True (default).
      - SQLAlchemy emits ::dronesource casts in INSERT SQL.
      - PostgreSQL: 'dronesource' type never existed → UndefinedObject error.
      - Entire mrv/demo/high-emission transaction rolled back → all counts zero.

    Fix: SAEnum(DroneSource, native_enum=False) in the model.
    These tests verify direct ORM inserts work and the response counts are real.
    """

    @pytest.fixture()
    def farmer(self, db):
        u = User(
            name="Drone Reg Farmer",
            email="drone_reg@regression.example.com",
            password_hash=__import__("app.security", fromlist=["hash_password"]).hash_password("pass123"),
            role=UserRole.FARMER,
            is_active=True,
            is_approved=True,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u

    @pytest.fixture()
    def farm(self, db, farmer):
        f = Farm(
            farmer_id=farmer.id,
            farm_name="Drone Regression Farm",
            land_area_acres=5.0,
            latitude=18.5,
            longitude=73.8,
            village="Regtown",
            district="Pune",
            state="Maharashtra",
            soil_type="Clay",
            water_source="Well",
        )
        db.add(f)
        db.commit()
        db.refresh(f)
        return f

    @pytest.fixture()
    def cycle(self, db, farm):
        from datetime import date, timedelta
        past = date.today() - timedelta(days=60)
        c = CropCycle(
            farm_id=farm.id,
            crop_type="Livestock Demo",
            season="Annual",
            start_date=past,
            baseline_method="IPCC_TIER1",
            reduction_practice="BIODIGESTER",
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        return c

    def test_drone_observation_direct_orm_insert(self, db, farm, cycle):
        """
        Direct ORM insert of DroneObservation must not raise UndefinedObject.
        This is the exact operation that failed before the native_enum=False fix.
        """
        from datetime import date
        obs = DroneObservation(
            farm_id=farm.id,
            crop_cycle_id=cycle.id,
            observation_date=date.today(),
            vegetation_cover_percent=65.0,
            standing_water_percent=2.0,
            anomaly_score=5.0,
            source=DroneSource.DRONE_SIMULATED,
        )
        db.add(obs)
        # This commit MUST succeed — previously it raised:
        #   psycopg2.errors.UndefinedObject: type "dronesource" does not exist
        db.commit()
        db.refresh(obs)
        assert obs.id is not None
        assert obs.source == DroneSource.DRONE_SIMULATED

    def test_drone_observation_all_source_values(self, db, farm, cycle):
        """All three DroneSource enum values can be inserted without error."""
        from datetime import date, timedelta
        for i, src in enumerate(DroneSource):
            obs = DroneObservation(
                farm_id=farm.id,
                crop_cycle_id=cycle.id,
                observation_date=date.today() - timedelta(days=i),
                vegetation_cover_percent=60.0 + i,
                standing_water_percent=1.0,
                anomaly_score=0.0,
                source=src,
            )
            db.add(obs)
        db.commit()
        count = db.query(DroneObservation).filter(
            DroneObservation.crop_cycle_id == cycle.id
        ).count()
        assert count == 3

    def test_high_emission_endpoint_drone_count_nonzero(
        self, client, db, farmer, farm, cycle
    ):
        """
        POST /mrv/demo/high-emission must return drone_observations_generated > 0.

        Before the fix, the transaction rolled back due to the dronesource type error
        and all counts were 0 even though the endpoint returned HTTP 201.
        """
        headers = _login(client, "drone_reg@regression.example.com")
        resp = client.post(
            "/mrv/demo/high-emission",
            json={
                "farm_id": farm.id,
                "crop_cycle_id": cycle.id,
                "scenario": "DAIRY_BIODIGESTER",
                "days": 30,
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()

        # All three counts must be non-zero — this was the failing assertion
        assert data["sensor_readings_generated"] > 0, (
            "sensor_readings_generated is 0 — transaction rolled back"
        )
        assert data["satellite_observations_generated"] > 0, (
            "satellite_observations_generated is 0 — transaction rolled back"
        )
        assert data["drone_observations_generated"] > 0, (
            "drone_observations_generated is 0 — dronesource type error still present"
        )

        # Verify actual DB rows were created (not just response values)
        sensor_count = db.query(SensorReading).filter(
            SensorReading.crop_cycle_id == cycle.id
        ).count()
        drone_count = db.query(DroneObservation).filter(
            DroneObservation.crop_cycle_id == cycle.id
        ).count()
        sat_count = db.query(SatelliteObservation).filter(
            SatelliteObservation.crop_cycle_id == cycle.id
        ).count()

        assert sensor_count > 0, f"No sensor rows in DB — expected {data['sensor_readings_generated']}"
        assert drone_count > 0, f"No drone rows in DB — expected {data['drone_observations_generated']}"
        assert sat_count > 0, f"No satellite rows in DB — expected {data['satellite_observations_generated']}"

        # Response values must match actual DB counts
        assert data["sensor_readings_generated"] == sensor_count
        assert data["drone_observations_generated"] == drone_count
        assert data["satellite_observations_generated"] == sat_count
