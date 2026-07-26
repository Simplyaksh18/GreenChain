"""
Phase 7 — Fraud detection engine unit tests.

Tests app/services/fraud_detection.py logic directly.
Uses types.SimpleNamespace to avoid SQLAlchemy ORM initialisation overhead.
"""
import pytest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

from app.services.fraud_detection import detect_fraud, FraudLevel, FraudResult
from app.models.satellite_observation import VegetationHealth, FloodRisk, SatelliteSource
from app.models.sensor import SensorSourceType
from app.models.carbon_report import ReportStatus


def _make_farm(land_area=5.0):
    return SimpleNamespace(id=1, land_area_acres=land_area, is_approved=True)


def _make_report(estimated_credits=3, baseline_methane=100.0, reduction=30.0):
    return SimpleNamespace(
        id=1,
        estimated_credits=estimated_credits,
        baseline_methane_kg=baseline_methane,
        methane_reduction_kg=reduction,
        co2e_reduction_tonnes=reduction * 0.001 * 27.2,
        current_methane_kg=baseline_methane - reduction,
        status=ReportStatus.VERIFIED,
    )


def _make_sensor(soil_moisture=62.0, days_ago=0):
    base = datetime(2024, 6, 1, tzinfo=timezone.utc) + timedelta(days=days_ago)
    return SimpleNamespace(
        farm_id=1,
        crop_cycle_id=1,
        reading_time=base,
        soil_moisture=soil_moisture,
        water_depth_cm=5.0,
        temperature_c=30.0,
        humidity=70.0,
        rainfall_mm=0.0,
        estimated_methane=0.5,
        data_quality_score=85.0,
        source_type=SensorSourceType.SIMULATED,
    )


def _make_satellite(ndwi=0.2, health=VegetationHealth.GOOD):
    return SimpleNamespace(
        ndvi=0.5,
        ndwi=ndwi,
        vegetation_health=health,
        flood_risk=FloodRisk.NONE,
        cloud_cover_percent=10.0,
        source=SatelliteSource.SATELLITE_SIMULATED,
    )


def _make_drone(anomaly=10.0, vegetation=70.0, water=15.0):
    return SimpleNamespace(
        vegetation_cover_percent=vegetation,
        standing_water_percent=water,
        anomaly_score=anomaly,
    )


class TestFraudDetectionBaseline:
    def test_low_risk_clean_data(self):
        farm = _make_farm()
        report = _make_report()
        sensors = [_make_sensor(days_ago=i) for i in range(14)]
        sats = [_make_satellite()]
        drones = [_make_drone()]
        result = detect_fraud(report, farm, sensors, sats, drones)
        assert isinstance(result, FraudResult)
        assert result.fraud_level == FraudLevel.LOW
        assert result.fraud_score <= 25

    def test_returns_fraud_result_type(self):
        result = detect_fraud(_make_report(), _make_farm(), [], [], [])
        assert isinstance(result, FraudResult)
        assert isinstance(result.detections, list)


class TestSensorSatelliteMismatch:
    def test_high_moisture_low_ndwi_detected(self):
        farm = _make_farm()
        report = _make_report()
        sensors = [_make_sensor(soil_moisture=70.0, days_ago=i) for i in range(14)]
        sats = [_make_satellite(ndwi=-0.2)]  # very dry satellite
        result = detect_fraud(report, farm, sensors, sats, [])
        assert any("SENSOR_SATELLITE_MISMATCH" in d for d in result.detections)

    def test_no_mismatch_when_both_agree(self):
        farm = _make_farm()
        report = _make_report()
        sensors = [_make_sensor(soil_moisture=50.0, days_ago=i) for i in range(5)]
        sats = [_make_satellite(ndwi=0.3)]
        result = detect_fraud(report, farm, sensors, sats, [])
        assert not any("SENSOR_SATELLITE_MISMATCH" in d for d in result.detections)


class TestCreditSpike:
    def test_excessive_credits_per_acre_detected(self):
        farm = _make_farm(land_area=1.0)   # 1 acre
        report = _make_report(estimated_credits=10)  # 10 credits/acre > 5 threshold
        result = detect_fraud(report, farm, [], [], [])
        assert any("SUDDEN_CREDIT_SPIKE" in d for d in result.detections)

    def test_normal_credits_no_flag(self):
        farm = _make_farm(land_area=10.0)
        report = _make_report(estimated_credits=5)  # 0.5 credits/acre
        result = detect_fraud(report, farm, [], [], [])
        assert not any("SUDDEN_CREDIT_SPIKE" in d for d in result.detections)


class TestDataCompletenessFraud:
    def test_no_data_at_all_detected(self):
        farm = _make_farm()
        report = _make_report()
        # < 7 readings, no satellite, no drone
        sensors = [_make_sensor()]  # only 1
        result = detect_fraud(report, farm, sensors, [], [])
        assert any("DATA_COMPLETENESS_FRAUD" in d for d in result.detections)

    def test_enough_sensors_no_flag(self):
        farm = _make_farm()
        report = _make_report()
        sensors = [_make_sensor(days_ago=i) for i in range(8)]
        result = detect_fraud(report, farm, sensors, [], [])
        assert not any("DATA_COMPLETENESS_FRAUD" in d for d in result.detections)


class TestAnomalySpike:
    def test_high_anomaly_detected(self):
        farm = _make_farm()
        report = _make_report()
        drones = [_make_drone(anomaly=80.0)]
        result = detect_fraud(report, farm, [], [], drones)
        assert any("ANOMALY_SCORE_SPIKE" in d for d in result.detections)

    def test_normal_anomaly_no_flag(self):
        farm = _make_farm()
        report = _make_report()
        drones = [_make_drone(anomaly=30.0)]
        result = detect_fraud(report, farm, [], [], drones)
        assert not any("ANOMALY_SCORE_SPIKE" in d for d in result.detections)


class TestVegetationMismatch:
    def test_poor_veg_high_moisture_detected(self):
        farm = _make_farm()
        report = _make_report()
        sensors = [_make_sensor(soil_moisture=70.0) for _ in range(5)]
        # Majority POOR
        sats = [_make_satellite(health=VegetationHealth.POOR) for _ in range(3)]
        result = detect_fraud(report, farm, sensors, sats, [])
        assert any("VEGETATION_MISMATCH" in d for d in result.detections)


class TestTemporalGap:
    def test_short_window_detected(self):
        farm = _make_farm()
        report = _make_report()
        # 2 readings only 2 days apart
        sensors = [_make_sensor(days_ago=0), _make_sensor(days_ago=2)]
        result = detect_fraud(report, farm, sensors, [], [])
        assert any("TEMPORAL_GAP" in d for d in result.detections)

    def test_long_enough_window_no_flag(self):
        farm = _make_farm()
        report = _make_report()
        sensors = [_make_sensor(days_ago=0), _make_sensor(days_ago=10)]
        result = detect_fraud(report, farm, sensors, [], [])
        assert not any("TEMPORAL_GAP" in d for d in result.detections)


class TestFraudLevelMapping:
    def test_score_0_is_low(self):
        from app.services.fraud_detection import _map_fraud_level
        assert _map_fraud_level(0) == FraudLevel.LOW

    def test_score_25_is_low(self):
        from app.services.fraud_detection import _map_fraud_level
        assert _map_fraud_level(25) == FraudLevel.LOW

    def test_score_26_is_medium(self):
        from app.services.fraud_detection import _map_fraud_level
        assert _map_fraud_level(26) == FraudLevel.MEDIUM

    def test_score_55_is_medium(self):
        from app.services.fraud_detection import _map_fraud_level
        assert _map_fraud_level(55) == FraudLevel.MEDIUM

    def test_score_56_is_high(self):
        from app.services.fraud_detection import _map_fraud_level
        assert _map_fraud_level(56) == FraudLevel.HIGH

    def test_score_80_is_high(self):
        from app.services.fraud_detection import _map_fraud_level
        assert _map_fraud_level(80) == FraudLevel.HIGH

    def test_score_81_is_critical(self):
        from app.services.fraud_detection import _map_fraud_level
        assert _map_fraud_level(81) == FraudLevel.CRITICAL

    def test_score_100_is_critical(self):
        from app.services.fraud_detection import _map_fraud_level
        assert _map_fraud_level(100) == FraudLevel.CRITICAL

    def test_score_clamped_to_100(self):
        # All detections firing simultaneously
        farm = _make_farm(land_area=0.5)  # triggers credit spike
        report = _make_report(estimated_credits=20)
        # 1 sensor (< 7), no satellite, no drone → completeness fraud
        # short temporal gap not triggered with 1 reading
        sensors = [_make_sensor(soil_moisture=70.0)]
        sats = [
            _make_satellite(ndwi=-0.2, health=VegetationHealth.POOR)
            for _ in range(3)
        ]
        drones = [_make_drone(anomaly=80.0)]
        result = detect_fraud(report, farm, sensors, sats, drones)
        assert result.fraud_score <= 100.0
