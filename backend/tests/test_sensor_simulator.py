"""
Phase 3 — Sensor Simulator unit tests
Tests the simulation service directly (no HTTP, no DB).
"""
import pytest
from datetime import datetime, timezone
from app.services.sensor_simulator import simulate_sensor_readings
from app.models.sensor import SensorSourceType


def _sim(days=10, farm_id=1, cycle_id=1, crop="Paddy"):
    return simulate_sensor_readings(
        farm_id=farm_id,
        crop_cycle_id=cycle_id,
        crop_type=crop,
        number_of_days=days,
    )


class TestSimulatorCount:
    def test_generates_exact_count(self):
        readings = _sim(days=30)
        assert len(readings) == 30

    def test_generates_one_reading(self):
        assert len(_sim(days=1)) == 1

    def test_generates_365_readings(self):
        assert len(_sim(days=365)) == 365


class TestSimulatorRanges:
    """All values must stay within spec."""

    def _check(self, days=60):
        return _sim(days=days)

    def test_soil_moisture_in_range(self):
        for r in self._check():
            assert 0 <= r.soil_moisture <= 100, f"soil_moisture={r.soil_moisture}"

    def test_water_depth_in_range(self):
        for r in self._check():
            assert 0 <= r.water_depth_cm <= 30, f"water_depth={r.water_depth_cm}"

    def test_temperature_in_range(self):
        for r in self._check():
            assert 15 <= r.temperature_c <= 45, f"temp={r.temperature_c}"

    def test_humidity_in_range(self):
        for r in self._check():
            assert 20 <= r.humidity <= 100, f"humidity={r.humidity}"

    def test_rainfall_in_range(self):
        for r in self._check():
            assert 0 <= r.rainfall_mm <= 100, f"rainfall={r.rainfall_mm}"

    def test_data_quality_in_range(self):
        for r in self._check():
            assert 0 <= r.data_quality_score <= 100, f"quality={r.data_quality_score}"

    def test_methane_non_negative(self):
        for r in self._check():
            assert r.estimated_methane >= 0, f"methane={r.estimated_methane}"


class TestSimulatorEnvironmentalLogic:
    """Readings must exhibit correlated environmental patterns, not pure noise."""

    def test_timestamps_are_sequential(self):
        readings = _sim(days=10)
        times = [r.reading_time for r in readings]
        for i in range(1, len(times)):
            assert times[i] > times[i - 1], "Timestamps not ascending"

    def test_timestamps_span_correct_duration(self):
        readings = _sim(days=10)
        delta = readings[-1].reading_time - readings[0].reading_time
        assert delta.days == 9  # 10 readings, 9 gaps

    def test_high_rainfall_days_have_higher_soil_moisture(self):
        readings = _sim(days=60)
        high_rain = [r for r in readings if r.rainfall_mm > 15]
        low_rain  = [r for r in readings if r.rainfall_mm < 1]
        if high_rain and low_rain:
            avg_high = sum(r.soil_moisture for r in high_rain) / len(high_rain)
            avg_low  = sum(r.soil_moisture for r in low_rain)  / len(low_rain)
            assert avg_high >= avg_low, "High-rain days should have ≥ soil moisture vs no-rain"

    def test_readings_vary_not_constant(self):
        readings = _sim(days=30)
        moistures = [r.soil_moisture for r in readings]
        assert max(moistures) - min(moistures) > 5, "Soil moisture should show variation"

    def test_paddy_methane_higher_than_wheat_on_average(self):
        paddy = _sim(days=30, crop="Paddy")
        wheat = _sim(days=30, crop="Wheat")
        avg_paddy = sum(r.estimated_methane for r in paddy) / len(paddy)
        avg_wheat = sum(r.estimated_methane for r in wheat) / len(wheat)
        assert avg_paddy > avg_wheat

    def test_source_type_is_simulated(self):
        for r in _sim(days=5):
            assert r.source_type == SensorSourceType.SIMULATED

    def test_farm_id_and_cycle_id_match(self):
        readings = _sim(days=5, farm_id=7, cycle_id=3)
        for r in readings:
            assert r.farm_id == 7
            assert r.crop_cycle_id == 3

    def test_deterministic_same_inputs(self):
        r1 = _sim(days=10, farm_id=1, cycle_id=1, crop="Paddy")
        r2 = _sim(days=10, farm_id=1, cycle_id=1, crop="Paddy")
        for a, b in zip(r1, r2):
            assert a.soil_moisture == b.soil_moisture
            assert a.estimated_methane == b.estimated_methane

    def test_different_farms_produce_different_data(self):
        f1 = _sim(days=10, farm_id=1, cycle_id=1)
        f2 = _sim(days=10, farm_id=2, cycle_id=1)
        # At least some readings should differ
        diffs = sum(
            1 for a, b in zip(f1, f2)
            if abs(a.soil_moisture - b.soil_moisture) > 0.01
        )
        assert diffs > 0
