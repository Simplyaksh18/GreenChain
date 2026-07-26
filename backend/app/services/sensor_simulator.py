"""
Sensor Simulator
================
Generates realistic daily sensor readings for paddy / agriculture fields.

Design principles
-----------------
* NO pure random noise — all values follow deterministic environmental logic.
* Rainfall drives soil moisture and water depth with realistic lag/decay.
* Temperature follows a sinusoidal daily/seasonal curve.
* Humidity correlates with rainfall and temperature.
* Methane is computed via the emission_estimator module (same formula used
  in the real estimation pipeline so simulator and estimator are always consistent).
* A seed derived from (farm_id, crop_cycle_id, day_index) makes the output
  repeatable for the same inputs, while different farms/cycles diverge.

Supported crop_type values (case-insensitive):
  Paddy, Rice, Wheat, Millet, Maize, Corn, <unknown>
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List

from app.services.emission_estimator import estimate_methane
from app.models.sensor import SensorSourceType


@dataclass
class SimulatedReading:
    farm_id: int
    crop_cycle_id: int
    reading_time: datetime
    soil_moisture: float
    water_depth_cm: float
    temperature_c: float
    humidity: float
    rainfall_mm: float
    estimated_methane: float
    data_quality_score: float
    source_type: SensorSourceType = SensorSourceType.SIMULATED


# ── Internal helpers ──────────────────────────────────────────────────────────

def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _pseudo_random(seed: int, amplitude: float = 1.0) -> float:
    """
    Deterministic value in [-amplitude, +amplitude] derived from an integer seed.
    Uses a simple multiplicative hash — no stdlib random, fully reproducible.
    """
    h = (seed * 2654435761) & 0xFFFFFFFF          # Knuth multiplicative hash
    h = ((h >> 16) ^ h) & 0xFFFFFFFF
    return amplitude * (h / 0xFFFFFFFF * 2.0 - 1.0)


# ── Main simulator ────────────────────────────────────────────────────────────

def simulate_sensor_readings(
    farm_id: int,
    crop_cycle_id: int,
    crop_type: str,
    number_of_days: int,
    start_time: datetime | None = None,
) -> List[SimulatedReading]:
    """
    Generate `number_of_days` daily sensor readings starting from `start_time`
    (default: UTC midnight today).

    Environmental model
    -------------------
    Day index drives:
      * A sinusoidal rainfall pattern with base period 10 days (monsoon-like
        bursts every ~10 days) plus smaller noise.
      * Soil moisture accumulates from rainfall and decays at 3%/day.
      * Water depth responds to heavy rain (>10 mm) and evaporates at 0.8 cm/day.
      * Temperature follows a 30-day seasonal sine (warm centre) plus small
        diurnal jitter.
      * Humidity = 40 + 0.5 * soil_moisture + rainfall contribution.
    """
    if start_time is None:
        start_time = datetime.now(timezone.utc).replace(
            hour=6, minute=0, second=0, microsecond=0
        )

    readings: List[SimulatedReading] = []

    # State variables with realistic initial values
    soil_moisture = 45.0        # %
    water_depth_cm = 2.0        # cm
    base_seed = farm_id * 1000 + crop_cycle_id * 37

    for day in range(number_of_days):
        day_seed = base_seed + day

        # ── Rainfall (mm) ─────────────────────────────────────────────────
        # Primary: 10-day monsoon burst cycle
        monsoon_wave = math.sin(2 * math.pi * day / 10.0)
        # Secondary: 30-day seasonal envelope (heavier rain mid-season)
        seasonal_env = 0.5 + 0.5 * math.sin(math.pi * day / max(number_of_days, 30))
        rain_base = 8.0 * seasonal_env * max(0, monsoon_wave)
        rain_noise = _pseudo_random(day_seed + 1, 3.0)
        rainfall_mm = _clamp(rain_base + rain_noise, 0.0, 100.0)

        # ── Soil moisture ──────────────────────────────────────────────────
        # Increases proportionally to rainfall, decays 3%/day
        soil_moisture += rainfall_mm * 0.4       # absorption coefficient
        soil_moisture *= 0.97                    # daily evapotranspiration
        soil_noise = _pseudo_random(day_seed + 2, 1.5)
        soil_moisture = _clamp(soil_moisture + soil_noise, 20.0, 95.0)

        # ── Water depth ────────────────────────────────────────────────────
        # Increases on heavy rain days, drains at 0.8 cm/day
        if rainfall_mm > 10:
            water_depth_cm += (rainfall_mm - 10) * 0.12
        water_depth_cm -= 0.8                    # daily drainage/evaporation
        water_noise = _pseudo_random(day_seed + 3, 0.5)
        water_depth_cm = _clamp(water_depth_cm + water_noise, 0.0, 30.0)

        # ── Temperature (°C) ──────────────────────────────────────────────
        # 30-day seasonal curve: warm mid-season, cooler at edges
        # Range roughly 22–38 °C (tropical paddy belt)
        temp_seasonal = 30.0 + 6.0 * math.sin(math.pi * day / max(number_of_days, 30))
        temp_noise = _pseudo_random(day_seed + 4, 1.0)
        temperature_c = _clamp(temp_seasonal + temp_noise, 15.0, 45.0)

        # ── Humidity ──────────────────────────────────────────────────────
        hum_base = 40.0 + 0.5 * soil_moisture + 0.3 * rainfall_mm
        hum_noise = _pseudo_random(day_seed + 5, 3.0)
        humidity = _clamp(hum_base + hum_noise, 20.0, 100.0)

        # ── Methane via estimator ─────────────────────────────────────────
        result = estimate_methane(
            soil_moisture=round(soil_moisture, 2),
            water_depth_cm=round(water_depth_cm, 2),
            temperature_c=round(temperature_c, 2),
            crop_type=crop_type,
        )

        # ── Data quality score ────────────────────────────────────────────
        # Penalise extreme values; simulated data is generally high quality
        quality = 92.0
        if soil_moisture > 90 or soil_moisture < 25:
            quality -= 5.0
        if water_depth_cm > 25:
            quality -= 5.0
        if temperature_c > 42 or temperature_c < 18:
            quality -= 8.0
        quality += _pseudo_random(day_seed + 6, 2.0)    # ±2 jitter
        data_quality_score = _clamp(quality, 0.0, 100.0)

        reading_time = start_time + timedelta(days=day)

        readings.append(SimulatedReading(
            farm_id=farm_id,
            crop_cycle_id=crop_cycle_id,
            reading_time=reading_time,
            soil_moisture=round(soil_moisture, 2),
            water_depth_cm=round(water_depth_cm, 2),
            temperature_c=round(temperature_c, 2),
            humidity=round(humidity, 2),
            rainfall_mm=round(rainfall_mm, 2),
            estimated_methane=result.estimated_methane,
            data_quality_score=round(data_quality_score, 2),
            source_type=SensorSourceType.SIMULATED,
        ))

    return readings
