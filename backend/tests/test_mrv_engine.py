"""
Phase 7 — MRV engine unit tests.

Tests app/services/mrv_engine.py logic directly.
Uses types.SimpleNamespace to avoid SQLAlchemy ORM initialisation overhead.
"""
import pytest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

from app.services.mrv_engine import calculate_mrv, MRVResult
from app.models.satellite_observation import VegetationHealth, FloodRisk, SatelliteSource
from app.models.sensor import SensorSourceType


def _make_sensor(farm_id=1, cycle_id=1, quality=85.0, days_ago=0):
    base = datetime(2024, 6, 1, tzinfo=timezone.utc) + timedelta(days=days_ago)
    return SimpleNamespace(
        farm_id=farm_id,
        crop_cycle_id=cycle_id,
        reading_time=base,
        soil_moisture=62.0,
        water_depth_cm=5.0,
        temperature_c=30.0,
        humidity=70.0,
        rainfall_mm=0.0,
        estimated_methane=0.5,
        data_quality_score=quality,
        source_type=SensorSourceType.SIMULATED,
    )


def _make_satellite(ndvi=0.5, ndwi=0.2, health=VegetationHealth.GOOD,
                    flood=FloodRisk.NONE, cloud=10.0):
    return SimpleNamespace(
        ndvi=ndvi,
        ndwi=ndwi,
        vegetation_health=health,
        flood_risk=flood,
        cloud_cover_percent=cloud,
        source=SatelliteSource.SATELLITE_SIMULATED,
    )


def _make_drone(vegetation=70.0, water=15.0, anomaly=10.0):
    return SimpleNamespace(
        vegetation_cover_percent=vegetation,
        standing_water_percent=water,
        anomaly_score=anomaly,
    )


class TestMRVBaseline:
    def test_all_good_data_high_confidence(self):
        sensors = [_make_sensor(quality=85.0, days_ago=i) for i in range(14)]
        satellites = [_make_satellite() for _ in range(5)]
        drones = [_make_drone() for _ in range(3)]
        result = calculate_mrv(sensors, satellites, drones)
        assert result.confidence_score >= 70
        assert result.consistency_score == 100.0
        assert result.flags == []
        assert result.inconsistencies == []

    def test_returns_mrv_result(self):
        result = calculate_mrv([], [], [])
        assert isinstance(result, MRVResult)

    def test_counts_correct(self):
        sensors = [_make_sensor() for _ in range(10)]
        sats = [_make_satellite() for _ in range(3)]
        drones = [_make_drone() for _ in range(2)]
        result = calculate_mrv(sensors, sats, drones)
        assert result.sensor_count == 10
        assert result.satellite_count == 3
        assert result.drone_count == 2


class TestMRVSensorFlags:
    def test_insufficient_readings_flag(self):
        sensors = [_make_sensor() for _ in range(5)]  # < 7
        result = calculate_mrv(sensors, [], [])
        assert any("INSUFFICIENT_SENSOR_READINGS" in f for f in result.flags)

    def test_low_quality_flag(self):
        sensors = [_make_sensor(quality=55.0) for _ in range(10)]
        result = calculate_mrv(sensors, [], [])
        assert any("LOW_SENSOR_QUALITY" in f for f in result.flags)

    def test_good_quality_no_flag(self):
        sensors = [_make_sensor(quality=85.0) for _ in range(14)]
        result = calculate_mrv(sensors, [], [])
        assert not any("LOW_SENSOR_QUALITY" in f for f in result.flags)


class TestMRVSatelliteFlags:
    def test_missing_satellite_flag(self):
        sensors = [_make_sensor() for _ in range(14)]
        result = calculate_mrv(sensors, [], [])
        assert "MISSING_SATELLITE_DATA" in result.flags

    def test_poor_vegetation_flag(self):
        sensors = [_make_sensor() for _ in range(14)]
        sats = [_make_satellite(health=VegetationHealth.POOR)]
        result = calculate_mrv(sensors, sats, [])
        assert any("POOR_VEGETATION_DETECTED" in f for f in result.flags)

    def test_high_flood_risk_flag(self):
        sats = [_make_satellite(flood=FloodRisk.HIGH)]
        result = calculate_mrv([], sats, [])
        assert any("HIGH_FLOOD_RISK" in f for f in result.flags)

    def test_high_cloud_flag(self):
        sats = [_make_satellite(cloud=60.0)]
        result = calculate_mrv([], sats, [])
        assert any("HIGH_CLOUD_COVER" in f for f in result.flags)

    def test_low_ndvi_inconsistency(self):
        sats = [_make_satellite(ndvi=0.1)]  # < 0.2
        result = calculate_mrv([], sats, [])
        assert any("LOW_NDVI_FOR_ACTIVE_CROP" in i for i in result.inconsistencies)

    def test_avg_ndvi_returned(self):
        sats = [_make_satellite(ndvi=0.4), _make_satellite(ndvi=0.6)]
        result = calculate_mrv([], sats, [])
        assert result.avg_ndvi == pytest.approx(0.5, abs=0.01)


class TestMRVDroneFlags:
    def test_missing_drone_flag(self):
        result = calculate_mrv([], [], [])
        assert "MISSING_DRONE_DATA" in result.flags

    def test_high_anomaly_flag(self):
        drones = [_make_drone(anomaly=75.0)]
        result = calculate_mrv([], [], drones)
        assert any("DRONE_ANOMALY_DETECTED" in f for f in result.flags)

    def test_excessive_water_flag(self):
        drones = [_make_drone(water=90.0)]
        result = calculate_mrv([], [], drones)
        assert any("EXCESSIVE_STANDING_WATER" in f for f in result.flags)

    def test_low_vegetation_inconsistency(self):
        drones = [_make_drone(vegetation=10.0)]
        result = calculate_mrv([], [], drones)
        assert any("LOW_DRONE_VEGETATION_COVER" in i for i in result.inconsistencies)

    def test_avg_drone_vegetation_returned(self):
        drones = [_make_drone(vegetation=60.0), _make_drone(vegetation=80.0)]
        result = calculate_mrv([], [], drones)
        assert result.avg_drone_vegetation == pytest.approx(70.0, abs=0.1)


class TestMRVConsistency:
    def test_no_inconsistencies_score_100(self):
        result = calculate_mrv(
            [_make_sensor() for _ in range(14)],
            [_make_satellite()],
            [_make_drone()],
        )
        assert result.consistency_score == 100.0

    def test_one_inconsistency_reduces_score(self):
        # low NDVI triggers inconsistency
        sats = [_make_satellite(ndvi=0.1)]
        result = calculate_mrv([], sats, [])
        assert result.consistency_score == 80.0

    def test_two_inconsistencies_reduces_more(self):
        sats = [_make_satellite(ndvi=0.1)]
        drones = [_make_drone(vegetation=10.0)]
        result = calculate_mrv([], sats, drones)
        assert result.consistency_score == 60.0

    def test_scores_clamped_to_zero(self):
        # Multiple flags that drive confidence below 0
        sensors = []  # no sensors: -20
        sats = [
            _make_satellite(health=VegetationHealth.POOR, flood=FloodRisk.HIGH, cloud=60.0)
        ]   # poor: -10, flood: -15, cloud: -5 + missing drone: -5 = -35 more
        result = calculate_mrv(sensors, sats, [])
        assert result.confidence_score >= 0.0

    def test_max_confidence_100(self):
        sensors = [_make_sensor() for _ in range(14)]
        sats = [_make_satellite()]
        drones = [_make_drone()]
        result = calculate_mrv(sensors, sats, drones)
        assert result.confidence_score <= 100.0
