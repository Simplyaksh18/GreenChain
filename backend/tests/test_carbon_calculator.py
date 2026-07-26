"""
Phase 4 — Carbon Calculator service unit tests.
Uses SimpleNamespace mock objects to avoid DB dependency.
"""
import math
import pytest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.carbon_calculator import (
    calculate_baseline_methane,
    calculate_current_methane,
    calculate_carbon_report,
    generate_report_hash,
    InsufficientReadingsError,
    MIN_READINGS,
    GWP_CH4,
)


def _reading(methane: float, day: int) -> SimpleNamespace:
    """Minimal mock sensor reading."""
    return SimpleNamespace(
        estimated_methane=methane,
        reading_time=datetime(2024, 6, 1, tzinfo=timezone.utc) + timedelta(days=day),
        data_quality_score=85.0,
    )


def _readings(values: list) -> list:
    return [_reading(v, i) for i, v in enumerate(values)]


# ── Baseline ──────────────────────────────────────────────────────────────────
class TestBaselineCalc:
    def test_uses_first_7_readings(self):
        # readings 0–6 have methane=10; readings 7-13 have methane=5
        r = _readings([10]*7 + [5]*7)
        baseline = calculate_baseline_methane(r)
        assert abs(baseline - 10.0) < 1e-4

    def test_sorted_by_reading_time(self):
        # Pass in reversed order — still picks earliest 7
        r = list(reversed(_readings([10]*7 + [5]*7)))
        baseline = calculate_baseline_methane(r)
        assert abs(baseline - 10.0) < 1e-4

    def test_fewer_than_7_uses_all(self):
        r = _readings([4.0, 4.0, 4.0])
        baseline = calculate_baseline_methane(r)
        assert abs(baseline - 4.0) < 1e-4

    def test_empty_raises(self):
        with pytest.raises(InsufficientReadingsError):
            calculate_baseline_methane([])


# ── Current ───────────────────────────────────────────────────────────────────
class TestCurrentCalc:
    def test_uses_latest_7_readings(self):
        # readings 0–6 have methane=10; readings 7-13 have methane=5
        r = _readings([10]*7 + [5]*7)
        current = calculate_current_methane(r)
        assert abs(current - 5.0) < 1e-4

    def test_fewer_than_7_uses_all(self):
        r = _readings([3.0, 3.0, 3.0])
        current = calculate_current_methane(r)
        assert abs(current - 3.0) < 1e-4


# ── Full report calculation ───────────────────────────────────────────────────
class TestCarbonReport:
    def _calc(self, baseline_vals, current_vals):
        r = _readings(baseline_vals + current_vals)
        return calculate_carbon_report(r, farm_id=1, crop_cycle_id=1)

    def test_positive_reduction(self):
        calc = self._calc([10]*7, [5]*7)
        assert abs(calc.methane_reduction_kg - 5.0) < 1e-3

    def test_negative_reduction_floored_at_zero(self):
        # current > baseline → no reduction
        calc = self._calc([5]*7, [10]*7)
        assert calc.methane_reduction_kg == 0.0

    def test_co2e_conversion(self):
        calc = self._calc([10]*7, [5]*7)
        expected_co2e = round(5.0 * GWP_CH4 / 1000, 6)
        assert abs(calc.co2e_reduction_tonnes - expected_co2e) < 1e-4

    def test_estimated_credits_floor(self):
        # co2e = 5 * 27.2 / 1000 = 0.136 → floor(0.136) = 0
        calc = self._calc([10]*7, [5]*7)
        assert calc.estimated_credits == math.floor(calc.co2e_reduction_tonnes)
        assert isinstance(calc.estimated_credits, int)

    def test_zero_reduction_zero_credits(self):
        calc = self._calc([5]*7, [10]*7)
        assert calc.estimated_credits == 0
        assert calc.co2e_reduction_tonnes == 0.0

    def test_hash_is_64_hex_chars(self):
        calc = self._calc([10]*7, [5]*7)
        assert len(calc.report_hash) == 64
        assert all(c in "0123456789abcdef" for c in calc.report_hash)

    def test_hash_deterministic(self):
        c1 = self._calc([10]*7, [5]*7)
        c2 = self._calc([10]*7, [5]*7)
        assert c1.report_hash == c2.report_hash

    def test_different_data_different_hash(self):
        c1 = self._calc([10]*7, [5]*7)
        c2 = self._calc([12]*7, [5]*7)
        assert c1.report_hash != c2.report_hash

    def test_insufficient_readings_raises(self):
        r = _readings([5.0] * 6)   # only 6 — below MIN_READINGS=7
        with pytest.raises(InsufficientReadingsError):
            calculate_carbon_report(r, 1, 1)

    def test_exactly_7_readings_accepted(self):
        r = _readings([5.0] * 7)
        calc = calculate_carbon_report(r, 1, 1)
        assert calc is not None

    def test_baseline_and_current_fields_returned(self):
        calc = self._calc([10]*7, [5]*7)
        assert calc.baseline_methane_kg > 0
        assert calc.current_methane_kg > 0
        assert calc.methane_reduction_kg >= 0
        assert calc.co2e_reduction_tonnes >= 0


# ── Hash util ─────────────────────────────────────────────────────────────────
class TestReportHash:
    def test_consistent_for_same_dict(self):
        d = {"a": 1, "b": 2}
        assert generate_report_hash(d) == generate_report_hash(d)

    def test_key_order_independent(self):
        h1 = generate_report_hash({"a": 1, "b": 2})
        h2 = generate_report_hash({"b": 2, "a": 1})
        assert h1 == h2
