"""
Credit Eligibility Engine — Phase 11

Explains why a carbon report does or does not qualify for credit issuance.
Returns structured explanation with current values vs. required thresholds.
"""
from dataclasses import dataclass
from typing import Optional


CREDIT_ISSUANCE_THRESHOLD = 1.0   # Minimum tCO2e required for 1 tradable credit
GWP_METHANE = 27.2                # AR6 100-year GWP for CH4


@dataclass
class EligibilityResult:
    eligible: bool
    reason: str
    current_co2e: float
    required_co2e: float
    current_credits: int
    # Breakdown
    baseline_methane_kg: float
    current_methane_kg: float
    methane_reduction_kg: float
    # What the farmer needs to do to earn credits (if not eligible)
    required_methane_reduction_kg: Optional[float]
    gap_methane_kg: Optional[float]
    # Human-readable steps
    steps: list


def explain_eligibility(
    baseline_methane_kg: float,
    current_methane_kg: float,
    methane_reduction_kg: float,
    co2e_reduction_tonnes: float,
    estimated_credits: int,
) -> EligibilityResult:
    """
    Build a full eligibility explanation for a carbon report.

    Parameters come directly from the CarbonReport model.
    """
    required_co2e = CREDIT_ISSUANCE_THRESHOLD
    eligible = estimated_credits >= 1
    current_credits = estimated_credits

    # Required methane reduction to earn 1 credit
    required_reduction = required_co2e * 1000 / GWP_METHANE  # kg/day

    gap_methane = max(0.0, required_reduction - methane_reduction_kg) if not eligible else None

    if eligible:
        reason = (
            f"CO2e reduction ({co2e_reduction_tonnes:.4f} tCO2e) meets the "
            f"{CREDIT_ISSUANCE_THRESHOLD} tCO2e issuance threshold. "
            f"{current_credits} tradable credit{'s' if current_credits != 1 else ''} issued."
        )
    elif methane_reduction_kg <= 0:
        reason = (
            "No measurable methane reduction detected. "
            "Current methane equals or exceeds baseline. "
            "Ensure emission-reduction practices are in place and sensors are calibrated."
        )
    elif co2e_reduction_tonnes < CREDIT_ISSUANCE_THRESHOLD:
        reason = (
            f"CO2e reduction ({co2e_reduction_tonnes:.4f} tCO2e) is below the "
            f"{CREDIT_ISSUANCE_THRESHOLD} tCO2e minimum required to issue tradable credits. "
            f"A verification certificate has been issued instead."
        )
    else:
        reason = "CO2e reduction rounds down to 0 credits (floor function applied)."

    steps = [
        {
            "step": 1,
            "label": "Baseline Methane",
            "value": round(baseline_methane_kg, 4),
            "unit": "kg CH4/day",
            "note": "Average of first 7 sensor readings",
        },
        {
            "step": 2,
            "label": "Current Methane",
            "value": round(current_methane_kg, 4),
            "unit": "kg CH4/day",
            "note": "Average of last 7 sensor readings",
        },
        {
            "step": 3,
            "label": "Methane Reduction",
            "value": round(methane_reduction_kg, 4),
            "unit": "kg CH4/day",
            "note": f"Baseline minus current. Need >= {required_reduction:.4f} kg/day for 1 credit.",
        },
        {
            "step": 4,
            "label": "CO2e Reduction",
            "value": round(co2e_reduction_tonnes, 6),
            "unit": "tCO2e",
            "note": f"Methane x {GWP_METHANE} / 1000. Need >= {CREDIT_ISSUANCE_THRESHOLD} tCO2e.",
        },
        {
            "step": 5,
            "label": "Credits Issued",
            "value": current_credits,
            "unit": "credits",
            "note": "floor(CO2e). Fractional tCO2e is not tradable.",
        },
    ]

    return EligibilityResult(
        eligible=eligible,
        reason=reason,
        current_co2e=round(co2e_reduction_tonnes, 6),
        required_co2e=required_co2e,
        current_credits=current_credits,
        baseline_methane_kg=round(baseline_methane_kg, 4),
        current_methane_kg=round(current_methane_kg, 4),
        methane_reduction_kg=round(methane_reduction_kg, 4),
        required_methane_reduction_kg=round(required_reduction, 4),
        gap_methane_kg=round(gap_methane, 4) if gap_methane is not None else None,
        steps=steps,
    )
