"""
MRV Demo Router — Phase 10A / 10B

POST /mrv/demo/high-emission

Generates engineered demo MRV data (sensor readings, satellite observations,
drone observations) for a specific high-emission livestock scenario.

PURPOSE
-------
Standard paddy simulation cannot produce tradeable carbon credits because:
  - The sensor simulator models a seasonal environmental pattern, not a
    pre/post-intervention effect.
  - Carbon calculator = avg(first 7 readings) - avg(last 7 readings) in kg/day.
  - Seasonal values are nearly identical early vs. late → ~0 reduction → 0 credits.

This endpoint creates sensor readings with specifically engineered
`estimated_methane` values so the carbon calculator produces the target co2e
and integer credits. The readings are clearly labeled HIGH_EMISSION_DEMO and
are intended for testing the full credit issuance pipeline.

SCENARIOS
---------
1. DAIRY_SRI_LOW           → ~6 credits (5–7 tCO₂e)
2. DAIRY_BIODIGESTER       → ~14 credits (12–16 tCO₂e)
3. MIXED_LIVESTOCK_BIOCHAR → ~16 credits (14–18 tCO₂e)
4. BUFFALO_BIODIGESTER     → ~11 credits (10–14 tCO₂e)
5. EDGE_CERTIFICATE_ONLY   → 0 credits (<1 tCO₂e)

METHODOLOGY
-----------
Carbon calculator formula:
  baseline = avg(estimated_methane, first 7 readings)
  current  = avg(estimated_methane, last 7 readings)
  methane_reduction_kg = max(0, baseline - current)
  co2e = methane_reduction_kg × 27.2 / 1000

To achieve N credits (N ≥ 1):
  co2e must be ≥ N and < N+1
  Required reduction = N × 1000/27.2 + ε (small margin)
  baseline = current + required_reduction

DATA LABELING
-------------
- sensor_readings: source_type = HIGH_EMISSION_DEMO
- satellite: source = SATELLITE_SIMULATED (labeled demo in image_reference)
- drone: source = DRONE_SIMULATED (labeled demo in image_reference)

IMPORTANT: Never use this data for production MRV submissions.
"""
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.farm import Farm, CropCycle
from app.models.fpo import FPOProfile
from app.models.sensor import SensorReading, SensorSourceType
from app.models.satellite_observation import SatelliteObservation, SatelliteSource, VegetationHealth, FloodRisk
from app.models.drone_observation import DroneObservation, DroneSource

router = APIRouter(prefix="/mrv", tags=["MRV Demo"])

# ── Constants ──────────────────────────────────────────────────────────────────

GWP_CH4 = 27.2          # IPCC AR6 CH₄ 100-year GWP (same as carbon_calculator.py)
MIN_READINGS = 7        # Minimum readings required by carbon_calculator.py

# Current methane (post-intervention, shared across livestock scenarios)
# Represents reduced daily emissions after manure management improvement
DEMO_CURRENT_METHANE_KG_DAY = 20.0


def _required_baseline(target_credits: int, current: float) -> float:
    """
    Reverse-engineer the baseline methane needed to hit exactly target_credits.
    Adds a small epsilon so floor(co2e) = target_credits reliably.
    """
    required_co2e = target_credits + 0.01          # just above the integer floor
    required_reduction = required_co2e * 1000.0 / GWP_CH4
    return round(current + required_reduction, 4)


# Scenario definitions: (description, target_credits, current_methane, notes)
SCENARIOS = {
    "DAIRY_SRI_LOW": {
        "description": "12 dairy cattle + SRI/improved feed practices",
        "target_credits": 6,
        "current_methane": DEMO_CURRENT_METHANE_KG_DAY,
        "baseline_methane": _required_baseline(6, DEMO_CURRENT_METHANE_KG_DAY),
        "expected_co2e_reduction_tonnes": round((_required_baseline(6, DEMO_CURRENT_METHANE_KG_DAY) - DEMO_CURRENT_METHANE_KG_DAY) * GWP_CH4 / 1000, 3),
        "livestock_note": "12 dairy cattle @ ~150 kg CH₄/yr, 12% reduction via improved feed",
    },
    "DAIRY_BIODIGESTER": {
        "description": "20 Holstein dairy cattle + anaerobic biodigester",
        "target_credits": 14,
        "current_methane": DEMO_CURRENT_METHANE_KG_DAY,
        "baseline_methane": _required_baseline(14, DEMO_CURRENT_METHANE_KG_DAY),
        "expected_co2e_reduction_tonnes": round((_required_baseline(14, DEMO_CURRENT_METHANE_KG_DAY) - DEMO_CURRENT_METHANE_KG_DAY) * GWP_CH4 / 1000, 3),
        "livestock_note": "20 Holstein cattle @ ~160 kg CH₄/yr, 16% reduction via biodigester",
    },
    "MIXED_LIVESTOCK_BIOCHAR": {
        "description": "15 Sahiwal cattle + 30 goats + pasture biochar",
        "target_credits": 16,
        "current_methane": DEMO_CURRENT_METHANE_KG_DAY,
        "baseline_methane": _required_baseline(16, DEMO_CURRENT_METHANE_KG_DAY),
        "expected_co2e_reduction_tonnes": round((_required_baseline(16, DEMO_CURRENT_METHANE_KG_DAY) - DEMO_CURRENT_METHANE_KG_DAY) * GWP_CH4 / 1000, 3),
        "livestock_note": "15 cattle + 30 goats, 27% reduction via pasture management + biochar",
    },
    "BUFFALO_BIODIGESTER": {
        "description": "25 Murrah buffaloes + anaerobic biodigester",
        "target_credits": 11,
        "current_methane": DEMO_CURRENT_METHANE_KG_DAY,
        "baseline_methane": _required_baseline(11, DEMO_CURRENT_METHANE_KG_DAY),
        "expected_co2e_reduction_tonnes": round((_required_baseline(11, DEMO_CURRENT_METHANE_KG_DAY) - DEMO_CURRENT_METHANE_KG_DAY) * GWP_CH4 / 1000, 3),
        "livestock_note": "25 Murrah buffaloes @ ~55 kg CH₄/yr, 30% reduction via biodigester",
    },
    "EDGE_CERTIFICATE_ONLY": {
        "description": "Minimal reduction (edge case: certificate issued, no tradeable credits)",
        "target_credits": 0,
        "current_methane": 20.0,
        "baseline_methane": 40.0,   # reduction = 20 → co2e = 20×27.2/1000 = 0.544 < 1
        "expected_co2e_reduction_tonnes": round(20.0 * GWP_CH4 / 1000, 3),
        "livestock_note": "2 goats, minimal methane reduction — below 1 tCO₂e threshold for credits",
    },
}


def _assert_farm_access(farm: Farm, current_user: User, db: Session):
    """FARMER (own farm), ADMIN. FPO blocked (they use the FPO mint flow)."""
    if current_user.role == UserRole.ADMIN:
        return
    if current_user.role == UserRole.FARMER:
        if farm.farmer_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied: not your farm")
        return
    raise HTTPException(
        status_code=403,
        detail="Only farmers (own farm) or admins can generate high-emission demo data",
    )


# ── Request / Response schemas ────────────────────────────────────────────────

class HighEmissionDemoRequest(BaseModel):
    farm_id: int
    crop_cycle_id: int
    scenario: str = Field(
        description=(
            "One of: DAIRY_SRI_LOW, DAIRY_BIODIGESTER, MIXED_LIVESTOCK_BIOCHAR, "
            "BUFFALO_BIODIGESTER, EDGE_CERTIFICATE_ONLY"
        )
    )
    days: int = Field(default=30, ge=14, le=90, description="Number of sensor readings to generate (14–90)")


class HighEmissionDemoResponse(BaseModel):
    success: bool = True
    scenario: str
    scenario_description: str
    livestock_note: str
    farm_id: int
    crop_cycle_id: int
    sensor_readings_generated: int
    satellite_observations_generated: int
    drone_observations_generated: int
    expected_co2e_reduction_tonnes: float
    expected_credits: int
    baseline_methane_kg_day: float
    current_methane_kg_day: float
    demo_label: str = "DEMO_HIGH_EMISSION"
    message: str = "High-emission demo data generated successfully"
    warning: str = (
        "This is synthetic test data with engineered methane values. "
        "Do not use for real carbon credit claims."
    )


# ── POST /mrv/demo/high-emission ──────────────────────────────────────────────

@router.post(
    "/demo/high-emission",
    response_model=HighEmissionDemoResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_high_emission_demo(
    body: HighEmissionDemoRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate high-emission livestock/manure-management demo MRV data.

    Creates sensor readings, satellite observations, and drone observations
    with engineered values that will produce 5–16+ tCO₂e when carbon report
    is generated — enabling end-to-end testing of the full credit pipeline.

    Returns expected co2e, expected credits, and counts of created records.
    Call POST /carbon-reports/generate/{crop_cycle_id} after this to create a report.

    DEMO DATA ONLY — labeled HIGH_EMISSION_DEMO, not suitable for production.
    """
    # ── Validate scenario ─────────────────────────────────────────────────────
    scenario_key = body.scenario.upper().replace("-", "_")
    if scenario_key not in SCENARIOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unknown scenario '{body.scenario}'. "
                f"Valid: {', '.join(SCENARIOS.keys())}"
            ),
        )
    sc = SCENARIOS[scenario_key]

    # ── Load and validate farm + cycle ────────────────────────────────────────
    farm = db.query(Farm).filter(Farm.id == body.farm_id, Farm.is_deleted == False).first()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    _assert_farm_access(farm, current_user, db)

    cycle = db.query(CropCycle).filter(
        CropCycle.id == body.crop_cycle_id,
        CropCycle.farm_id == body.farm_id,
    ).first()
    if not cycle:
        raise HTTPException(
            status_code=404,
            detail=f"Crop cycle {body.crop_cycle_id} not found on farm {body.farm_id}",
        )

    # ── Date range: always anchor to today so all records are in the past ─────
    today_utc = datetime.now(timezone.utc)
    today_date = today_utc.date()

    # We generate `body.days` daily sensor readings ending at today.
    # Always anchor end to today and count backward — cycle.start_date is not a
    # date-floor constraint for demo data.  This matches the logic in
    # /drone/simulate and /satellite/simulate after the Phase 10A fix.
    sensor_start_date = today_date - timedelta(days=body.days - 1)
    actual_days = body.days

    # ── Build sensor readings with engineered methane values ──────────────────
    baseline = sc["baseline_methane"]
    current = sc["current_methane"]

    readings_to_insert = []
    for day_offset in range(actual_days):
        reading_date = sensor_start_date + timedelta(days=day_offset)
        reading_dt = datetime(
            reading_date.year, reading_date.month, reading_date.day,
            7, 0, 0, tzinfo=timezone.utc,
        )

        # Engineer methane: high at start (baseline), low at end (current).
        # Linear transition over the full period.
        # - First 7 readings average ≈ baseline (needed for carbon calculator)
        # - Last 7 readings average ≈ current (needed for carbon calculator)
        if actual_days >= 14:
            t = day_offset / (actual_days - 1)           # 0.0 → 1.0
        else:
            t = day_offset / max(actual_days - 1, 1)

        # Use step function: first 1/3 = baseline, last 1/3 = current, middle = linear
        if t <= 0.30:
            methane = baseline
        elif t >= 0.70:
            methane = current
        else:
            # Linear interpolation in the middle third
            frac = (t - 0.30) / 0.40
            methane = baseline + (current - baseline) * frac

        # Soil / water / temp values — realistic for a livestock pasture/barn
        # These don't affect the carbon calculation (estimated_methane is set directly)
        soil_moisture = 35.0 + (day_offset % 7) * 2.0   # 35–47% (drier than paddy)
        water_depth_cm = 0.5                              # minimal (not flooded)
        temperature_c = 28.0 + 3.0 * math.sin(math.pi * day_offset / 30.0)
        humidity = 55.0 + soil_moisture * 0.2
        rainfall_mm = 2.0 if day_offset % 10 == 0 else 0.0
        quality_score = 94.0

        reading = SensorReading(
            farm_id=body.farm_id,
            crop_cycle_id=body.crop_cycle_id,
            reading_time=reading_dt,
            soil_moisture=round(soil_moisture, 2),
            water_depth_cm=water_depth_cm,
            temperature_c=round(temperature_c, 2),
            humidity=round(humidity, 2),
            rainfall_mm=rainfall_mm,
            estimated_methane=round(methane, 4),
            data_quality_score=quality_score,
            source_type=SensorSourceType.HIGH_EMISSION_DEMO,
        )
        db.add(reading)
        db.flush()
        readings_to_insert.append(reading)

    db.commit()
    sensor_count = len(readings_to_insert)

    # ── Satellite observations (backward from today, 5-day spacing) ───────────
    # Always anchor last observation to today and go backward — same logic as
    # /satellite/simulate. cycle.start_date is not a constraint here.
    N_SAT = 6
    SAT_INTERVAL = 5
    sat_base = today_date - timedelta(days=(N_SAT - 1) * SAT_INTERVAL)

    sat_created = 0
    for i in range(N_SAT):
        obs_date = sat_base + timedelta(days=i * SAT_INTERVAL)
        if obs_date > today_date:
            break
        obs = SatelliteObservation(
            farm_id=body.farm_id,
            crop_cycle_id=body.crop_cycle_id,
            observation_date=obs_date,
            ndvi=round(0.45 + 0.1 * math.sin(math.pi * i / N_SAT), 4),
            ndwi=round(0.05 + 0.05 * i / N_SAT, 4),
            vegetation_health=VegetationHealth.GOOD,
            flood_risk=FloodRisk.NONE,
            cloud_cover_percent=10.0 + i * 2.0,
            source=SatelliteSource.SATELLITE_SIMULATED,
        )
        db.add(obs)
        db.flush()  # Force flush to avoid bulk insert type mismatch for PG Enums
        sat_created += 1

    db.commit()

    # ── Drone observations (backward from today, 7-day spacing) ──────────────
    # Always anchor last observation to today — same logic as /drone/simulate.
    N_DRONE = 4
    DRONE_INTERVAL = 7
    drone_base = today_date - timedelta(days=(N_DRONE - 1) * DRONE_INTERVAL)

    drone_created = 0
    for i in range(N_DRONE):
        obs_date = drone_base + timedelta(days=i * DRONE_INTERVAL)
        if obs_date > today_date:
            break
        obs = DroneObservation(
            farm_id=body.farm_id,
            crop_cycle_id=body.crop_cycle_id,
            observation_date=obs_date,
            vegetation_cover_percent=round(55.0 + 10.0 * i / N_DRONE, 2),
            standing_water_percent=2.0,          # livestock area: minimal water
            anomaly_score=round(5.0 + 2.0 * i, 2),
            image_reference=f"DEMO_HIGH_EMISSION_{scenario_key}_drone{i+1}.jpg",
            source=DroneSource.DRONE_SIMULATED,
        )
        db.add(obs)
        db.flush()  # Force flush to avoid bulk insert type mismatch for PG Enums
        drone_created += 1

    db.commit()

    # ── Expected carbon metrics ───────────────────────────────────────────────
    # Recalculate based on actual first/last 7 readings we created
    methane_values = [r.estimated_methane for r in readings_to_insert]
    # Actually: first 7 by time = readings_to_insert[:7], last 7 = readings_to_insert[-7:]
    first7 = methane_values[:7]
    last7 = methane_values[-7:]
    actual_baseline_avg = sum(first7) / len(first7) if first7 else 0.0
    actual_current_avg = sum(last7) / len(last7) if last7 else 0.0
    actual_reduction = max(0.0, actual_baseline_avg - actual_current_avg)
    actual_co2e = round(actual_reduction * GWP_CH4 / 1000.0, 3)
    actual_credits = math.floor(actual_co2e)

    return HighEmissionDemoResponse(
        scenario=scenario_key,
        scenario_description=sc["description"],
        livestock_note=sc["livestock_note"],
        farm_id=body.farm_id,
        crop_cycle_id=body.crop_cycle_id,
        sensor_readings_generated=sensor_count,
        satellite_observations_generated=sat_created,
        drone_observations_generated=drone_created,
        expected_co2e_reduction_tonnes=actual_co2e,
        expected_credits=actual_credits,
        baseline_methane_kg_day=round(actual_baseline_avg, 2),
        current_methane_kg_day=round(actual_current_avg, 2),
    )


# ── GET /mrv/demo/scenarios ───────────────────────────────────────────────────

@router.get(
    "/demo/scenarios",
    tags=["MRV Demo"],
)
def list_demo_scenarios():
    """List available high-emission demo scenarios with expected credit outputs."""
    return [
        {
            "key": key,
            "description": sc["description"],
            "livestock_note": sc["livestock_note"],
            "expected_credits": sc["target_credits"],
            "expected_co2e_reduction_tonnes": sc["expected_co2e_reduction_tonnes"],
        }
        for key, sc in SCENARIOS.items()
    ]
