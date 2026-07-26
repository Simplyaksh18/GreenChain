"""
Verification Engine
===================
Computes a risk score for a carbon report and maps it to a risk level
and recommendation for the verifier.

Risk Factor Table
-----------------
Factor                                           | Points
-------------------------------------------------|-------
Fewer than 14 sensor readings                    | +30
Average data-quality score < 70                  | +25
No evidence files for the crop cycle             | +20
Farm not approved by FPO (is_approved = False)   | +20
Claimed reduction > 40 % of baseline methane     | +25
Estimated credits > 10                           | +15

Risk Level Mapping
------------------
  0 – 30  → LOW     → APPROVE
 31 – 65  → MEDIUM  → MANUAL_REVIEW
 66 – 100 → HIGH    → REJECT

Score is clamped to [0, 100].
"""
from __future__ import annotations
from dataclasses import dataclass

from app.models.verification import RiskLevel, Recommendation


# ── Risk thresholds ────────────────────────────────────────────────────────────
THRESHOLD_READINGS      = 14
THRESHOLD_QUALITY       = 70.0
THRESHOLD_REDUCTION_PCT = 0.40   # 40 %
THRESHOLD_CREDITS       = 10


@dataclass
class RiskResult:
    risk_score: float
    risk_level: RiskLevel
    recommendation: Recommendation
    factors_triggered: list[str]


def calculate_risk(
    num_readings: int,
    avg_quality_score: float,
    num_evidence_files: int,
    farm_is_approved: bool,
    baseline_methane_kg: float,
    methane_reduction_kg: float,
    estimated_credits: int,
) -> RiskResult:
    """
    Calculate a risk score from 0–100 and derive level + recommendation.

    Parameters
    ----------
    num_readings         : Total sensor readings for the crop cycle
    avg_quality_score    : Mean data_quality_score across all readings (0–100)
    num_evidence_files   : Evidence files attached to this crop cycle
    farm_is_approved     : Whether the farm has been FPO-approved
    baseline_methane_kg  : Baseline methane from the carbon report
    methane_reduction_kg : Claimed reduction (already floored at 0)
    estimated_credits    : Integer credits claimed in the report
    """
    score = 0.0
    triggered: list[str] = []

    # ── Insufficient sensor data ──────────────────────────────────────────
    if num_readings < THRESHOLD_READINGS:
        score += 30
        triggered.append(
            f"Insufficient readings: {num_readings} < {THRESHOLD_READINGS} required (+30)"
        )

    # ── Low data quality ──────────────────────────────────────────────────
    if num_readings > 0 and avg_quality_score < THRESHOLD_QUALITY:
        score += 25
        triggered.append(
            f"Low avg quality score: {avg_quality_score:.1f} < {THRESHOLD_QUALITY} (+25)"
        )

    # ── No evidence ───────────────────────────────────────────────────────
    if num_evidence_files == 0:
        score += 20
        triggered.append("No evidence files uploaded (+20)")

    # ── Farm not FPO-approved ─────────────────────────────────────────────
    if not farm_is_approved:
        score += 20
        triggered.append("Farm not approved by FPO (+20)")

    # ── Suspicious reduction claim ────────────────────────────────────────
    if baseline_methane_kg > 0:
        reduction_pct = methane_reduction_kg / baseline_methane_kg
        if reduction_pct > THRESHOLD_REDUCTION_PCT:
            score += 25
            triggered.append(
                f"High claimed reduction: {reduction_pct*100:.1f}% > {THRESHOLD_REDUCTION_PCT*100:.0f}% (+25)"
            )

    # ── Very high credit claim ────────────────────────────────────────────
    if estimated_credits > THRESHOLD_CREDITS:
        score += 15
        triggered.append(
            f"High credit claim: {estimated_credits} > {THRESHOLD_CREDITS} (+15)"
        )

    # ── Clamp and map ─────────────────────────────────────────────────────
    risk_score = round(min(score, 100.0), 1)
    risk_level, recommendation = _map_risk(risk_score)

    return RiskResult(
        risk_score=risk_score,
        risk_level=risk_level,
        recommendation=recommendation,
        factors_triggered=triggered,
    )


def _map_risk(score: float) -> tuple[RiskLevel, Recommendation]:
    if score <= 30:
        return RiskLevel.LOW, Recommendation.APPROVE
    if score <= 65:
        return RiskLevel.MEDIUM, Recommendation.MANUAL_REVIEW
    return RiskLevel.HIGH, Recommendation.REJECT
