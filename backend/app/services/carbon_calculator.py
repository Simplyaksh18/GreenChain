"""
Carbon Calculator Service
=========================
Computes carbon report figures from stored SensorReading objects.

Formula chain
-------------
1.  baseline_methane_kg  = avg(estimated_methane) of first 7 readings (asc by reading_time)
2.  current_methane_kg   = avg(estimated_methane) of latest 7 readings (desc by reading_time)
3.  methane_reduction_kg = max(0, baseline − current)          # floor at 0
4.  co2e_reduction_tonnes = methane_reduction_kg × 27.2 / 1000
5.  estimated_credits    = floor(co2e_reduction_tonnes)        # integer credits
6.  report_hash          = SHA256 of deterministic dict of above + farm/cycle ids

Units
-----
* methane values   : kg CH₄ / day
* co2e             : tonnes CO₂-equivalent
* credits          : integer (1 credit = 1 tonne CO₂e)
* GWP factor used  : 27.2  (IPCC AR6 CH₄ 100-year GWP)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, List, Sequence

from app.utils.hash_utils import sha256_hash


# ── Minimum readings required to generate a report ────────────────────────────
MIN_READINGS = 7
GWP_CH4 = 27.2          # kg CO₂e per kg CH₄ (IPCC AR6)


@dataclass
class CarbonCalculation:
    baseline_methane_kg: float
    current_methane_kg: float
    methane_reduction_kg: float
    co2e_reduction_tonnes: float
    estimated_credits: int
    report_hash: str


class InsufficientReadingsError(ValueError):
    """Raised when fewer than MIN_READINGS exist for a crop cycle."""


def _avg_methane(readings: Sequence[Any]) -> float:
    """Mean estimated_methane across a slice of readings."""
    return sum(r.estimated_methane for r in readings) / len(readings)


def calculate_baseline_methane(readings: Sequence[Any]) -> float:
    """Average methane of the first 7 readings (sorted ascending by reading_time)."""
    if not readings:
        raise InsufficientReadingsError("No readings available")
    ordered = sorted(readings, key=lambda r: r.reading_time)
    return round(_avg_methane(ordered[:MIN_READINGS]), 6)


def calculate_current_methane(readings: Sequence[Any]) -> float:
    """Average methane of the latest 7 readings (sorted descending by reading_time)."""
    if not readings:
        raise InsufficientReadingsError("No readings available")
    ordered = sorted(readings, key=lambda r: r.reading_time, reverse=True)
    return round(_avg_methane(ordered[:MIN_READINGS]), 6)


def calculate_carbon_report(
    readings: Sequence[Any],
    farm_id: int,
    crop_cycle_id: int,
) -> CarbonCalculation:
    """
    Full carbon calculation from a list of SensorReading-like objects.

    Raises InsufficientReadingsError if fewer than MIN_READINGS readings.
    """
    if len(readings) < MIN_READINGS:
        raise InsufficientReadingsError(
            f"At least {MIN_READINGS} sensor readings are required to generate a report. "
            f"Found {len(readings)}."
        )

    baseline = calculate_baseline_methane(readings)
    current = calculate_current_methane(readings)

    methane_reduction = round(max(0.0, baseline - current), 6)
    co2e_reduction_tonnes = round(methane_reduction * GWP_CH4 / 1000.0, 6)
    estimated_credits = math.floor(co2e_reduction_tonnes)

    report_data = {
        "farm_id": farm_id,
        "crop_cycle_id": crop_cycle_id,
        "baseline_methane_kg": baseline,
        "current_methane_kg": current,
        "methane_reduction_kg": methane_reduction,
        "co2e_reduction_tonnes": co2e_reduction_tonnes,
        "estimated_credits": estimated_credits,
    }
    report_hash = generate_report_hash(report_data)

    return CarbonCalculation(
        baseline_methane_kg=baseline,
        current_methane_kg=current,
        methane_reduction_kg=methane_reduction,
        co2e_reduction_tonnes=co2e_reduction_tonnes,
        estimated_credits=estimated_credits,
        report_hash=report_hash,
    )


def generate_report_hash(report_data: dict) -> str:
    """Deterministic SHA-256 hash of report core fields."""
    return sha256_hash(report_data)
