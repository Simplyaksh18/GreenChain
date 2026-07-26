"""
Fraud Detection Engine — Phase 7.

Analyses a carbon report along with satellite / drone data and sensor
readings to produce a fraud_score (0–100) and fraud_level.

Detection Types
---------------
1. SENSOR_SATELLITE_MISMATCH   — sensor-reported soil moisture consistently
                                  high but satellite NDWI is very low.
2. SUDDEN_CREDIT_SPIKE         — estimated_credits unusually high relative
                                  to land area (> 5 credits/acre).
3. DATA_COMPLETENESS_FRAUD     — fewer than 7 readings AND no satellite obs
                                  AND no drone obs (all three gaps together).
4. ANOMALY_SCORE_SPIKE         — average drone anomaly_score > 70.
5. VEGETATION_MISMATCH         — satellite says POOR health but sensor
                                  shows very high soil moisture (supposed
                                  good-condition paddy).
6. TEMPORAL_GAP                — the gap between the earliest and latest
                                  sensor reading is < 7 days (report covers
                                  too short a window to be credible).

Fraud Level Mapping
-------------------
 0 – 25  → LOW
26 – 55  → MEDIUM
56 – 80  → HIGH
81 – 100 → CRITICAL

Score is clamped to [0, 100].
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Sequence

from app.models.satellite_observation import SatelliteObservation, VegetationHealth
from app.models.drone_observation import DroneObservation
from app.models.sensor import SensorReading
from app.models.carbon_report import CarbonReport
from app.models.farm import Farm


class FraudLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class FraudResult:
    fraud_score: float
    fraud_level: FraudLevel
    detections: list[str] = field(default_factory=list)


# ── Thresholds ─────────────────────────────────────────────────────────────────
CREDITS_PER_ACRE_THRESHOLD = 5.0
HIGH_ANOMALY_THRESHOLD = 70.0
MIN_OBSERVATION_DAYS = 7
AVG_SOIL_MOISTURE_HIGH = 65.0   # sensor high moisture threshold
NDWI_LOW_THRESHOLD = -0.1       # NDWI below this = very dry


def detect_fraud(
    carbon_report: CarbonReport,
    farm: Farm,
    sensor_readings: Sequence[SensorReading],
    satellite_obs: Sequence[SatelliteObservation],
    drone_obs: Sequence[DroneObservation],
) -> FraudResult:
    """Run all 6 fraud detectors and return a combined result."""
    score = 0.0
    detections: list[str] = []

    # ── 1. Sensor–satellite moisture mismatch ──────────────────────────────────
    if sensor_readings and satellite_obs:
        avg_moisture = sum(r.soil_moisture for r in sensor_readings) / len(sensor_readings)
        avg_ndwi = sum(o.ndwi for o in satellite_obs) / len(satellite_obs)
        if avg_moisture > AVG_SOIL_MOISTURE_HIGH and avg_ndwi < NDWI_LOW_THRESHOLD:
            score += 25
            detections.append(
                f"SENSOR_SATELLITE_MISMATCH: high sensor moisture "
                f"(avg={avg_moisture:.1f}) but low satellite NDWI "
                f"(avg={avg_ndwi:.3f}) (+25)"
            )

    # ── 2. Sudden credit spike relative to land area ───────────────────────────
    if farm.land_area_acres and farm.land_area_acres > 0:
        credits_per_acre = carbon_report.estimated_credits / farm.land_area_acres
        if credits_per_acre > CREDITS_PER_ACRE_THRESHOLD:
            score += 20
            detections.append(
                f"SUDDEN_CREDIT_SPIKE: {credits_per_acre:.2f} credits/acre "
                f"> {CREDITS_PER_ACRE_THRESHOLD} threshold (+20)"
            )

    # ── 3. All-source data completeness fraud ──────────────────────────────────
    if len(sensor_readings) < 7 and len(satellite_obs) == 0 and len(drone_obs) == 0:
        score += 30
        detections.append(
            "DATA_COMPLETENESS_FRAUD: insufficient sensor readings AND "
            "no satellite obs AND no drone obs (+30)"
        )

    # ── 4. Drone anomaly score spike ───────────────────────────────────────────
    if drone_obs:
        avg_anomaly = sum(o.anomaly_score for o in drone_obs) / len(drone_obs)
        if avg_anomaly > HIGH_ANOMALY_THRESHOLD:
            score += 20
            detections.append(
                f"ANOMALY_SCORE_SPIKE: avg drone anomaly={avg_anomaly:.1f} "
                f"> {HIGH_ANOMALY_THRESHOLD} (+20)"
            )

    # ── 5. Vegetation mismatch ─────────────────────────────────────────────────
    if sensor_readings and satellite_obs:
        poor_count = sum(
            1 for o in satellite_obs if o.vegetation_health == VegetationHealth.POOR
        )
        avg_moisture = sum(r.soil_moisture for r in sensor_readings) / len(sensor_readings)
        if poor_count > len(satellite_obs) / 2 and avg_moisture > AVG_SOIL_MOISTURE_HIGH:
            score += 15
            detections.append(
                f"VEGETATION_MISMATCH: majority satellite obs show POOR vegetation "
                f"but sensor moisture is high (avg={avg_moisture:.1f}) (+15)"
            )

    # ── 6. Temporal gap too short ──────────────────────────────────────────────
    if len(sensor_readings) >= 2:
        dates = sorted(r.reading_time for r in sensor_readings)
        span_days = (dates[-1] - dates[0]).days
        if span_days < MIN_OBSERVATION_DAYS:
            score += 20
            detections.append(
                f"TEMPORAL_GAP: observation window is only {span_days} day(s), "
                f"< {MIN_OBSERVATION_DAYS} required (+20)"
            )

    clamped = round(min(score, 100.0), 1)
    return FraudResult(
        fraud_score=clamped,
        fraud_level=_map_fraud_level(clamped),
        detections=detections,
    )


def _map_fraud_level(score: float) -> FraudLevel:
    if score <= 25:
        return FraudLevel.LOW
    if score <= 55:
        return FraudLevel.MEDIUM
    if score <= 80:
        return FraudLevel.HIGH
    return FraudLevel.CRITICAL
