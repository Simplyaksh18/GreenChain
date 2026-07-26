"""
Emission Estimator — Formula-Based AI Module
=============================================
Structured as a replaceable AI service: today it uses a deterministic formula,
but the interface is designed so that an ML model (e.g. scikit-learn, PyTorch)
can be swapped in later without changing callers.

Formula
-------
estimated_methane = BASE_FACTOR
                  × crop_factor
                  × moisture_factor
                  × water_factor
                  × temperature_factor

Units: kg CH₄ per day per hectare (normalised)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict


# ── Crop emission factors ──────────────────────────────────────────────────────
CROP_FACTORS: Dict[str, float] = {
    "paddy":  1.5,
    "rice":   1.5,   # alias
    "wheat":  0.7,
    "millet": 0.5,
    "maize":  0.8,
    "corn":   0.8,   # alias
}
DEFAULT_CROP_FACTOR = 1.0   # unknown crop

BASE_FACTOR = 2.0           # kg CH₄/day baseline at reference conditions


@dataclass
class EstimationResult:
    estimated_methane: float
    confidence_score: float
    explanation: str


def estimate_methane(
    soil_moisture: float,
    water_depth_cm: float,
    temperature_c: float,
    crop_type: str,
) -> EstimationResult:
    """
    Estimate daily methane emission for a single sensor reading.

    Parameters
    ----------
    soil_moisture   : 0–100  (%)
    water_depth_cm  : 0–30   (cm)
    temperature_c   : 15–45  (°C)
    crop_type       : string (case-insensitive)

    Returns
    -------
    EstimationResult with methane kg/day, confidence, and factor breakdown.
    """
    # ── Factor calculations ────────────────────────────────────────────────
    crop_key = crop_type.strip().lower()
    crop_factor = CROP_FACTORS.get(crop_key, DEFAULT_CROP_FACTOR)

    # Moisture factor: linear 0→0 at 0% moisture, 1.0 at 100%
    moisture_factor = max(soil_moisture, 0.0) / 100.0

    # Water factor: stagnant flooding multiplies methane
    water_factor = 1.0 + (max(water_depth_cm, 0.0) / 20.0)

    # Temperature factor: higher temp accelerates microbial activity
    temperature_factor = 1.0 + ((temperature_c - 20.0) / 50.0)
    temperature_factor = max(temperature_factor, 0.01)   # prevent negative

    # ── Final estimate ─────────────────────────────────────────────────────
    estimated_methane = (
        BASE_FACTOR
        * crop_factor
        * moisture_factor
        * water_factor
        * temperature_factor
    )
    estimated_methane = round(max(estimated_methane, 0.0), 6)

    # ── Confidence score (simple heuristic) ───────────────────────────────
    # Confidence drops for unknown crops or extreme values
    confidence = 85.0
    if crop_key not in CROP_FACTORS:
        confidence -= 20.0                            # unknown crop
    if not (0 <= soil_moisture <= 100):
        confidence -= 10.0
    if not (0 <= water_depth_cm <= 30):
        confidence -= 10.0
    if not (15 <= temperature_c <= 45):
        confidence -= 10.0
    confidence_score = round(max(confidence, 10.0), 1)

    # ── Human-readable explanation ─────────────────────────────────────────
    explanation = (
        f"Methane = {BASE_FACTOR} (base)"
        f" × {crop_factor} (crop:{crop_type})"
        f" × {moisture_factor:.3f} (moisture:{soil_moisture}%)"
        f" × {water_factor:.3f} (water_depth:{water_depth_cm}cm)"
        f" × {temperature_factor:.3f} (temp:{temperature_c}°C)"
        f" = {estimated_methane} kg CH₄/day"
    )

    return EstimationResult(
        estimated_methane=estimated_methane,
        confidence_score=confidence_score,
        explanation=explanation,
    )
