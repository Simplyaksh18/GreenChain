"""
MRV Intelligence Engine — Phase 7.

Compares sensor readings against satellite and drone observations to
detect inconsistencies and compute an overall MRV confidence score.

Confidence Score: 0–100 (higher = more trustworthy data)
Consistency Score: 0–100 (higher = sensor/satellite/drone agree better)

Rules
-----
Sensor baseline:
  - If < 7 readings            → -20 confidence
  - avg quality < 70           → -15 confidence

Satellite cross-check:
  - No satellite obs           → -10 confidence, flag MISSING_SATELLITE_DATA
  - vegetation_health POOR     → -10 confidence, flag POOR_VEGETATION_DETECTED
  - flood_risk HIGH            → -15 confidence, flag HIGH_FLOOD_RISK
  - cloud_cover > 50 %         → -5  confidence, flag HIGH_CLOUD_COVER
  - avg NDVI < 0.2 (no crop)   → inconsistency flag LOW_NDVI_FOR_ACTIVE_CROP

Drone cross-check:
  - No drone obs               → -5  confidence, flag MISSING_DRONE_DATA
  - anomaly_score > 60         → -15 confidence, flag DRONE_ANOMALY_DETECTED
  - standing_water > 80 %      → -10 confidence, flag EXCESSIVE_STANDING_WATER
  - vegetation_cover < 20 %    → inconsistency flag LOW_DRONE_VEGETATION_COVER

Consistency computation:
  - Start at 100
  - Each inconsistency flag    → -20 each (clamped to 0)

Final confidence = max(0, min(100, computed_confidence))
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from app.models.satellite_observation import SatelliteObservation, FloodRisk, VegetationHealth
from app.models.drone_observation import DroneObservation
from app.models.sensor import SensorReading


@dataclass
class MRVResult:
    confidence_score: float          # 0–100
    consistency_score: float         # 0–100
    flags: list[str] = field(default_factory=list)
    inconsistencies: list[str] = field(default_factory=list)
    satellite_count: int = 0
    drone_count: int = 0
    sensor_count: int = 0
    avg_ndvi: float | None = None
    avg_drone_vegetation: float | None = None


def calculate_mrv(
    sensor_readings: Sequence[SensorReading],
    satellite_obs: Sequence[SatelliteObservation],
    drone_obs: Sequence[DroneObservation],
) -> MRVResult:
    """
    Compute MRV confidence and consistency from the three data sources.
    """
    confidence = 100.0
    flags: list[str] = []
    inconsistencies: list[str] = []

    num_sensors = len(sensor_readings)
    num_satellite = len(satellite_obs)
    num_drone = len(drone_obs)

    # ── Sensor quality ─────────────────────────────────────────────────────────
    if num_sensors < 7:
        confidence -= 20
        flags.append(f"INSUFFICIENT_SENSOR_READINGS ({num_sensors} < 7)")

    if num_sensors > 0:
        avg_quality = sum(r.data_quality_score for r in sensor_readings) / num_sensors
        if avg_quality < 70.0:
            confidence -= 15
            flags.append(f"LOW_SENSOR_QUALITY (avg={avg_quality:.1f})")

    # ── Satellite cross-check ──────────────────────────────────────────────────
    avg_ndvi: float | None = None
    if num_satellite == 0:
        confidence -= 10
        flags.append("MISSING_SATELLITE_DATA")
    else:
        avg_ndvi = sum(o.ndvi for o in satellite_obs) / num_satellite
        poor_veg = sum(1 for o in satellite_obs if o.vegetation_health == VegetationHealth.POOR)
        if poor_veg > 0:
            confidence -= 10
            flags.append(f"POOR_VEGETATION_DETECTED ({poor_veg} observations)")

        high_flood = sum(1 for o in satellite_obs if o.flood_risk == FloodRisk.HIGH)
        if high_flood > 0:
            confidence -= 15
            flags.append(f"HIGH_FLOOD_RISK ({high_flood} observations)")

        avg_cloud = sum(o.cloud_cover_percent for o in satellite_obs) / num_satellite
        if avg_cloud > 50.0:
            confidence -= 5
            flags.append(f"HIGH_CLOUD_COVER (avg={avg_cloud:.1f}%)")

        # Inconsistency: NDVI too low for an active paddy crop
        if avg_ndvi < 0.2:
            inconsistencies.append(f"LOW_NDVI_FOR_ACTIVE_CROP (avg_ndvi={avg_ndvi:.3f})")

    # ── Drone cross-check ──────────────────────────────────────────────────────
    avg_drone_veg: float | None = None
    if num_drone == 0:
        confidence -= 5
        flags.append("MISSING_DRONE_DATA")
    else:
        avg_anomaly = sum(o.anomaly_score for o in drone_obs) / num_drone
        if avg_anomaly > 60.0:
            confidence -= 15
            flags.append(f"DRONE_ANOMALY_DETECTED (avg_score={avg_anomaly:.1f})")

        avg_water = sum(o.standing_water_percent for o in drone_obs) / num_drone
        if avg_water > 80.0:
            confidence -= 10
            flags.append(f"EXCESSIVE_STANDING_WATER (avg={avg_water:.1f}%)")

        avg_drone_veg = sum(o.vegetation_cover_percent for o in drone_obs) / num_drone
        if avg_drone_veg < 20.0:
            inconsistencies.append(f"LOW_DRONE_VEGETATION_COVER (avg={avg_drone_veg:.1f}%)")

    # ── Consistency score ──────────────────────────────────────────────────────
    consistency = max(0.0, 100.0 - len(inconsistencies) * 20.0)

    return MRVResult(
        confidence_score=round(max(0.0, min(100.0, confidence)), 1),
        consistency_score=round(consistency, 1),
        flags=flags,
        inconsistencies=inconsistencies,
        satellite_count=num_satellite,
        drone_count=num_drone,
        sensor_count=num_sensors,
        avg_ndvi=round(avg_ndvi, 4) if avg_ndvi is not None else None,
        avg_drone_vegetation=round(avg_drone_veg, 2) if avg_drone_veg is not None else None,
    )
