"""
Phase 7 — Recommendation engine unit tests.
"""
import pytest

from app.services.mrv_engine import MRVResult
from app.services.fraud_detection import FraudResult, FraudLevel
from app.services.recommendation_engine import generate_recommendations, RecommendationReport
from app.models.verification import RiskLevel


def _mrv(confidence=80.0, consistency=100.0, flags=None, inconsistencies=None):
    return MRVResult(
        confidence_score=confidence,
        consistency_score=consistency,
        flags=flags or [],
        inconsistencies=inconsistencies or [],
    )


def _fraud(score=5.0, level=FraudLevel.LOW, detections=None):
    return FraudResult(
        fraud_score=score,
        fraud_level=level,
        detections=detections or [],
    )


class TestRecommendationActions:
    def test_low_risk_low_fraud_approve(self):
        result = generate_recommendations(_mrv(), _fraud(), RiskLevel.LOW, 10.0)
        assert result.overall_action == "APPROVE"
        assert result.priority == "LOW"

    def test_medium_risk_manual_review(self):
        result = generate_recommendations(_mrv(), _fraud(), RiskLevel.MEDIUM, 45.0)
        assert result.overall_action == "MANUAL_REVIEW"
        assert result.priority == "MEDIUM"

    def test_high_risk_manual_review(self):
        result = generate_recommendations(
            _mrv(), _fraud(score=15.0, level=FraudLevel.LOW), RiskLevel.HIGH, 70.0
        )
        assert result.overall_action == "MANUAL_REVIEW"
        assert result.priority == "HIGH"

    def test_medium_fraud_manual_review(self):
        result = generate_recommendations(
            _mrv(), _fraud(score=40.0, level=FraudLevel.MEDIUM), RiskLevel.LOW, 10.0
        )
        assert result.overall_action == "MANUAL_REVIEW"

    def test_high_fraud_reject(self):
        result = generate_recommendations(
            _mrv(), _fraud(score=60.0, level=FraudLevel.HIGH), RiskLevel.LOW, 10.0
        )
        assert result.overall_action == "REJECT"
        assert result.priority == "HIGH"

    def test_critical_fraud_reject(self):
        result = generate_recommendations(
            _mrv(), _fraud(score=90.0, level=FraudLevel.CRITICAL), RiskLevel.HIGH, 80.0
        )
        assert result.overall_action == "REJECT"
        assert result.priority == "CRITICAL"


class TestRecommendationText:
    def test_missing_satellite_recommendation(self):
        mrv = _mrv(flags=["MISSING_SATELLITE_DATA"])
        result = generate_recommendations(mrv, _fraud(), RiskLevel.LOW, 10.0)
        assert any("satellite" in r.lower() for r in result.recommendations)

    def test_missing_drone_recommendation(self):
        mrv = _mrv(flags=["MISSING_DRONE_DATA"])
        result = generate_recommendations(mrv, _fraud(), RiskLevel.LOW, 10.0)
        assert any("drone" in r.lower() for r in result.recommendations)

    def test_low_sensor_quality_recommendation(self):
        mrv = _mrv(flags=["LOW_SENSOR_QUALITY (avg=55.0)"])
        result = generate_recommendations(mrv, _fraud(), RiskLevel.LOW, 10.0)
        assert any("sensor" in r.lower() or "quality" in r.lower() for r in result.recommendations)

    def test_poor_vegetation_recommendation(self):
        mrv = _mrv(flags=["POOR_VEGETATION_DETECTED (1 observations)"])
        result = generate_recommendations(mrv, _fraud(), RiskLevel.LOW, 10.0)
        assert any("vegetation" in r.lower() for r in result.recommendations)

    def test_drone_anomaly_recommendation(self):
        mrv = _mrv(flags=["DRONE_ANOMALY_DETECTED (avg_score=75.0)"])
        result = generate_recommendations(mrv, _fraud(), RiskLevel.LOW, 10.0)
        assert any("anomaly" in r.lower() or "drone" in r.lower() for r in result.recommendations)

    def test_low_ndvi_inconsistency_recommendation(self):
        mrv = _mrv(inconsistencies=["LOW_NDVI_FOR_ACTIVE_CROP (avg_ndvi=0.100)"])
        result = generate_recommendations(mrv, _fraud(), RiskLevel.LOW, 10.0)
        assert any("ndvi" in r.lower() or "field" in r.lower() for r in result.recommendations)

    def test_temporal_gap_fraud_recommendation(self):
        fraud = _fraud(detections=["TEMPORAL_GAP: observation window is only 3 day(s)"])
        result = generate_recommendations(_mrv(), fraud, RiskLevel.LOW, 10.0)
        assert any("7 days" in r or "window" in r.lower() for r in result.recommendations)


class TestRecommendationSummary:
    def test_summary_contains_key_fields(self):
        mrv = _mrv(confidence=75.0)
        fraud = _fraud(score=10.0, level=FraudLevel.LOW)
        result = generate_recommendations(mrv, fraud, RiskLevel.LOW, 15.0)
        assert "75" in result.summary
        assert "10" in result.summary
        assert "LOW" in result.summary

    def test_returns_recommendation_report(self):
        result = generate_recommendations(_mrv(), _fraud(), RiskLevel.LOW, 5.0)
        assert isinstance(result, RecommendationReport)
        assert isinstance(result.recommendations, list)
        assert len(result.recommendations) >= 1
