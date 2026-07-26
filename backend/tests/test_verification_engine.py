"""
Phase 4 — Verification Engine service unit tests.
"""
import pytest
from app.services.verification_engine import calculate_risk
from app.models.verification import RiskLevel, Recommendation


# ── Helpers ───────────────────────────────────────────────────────────────────
def _risk(**overrides):
    defaults = dict(
        num_readings=20,
        avg_quality_score=85.0,
        num_evidence_files=3,
        farm_is_approved=True,
        baseline_methane_kg=10.0,
        methane_reduction_kg=2.0,
        estimated_credits=1,
    )
    defaults.update(overrides)
    return calculate_risk(**defaults)


# ── Risk factor tests ─────────────────────────────────────────────────────────
class TestRiskFactors:
    def test_clean_profile_is_low_risk(self):
        r = _risk()
        assert r.risk_level == RiskLevel.LOW

    def test_insufficient_readings_adds_30(self):
        clean = _risk()
        with_low = _risk(num_readings=10)
        assert with_low.risk_score == clean.risk_score + 30

    def test_low_quality_adds_25(self):
        clean = _risk()
        with_low = _risk(avg_quality_score=60.0)
        assert with_low.risk_score == clean.risk_score + 25

    def test_no_evidence_adds_20(self):
        clean = _risk()
        no_ev = _risk(num_evidence_files=0)
        assert no_ev.risk_score == clean.risk_score + 20

    def test_unapproved_farm_adds_20(self):
        clean = _risk()
        not_approved = _risk(farm_is_approved=False)
        assert not_approved.risk_score == clean.risk_score + 20

    def test_high_reduction_pct_adds_25(self):
        # 50% reduction > 40% threshold
        clean = _risk(baseline_methane_kg=10.0, methane_reduction_kg=2.0)
        high_red = _risk(baseline_methane_kg=10.0, methane_reduction_kg=5.0)
        assert high_red.risk_score == clean.risk_score + 25

    def test_high_credits_adds_15(self):
        clean = _risk(estimated_credits=5)
        high_cr = _risk(estimated_credits=11)
        assert high_cr.risk_score == clean.risk_score + 15

    def test_zero_baseline_skips_reduction_check(self):
        # No division by zero
        r = _risk(baseline_methane_kg=0.0, methane_reduction_kg=0.0)
        assert r.risk_score >= 0

    def test_score_capped_at_100(self):
        # All factors simultaneously
        r = _risk(
            num_readings=5,
            avg_quality_score=50.0,
            num_evidence_files=0,
            farm_is_approved=False,
            baseline_methane_kg=10.0,
            methane_reduction_kg=6.0,
            estimated_credits=15,
        )
        assert r.risk_score <= 100.0

    def test_factors_triggered_list(self):
        r = _risk(num_readings=5, num_evidence_files=0)
        assert len(r.factors_triggered) >= 2


# ── Risk level mapping ────────────────────────────────────────────────────────
class TestRiskLevelMapping:
    def test_score_0_is_low(self):
        # Perfect scenario, but at minimum we need at least one factor for 0
        # score ≤ 30 → LOW
        r = _risk()
        assert r.risk_score <= 30
        assert r.risk_level == RiskLevel.LOW
        assert r.recommendation == Recommendation.APPROVE

    def test_score_31_to_65_is_medium(self):
        # +30 readings + some more
        r = _risk(num_readings=5, num_evidence_files=0)
        # risk = 30 + 20 = 50 → MEDIUM
        assert 31 <= r.risk_score <= 65
        assert r.risk_level == RiskLevel.MEDIUM
        assert r.recommendation == Recommendation.MANUAL_REVIEW

    def test_score_above_65_is_high(self):
        r = _risk(
            num_readings=5,
            avg_quality_score=50.0,
            num_evidence_files=0,
            farm_is_approved=False,
        )
        # 30 + 25 + 20 + 20 = 95 → HIGH
        assert r.risk_score > 65
        assert r.risk_level == RiskLevel.HIGH
        assert r.recommendation == Recommendation.REJECT


# ── Edge cases ────────────────────────────────────────────────────────────────
class TestEdgeCases:
    def test_exactly_14_readings_no_penalty(self):
        r_below = _risk(num_readings=13)
        r_exact = _risk(num_readings=14)
        assert r_exact.risk_score < r_below.risk_score

    def test_exactly_40pct_reduction_no_penalty(self):
        # exactly 40% → not > 40%, so no penalty
        r_exact = _risk(baseline_methane_kg=10.0, methane_reduction_kg=4.0)
        r_clean = _risk(baseline_methane_kg=10.0, methane_reduction_kg=2.0)
        assert r_exact.risk_score == r_clean.risk_score

    def test_exactly_10_credits_no_penalty(self):
        r = _risk(estimated_credits=10)
        r_clean = _risk(estimated_credits=5)
        assert r.risk_score == r_clean.risk_score

    def test_returns_result_dataclass(self):
        r = _risk()
        assert hasattr(r, "risk_score")
        assert hasattr(r, "risk_level")
        assert hasattr(r, "recommendation")
        assert hasattr(r, "factors_triggered")
