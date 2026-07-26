"""
Recommendation Engine — Phase 7.

Generates human-readable recommendations for a carbon report based on
MRV confidence, fraud score, risk score, and the individual flags raised.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.mrv_engine import MRVResult
from app.services.fraud_detection import FraudResult, FraudLevel
from app.models.verification import RiskLevel


@dataclass
class RecommendationReport:
    overall_action: str              # "APPROVE" | "MANUAL_REVIEW" | "REJECT"
    priority: str                    # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    recommendations: list[str] = field(default_factory=list)
    summary: str = ""


def generate_recommendations(
    mrv_result: MRVResult,
    fraud_result: FraudResult,
    risk_level: RiskLevel,
    risk_score: float,
) -> RecommendationReport:
    """
    Combine MRV, fraud, and verification risk into actionable recommendations.
    """
    recommendations: list[str] = []

    # ── Action based on fraud level ────────────────────────────────────────────
    if fraud_result.fraud_level == FraudLevel.CRITICAL:
        overall_action = "REJECT"
        priority = "CRITICAL"
        recommendations.append(
            "CRITICAL fraud indicators detected — reject report and escalate "
            "for investigation."
        )
    elif fraud_result.fraud_level == FraudLevel.HIGH:
        overall_action = "REJECT"
        priority = "HIGH"
        recommendations.append(
            "High fraud risk detected — report should be rejected pending "
            "physical site inspection."
        )
    elif fraud_result.fraud_level == FraudLevel.MEDIUM or risk_level == RiskLevel.HIGH:
        overall_action = "MANUAL_REVIEW"
        priority = "HIGH"
        recommendations.append(
            "Moderate fraud risk or high verification risk — manual review "
            "by senior verifier required before approval."
        )
    elif risk_level == RiskLevel.MEDIUM:
        overall_action = "MANUAL_REVIEW"
        priority = "MEDIUM"
        recommendations.append(
            "Moderate risk level — recommend verifier spot-check evidence "
            "files and sensor data before approval."
        )
    else:
        overall_action = "APPROVE"
        priority = "LOW"
        recommendations.append(
            "Low risk and no significant fraud indicators — report can be "
            "approved for carbon credit issuance."
        )

    # ── Specific flag-based recommendations ────────────────────────────────────
    if "MISSING_SATELLITE_DATA" in mrv_result.flags:
        recommendations.append(
            "No satellite observations found — upload Sentinel-2 or Landsat "
            "imagery for this crop cycle to improve MRV confidence."
        )

    if "MISSING_DRONE_DATA" in mrv_result.flags:
        recommendations.append(
            "No drone observations found — schedule a drone survey to provide "
            "ground-truth data for this report."
        )

    if "INSUFFICIENT_SENSOR_READINGS" in " ".join(mrv_result.flags):
        recommendations.append(
            "Fewer than 7 sensor readings were recorded — ensure IoT sensors "
            "are operational and submit additional readings."
        )

    if "LOW_SENSOR_QUALITY" in " ".join(mrv_result.flags):
        recommendations.append(
            "Average sensor data quality is below 70% — check sensor "
            "calibration and replace faulty units."
        )

    if "POOR_VEGETATION_DETECTED" in " ".join(mrv_result.flags):
        recommendations.append(
            "Satellite imagery indicates poor vegetation health — verify "
            "crop status and consider adjusting reduction practice claims."
        )

    if "HIGH_FLOOD_RISK" in " ".join(mrv_result.flags):
        recommendations.append(
            "High flood risk detected in satellite observations — assess "
            "impact on methane emissions and recalculate baseline if required."
        )

    if "DRONE_ANOMALY_DETECTED" in " ".join(mrv_result.flags):
        recommendations.append(
            "Drone anomaly scores are elevated — investigate suspected "
            "crop disease, pest damage, or field irregularities."
        )

    for inc in mrv_result.inconsistencies:
        if "LOW_NDVI_FOR_ACTIVE_CROP" in inc:
            recommendations.append(
                "Satellite NDVI is very low for an active paddy crop — "
                "verify that the correct field boundaries are registered."
            )
        if "LOW_DRONE_VEGETATION_COVER" in inc:
            recommendations.append(
                "Drone imagery shows very low vegetation cover — confirm "
                "crop cycle dates and actual field conditions."
            )

    for det in fraud_result.detections:
        if "SENSOR_SATELLITE_MISMATCH" in det:
            recommendations.append(
                "Sensor moisture readings do not match satellite water index — "
                "independent calibration check recommended."
            )
        if "SUDDEN_CREDIT_SPIKE" in det:
            recommendations.append(
                "Credit-per-acre ratio exceeds expected range — verify land "
                "area registration accuracy."
            )
        if "TEMPORAL_GAP" in det:
            recommendations.append(
                "Sensor data spans fewer than 7 days — a longer observation "
                "window is required for credible credit calculation."
            )

    # ── MRV confidence summary ─────────────────────────────────────────────────
    conf = mrv_result.confidence_score
    summary = (
        f"MRV confidence: {conf:.0f}/100 | "
        f"Consistency: {mrv_result.consistency_score:.0f}/100 | "
        f"Fraud score: {fraud_result.fraud_score:.0f}/100 ({fraud_result.fraud_level}) | "
        f"Risk: {risk_score:.0f}/100 ({risk_level}) | "
        f"Action: {overall_action}"
    )

    return RecommendationReport(
        overall_action=overall_action,
        priority=priority,
        recommendations=recommendations,
        summary=summary,
    )
