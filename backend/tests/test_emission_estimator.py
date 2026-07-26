"""
Phase 3 — Emission Estimator unit tests
Tests the formula-based AI module directly (no HTTP, no DB).
"""
import pytest
from app.services.emission_estimator import estimate_methane, CROP_FACTORS, BASE_FACTOR


class TestMethaneFormula:
    """Core formula correctness."""

    def test_returns_result_object(self):
        r = estimate_methane(80, 12, 32, "Paddy")
        assert hasattr(r, "estimated_methane")
        assert hasattr(r, "confidence_score")
        assert hasattr(r, "explanation")

    def test_paddy_emits_more_than_wheat(self):
        paddy = estimate_methane(70, 10, 30, "Paddy")
        wheat = estimate_methane(70, 10, 30, "Wheat")
        assert paddy.estimated_methane > wheat.estimated_methane

    def test_paddy_emits_more_than_millet(self):
        paddy = estimate_methane(70, 10, 30, "Paddy")
        millet = estimate_methane(70, 10, 30, "Millet")
        assert paddy.estimated_methane > millet.estimated_methane

    def test_higher_water_depth_increases_methane(self):
        low  = estimate_methane(70, 5, 30, "Paddy")
        high = estimate_methane(70, 20, 30, "Paddy")
        assert high.estimated_methane > low.estimated_methane

    def test_higher_moisture_increases_methane(self):
        low  = estimate_methane(30, 10, 30, "Paddy")
        high = estimate_methane(90, 10, 30, "Paddy")
        assert high.estimated_methane > low.estimated_methane

    def test_higher_temperature_increases_methane(self):
        low  = estimate_methane(70, 10, 20, "Paddy")
        high = estimate_methane(70, 10, 40, "Paddy")
        assert high.estimated_methane > low.estimated_methane

    def test_zero_moisture_gives_zero_or_near_zero(self):
        r = estimate_methane(0, 10, 30, "Paddy")
        assert r.estimated_methane == 0.0

    def test_zero_water_depth_still_emits(self):
        # water_factor = 1 + 0/20 = 1.0, so methane > 0 when moisture > 0
        r = estimate_methane(50, 0, 30, "Paddy")
        assert r.estimated_methane > 0

    def test_estimated_methane_non_negative(self):
        for crop in ["Paddy", "Wheat", "Millet", "Maize"]:
            r = estimate_methane(50, 10, 30, crop)
            assert r.estimated_methane >= 0, f"Negative methane for {crop}"

    def test_crop_case_insensitive(self):
        r1 = estimate_methane(70, 10, 30, "Paddy")
        r2 = estimate_methane(70, 10, 30, "paddy")
        r3 = estimate_methane(70, 10, 30, "PADDY")
        assert r1.estimated_methane == r2.estimated_methane == r3.estimated_methane

    def test_unknown_crop_uses_default_factor(self):
        r = estimate_methane(70, 10, 30, "UnknownCrop")
        # default factor = 1.0; paddy = 1.5 → paddy should be higher
        paddy = estimate_methane(70, 10, 30, "Paddy")
        assert paddy.estimated_methane > r.estimated_methane

    def test_explanation_contains_factor_labels(self):
        r = estimate_methane(80, 12, 32, "Paddy")
        assert "base" in r.explanation
        assert "crop" in r.explanation
        assert "moisture" in r.explanation
        assert "water_depth" in r.explanation
        assert "temp" in r.explanation

    def test_explanation_contains_methane_value(self):
        r = estimate_methane(80, 12, 32, "Paddy")
        assert str(r.estimated_methane) in r.explanation

    def test_confidence_score_range(self):
        r = estimate_methane(70, 10, 30, "Paddy")
        assert 0 <= r.confidence_score <= 100

    def test_unknown_crop_lower_confidence(self):
        known   = estimate_methane(70, 10, 30, "Paddy")
        unknown = estimate_methane(70, 10, 30, "SomethingElse")
        assert unknown.confidence_score < known.confidence_score

    def test_formula_precision(self):
        # Manual calculation for paddy at moisture=100, depth=20, temp=30
        moisture_factor     = 100 / 100             # 1.0
        water_factor        = 1 + (20 / 20)         # 2.0
        temperature_factor  = 1 + ((30 - 20) / 50)  # 1.2
        crop_factor         = CROP_FACTORS["paddy"]  # 1.5
        expected = round(BASE_FACTOR * crop_factor * moisture_factor * water_factor * temperature_factor, 6)
        r = estimate_methane(100, 20, 30, "Paddy")
        assert abs(r.estimated_methane - expected) < 1e-4

    def test_all_four_crops_have_unique_emissions(self):
        crops = ["Paddy", "Wheat", "Millet", "Maize"]
        methanes = [estimate_methane(70, 10, 30, c).estimated_methane for c in crops]
        assert len(set(methanes)) == len(crops), "Each crop should produce unique emission"
