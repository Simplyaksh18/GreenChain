"""
soc_service.py — Orchestrator: fetches data, calls soc_engine, persists results.

Reuses existing GreenChain data sources:
  - SatelliteObservation (NDVI, NDWI) from existing satellite_observations table
  - CropCycle metadata (crop_type, reduction_practice, start_date, end_date)
  - Farm metadata (land_area_acres, soil_type)
  - SOCMeasurement records (LAB / MANUAL / COPERNICUS / BHUVAN inputs)

No new provider integrations are introduced.  All satellite data comes from
the existing Copernicus / Bhuvan / simulated observation pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.farm import CropCycle, CropCycleStatus, Farm
from app.models.satellite_observation import SatelliteObservation
from app.models.soc import SOCMeasurement, SOCReport
from app.models.carbon_report import CarbonReport
from app.services.soc.soc_engine import estimate_soc
from app.services.soc.soc_models import CombinedCarbonReport, SOCEstimate  # noqa: F401 (used in type annotation)


# ── Data-status constants (used by the overview endpoint) ─────────────────────

DATA_STATUS_REPORT_AVAILABLE         = "REPORT_AVAILABLE"
DATA_STATUS_LIVE_ESTIMATE            = "LIVE_ESTIMATE"
DATA_STATUS_INSUFFICIENT_SATELLITE   = "INSUFFICIENT_SATELLITE_DATA"
DATA_STATUS_NO_CROP_CYCLE            = "NO_CROP_CYCLE"


# ── Overview result dataclass ─────────────────────────────────────────────────

@dataclass
class SOCOverviewResult:
    """
    Rich result returned by build_soc_overview().
    Drives both the API response and the mobile UI logic.
    """
    farm_id:   int
    farm_name: str

    data_status: str          # one of DATA_STATUS_* constants above
    is_persisted: bool        # True when data_status == REPORT_AVAILABLE

    # SOC figures — None when status is INSUFFICIENT_SATELLITE_DATA or NO_CROP_CYCLE
    crop_cycle_id:         Optional[int] = None
    baseline_soc_percent:  Optional[float] = None
    current_soc_percent:   Optional[float] = None
    soc_gain_percent:      Optional[float] = None
    soc_co2e:              Optional[float] = None
    soc_credits:           Optional[int] = None
    confidence_score:      Optional[float] = None
    sources_used:          List[str] = field(default_factory=list)
    message:               str = ""

    # Diagnostics
    satellite_observation_count: int = 0
    crop_cycle_found:            bool = False
    baseline_source:             Optional[str] = None
    missing_requirements:        List[str] = field(default_factory=list)

    # Phase 13 additions — available when soc_estimate is populated
    source_label:   str = ""
    recommendations: List[str] = field(default_factory=list)
    soc_estimate:   Optional["SOCEstimate"] = None   # kept for router to extract breakdown/diagnostics


# ── Internal helpers ──────────────────────────────────────────────────────────

def _pick_best_cycle(db: Session, farm_id: int) -> Optional[CropCycle]:
    """
    Select the most-relevant crop cycle for SOC overview.

    Priority:
      1. ACTIVE cycle (latest by start_date)
      2. HARVESTED / VERIFIED cycle (latest by start_date)
      3. Any non-CANCELLED cycle (latest by start_date)
      4. Any cycle (latest by start_date then created_at)
    """
    all_cycles: List[CropCycle] = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id)
        .order_by(CropCycle.start_date.desc(), CropCycle.id.desc())
        .all()
    )
    if not all_cycles:
        return None

    # Tier 1: ACTIVE
    for c in all_cycles:
        if c.status == CropCycleStatus.ACTIVE:
            return c

    # Tier 2: HARVESTED or VERIFIED
    for c in all_cycles:
        if c.status in (CropCycleStatus.HARVESTED, CropCycleStatus.VERIFIED):
            return c

    # Tier 3: anything except CANCELLED
    for c in all_cycles:
        if c.status != CropCycleStatus.CANCELLED:
            return c

    # Tier 4: latest of whatever remains
    return all_cycles[0]


def _fetch_satellite_obs_with_fallback(
    db: Session,
    farm_id: int,
    crop_cycle_id: Optional[int],
    cycle: Optional[CropCycle] = None,
) -> List[SatelliteObservation]:
    """
    Fetch satellite observations for a farm/cycle.

    Fallback strategy (prevents silent empty when obs have farm_id only):
      1. Exact match: farm_id AND crop_cycle_id
      2. If zero results: farm_id AND (crop_cycle_id IS NULL) filtered by
         date range overlapping the cycle window
      3. If still zero: all farm-level observations regardless of date

    This handles legacy simulated observations that may lack crop_cycle_id.
    """
    base_q = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.farm_id == farm_id)
    )

    # ── Strategy 1: exact cycle match ────────────────────────────────────────
    if crop_cycle_id:
        exact = (
            base_q.filter(SatelliteObservation.crop_cycle_id == crop_cycle_id)
            .order_by(SatelliteObservation.observation_date.asc())
            .all()
        )
        if exact:
            return exact

    # ── Strategy 2: farm-level obs in cycle date window ───────────────────────
    if cycle and cycle.start_date:
        end_date = cycle.end_date or __import__("datetime").date.today()
        windowed = (
            base_q.filter(
                or_(
                    SatelliteObservation.crop_cycle_id == crop_cycle_id,
                    SatelliteObservation.crop_cycle_id.is_(None),
                ),
                SatelliteObservation.observation_date >= cycle.start_date,
                SatelliteObservation.observation_date <= end_date,
            )
            .order_by(SatelliteObservation.observation_date.asc())
            .all()
        )
        if windowed:
            return windowed

    # ── Strategy 3: all farm-level observations (last resort) ────────────────
    all_obs = (
        base_q.order_by(SatelliteObservation.observation_date.asc()).all()
    )
    return all_obs


def _fetch_satellite_obs(
    db: Session,
    farm_id: int,
    crop_cycle_id: Optional[int],
    cycle: Optional[CropCycle] = None,
) -> List[SatelliteObservation]:
    """Public alias used by run_soc_estimate."""
    return _fetch_satellite_obs_with_fallback(db, farm_id, crop_cycle_id, cycle)


def _fetch_soc_measurements(
    db: Session,
    farm_id: int,
    crop_cycle_id: Optional[int],
) -> List[SOCMeasurement]:
    """Return SOC measurements for this farm (+ optional cycle)."""
    q = db.query(SOCMeasurement).filter(SOCMeasurement.farm_id == farm_id)
    if crop_cycle_id:
        q = q.filter(
            or_(
                SOCMeasurement.crop_cycle_id == crop_cycle_id,
                SOCMeasurement.crop_cycle_id.is_(None),
            )
        )
    return q.order_by(SOCMeasurement.created_at.asc()).all()


# ── Public API ────────────────────────────────────────────────────────────────

def run_soc_estimate(
    db: Session,
    farm: Farm,
    cycle: CropCycle,
) -> SOCEstimate:
    """
    Fetch all available data from existing tables and call the SOC engine.

    Uses _fetch_satellite_obs_with_fallback to capture both cycle-linked and
    farm-level satellite observations, so farms with simulated data always
    produce an estimate rather than silently falling back.

    Does NOT persist a SOCReport — call save_soc_report() for that.
    """
    soc_measurements = _fetch_soc_measurements(db, farm.id, cycle.id)
    sat_obs = _fetch_satellite_obs_with_fallback(db, farm.id, cycle.id, cycle)

    return estimate_soc(
        land_area_acres=farm.land_area_acres,
        soil_type=farm.soil_type,
        crop_type=cycle.crop_type,
        reduction_practice=cycle.reduction_practice,
        baseline_method=cycle.baseline_method,
        crop_start_date=cycle.start_date,
        crop_end_date=cycle.end_date,
        soc_measurements=soc_measurements,
        satellite_observations=sat_obs,
    )


def save_soc_report(
    db: Session,
    farm_id: int,
    crop_cycle_id: int,
    estimate: SOCEstimate,
) -> SOCReport:
    """
    Persist a SOCReport row from a SOCEstimate.

    If a report already exists for this farm+cycle, it is replaced.
    """
    existing = (
        db.query(SOCReport)
        .filter(
            SOCReport.farm_id == farm_id,
            SOCReport.crop_cycle_id == crop_cycle_id,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    report = SOCReport(
        farm_id=farm_id,
        crop_cycle_id=crop_cycle_id,
        baseline_soc=estimate.baseline_soc_percent,
        current_soc=estimate.current_soc_percent,
        soc_gain=estimate.soc_gain_percent,
        soc_co2e=estimate.soc_co2e_tonnes,
        soc_credits=estimate.soc_credits,
        confidence_score=estimate.confidence_score,
        sources_used=",".join(estimate.sources_detail) or estimate.source_used,
        methodology=estimate.methodology_notes,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def build_soc_overview(db: Session, farm: Farm) -> SOCOverviewResult:
    """
    Build a rich SOC overview for a farm.

    Priority logic:
      1. Find best crop cycle (_pick_best_cycle)
      2. If saved SOCReport exists → REPORT_AVAILABLE
      3. Elif satellite observations exist → run live estimate → LIVE_ESTIMATE
      4. Elif crop cycle exists but no satellite data → INSUFFICIENT_SATELLITE_DATA
      5. Else → NO_CROP_CYCLE

    This is the single source of truth for GET /soc/farms/{id}/overview.
    Never returns empty when usable data exists.
    """
    cycle = _pick_best_cycle(db, farm.id)
    missing: List[str] = []

    # ── Case: no crop cycle ───────────────────────────────────────────────────
    if cycle is None:
        missing.append("NO_ACTIVE_CROP_CYCLE")
        return SOCOverviewResult(
            farm_id=farm.id,
            farm_name=farm.farm_name,
            data_status=DATA_STATUS_NO_CROP_CYCLE,
            is_persisted=False,
            crop_cycle_found=False,
            satellite_observation_count=0,
            missing_requirements=missing,
            message="Create a crop cycle before SOC can be estimated.",
        )

    # ── Case: saved SOC report exists ────────────────────────────────────────
    saved_report: Optional[SOCReport] = (
        db.query(SOCReport)
        .filter(SOCReport.farm_id == farm.id, SOCReport.crop_cycle_id == cycle.id)
        .order_by(SOCReport.created_at.desc())
        .first()
    )

    sat_count = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.farm_id == farm.id)
        .count()
    )

    if saved_report:
        sources = [s.strip() for s in (saved_report.sources_used or "").split(",") if s.strip()]
        # Re-run the estimate so we have breakdown/diagnostics even for saved reports
        soc_meas_saved = _fetch_soc_measurements(db, farm.id, cycle.id)
        sat_obs_saved  = _fetch_satellite_obs_with_fallback(db, farm.id, cycle.id, cycle)
        live_est_for_saved = estimate_soc(
            land_area_acres=farm.land_area_acres,
            soil_type=farm.soil_type,
            crop_type=cycle.crop_type,
            reduction_practice=cycle.reduction_practice,
            baseline_method=cycle.baseline_method,
            crop_start_date=cycle.start_date,
            crop_end_date=cycle.end_date,
            soc_measurements=soc_meas_saved,
            satellite_observations=sat_obs_saved,
        )
        return SOCOverviewResult(
            farm_id=farm.id,
            farm_name=farm.farm_name,
            data_status=DATA_STATUS_REPORT_AVAILABLE,
            is_persisted=True,
            crop_cycle_id=cycle.id,
            crop_cycle_found=True,
            baseline_soc_percent=saved_report.baseline_soc,
            current_soc_percent=saved_report.current_soc,
            soc_gain_percent=saved_report.soc_gain,
            soc_co2e=saved_report.soc_co2e,
            soc_credits=saved_report.soc_credits,
            confidence_score=saved_report.confidence_score,
            sources_used=sources,
            baseline_source=sources[0] if sources else "ESTIMATED",
            satellite_observation_count=sat_count,
            missing_requirements=[],
            message="SOC report available for this farm.",
            source_label=live_est_for_saved.source_label,
            recommendations=live_est_for_saved.recommendations,
            soc_estimate=live_est_for_saved,
        )

    # ── Case: no saved report — try live estimate ─────────────────────────────
    sat_obs = _fetch_satellite_obs_with_fallback(db, farm.id, cycle.id, cycle)
    sat_count_for_cycle = len(sat_obs)

    if sat_count_for_cycle == 0:
        missing.append("NO_SATELLITE_OBSERVATIONS")
        return SOCOverviewResult(
            farm_id=farm.id,
            farm_name=farm.farm_name,
            data_status=DATA_STATUS_INSUFFICIENT_SATELLITE,
            is_persisted=False,
            crop_cycle_id=cycle.id,
            crop_cycle_found=True,
            satellite_observation_count=0,
            missing_requirements=missing,
            message=(
                "Satellite observations are required to estimate SOC. "
                "Add observations via the Satellite Insights screen."
            ),
        )

    # Live estimate using existing satellite observations
    soc_measurements = _fetch_soc_measurements(db, farm.id, cycle.id)
    est = estimate_soc(
        land_area_acres=farm.land_area_acres,
        soil_type=farm.soil_type,
        crop_type=cycle.crop_type,
        reduction_practice=cycle.reduction_practice,
        baseline_method=cycle.baseline_method,
        crop_start_date=cycle.start_date,
        crop_end_date=cycle.end_date,
        soc_measurements=soc_measurements,
        satellite_observations=sat_obs,
    )

    return SOCOverviewResult(
        farm_id=farm.id,
        farm_name=farm.farm_name,
        data_status=DATA_STATUS_LIVE_ESTIMATE,
        is_persisted=False,
        crop_cycle_id=cycle.id,
        crop_cycle_found=True,
        baseline_soc_percent=est.baseline_soc_percent,
        current_soc_percent=est.current_soc_percent,
        soc_gain_percent=est.soc_gain_percent,
        soc_co2e=est.soc_co2e_tonnes,
        soc_credits=est.soc_credits,
        confidence_score=est.confidence_score,
        sources_used=est.sources_detail,
        baseline_source=est.source_used,
        satellite_observation_count=sat_count_for_cycle,
        missing_requirements=[],
        message=(
            "Live SOC estimate generated from satellite observations and crop cycle data. "
            "Generate a SOC report to save this estimate."
        ),
        source_label=est.source_label,
        recommendations=est.recommendations,
        soc_estimate=est,
    )


def get_combined_report(
    db: Session,
    farm: Farm,
    cycle: CropCycle,
) -> CombinedCarbonReport:
    """
    Build a CombinedCarbonReport merging methane (from CarbonReport) + SOC.

    If no CarbonReport exists for this cycle the methane section is zeros.
    SOC estimate is always computed live from available data (uses fallback obs).
    """
    carbon_report: Optional[CarbonReport] = (
        db.query(CarbonReport)
        .filter(
            CarbonReport.farm_id == farm.id,
            CarbonReport.crop_cycle_id == cycle.id,
        )
        .order_by(CarbonReport.created_at.desc())
        .first()
    )

    soc_estimate = run_soc_estimate(db, farm, cycle)

    if carbon_report:
        return CombinedCarbonReport(
            farm_id=farm.id,
            crop_cycle_id=cycle.id,
            carbon_report_id=carbon_report.id,
            baseline_methane_kg=carbon_report.baseline_methane_kg,
            current_methane_kg=carbon_report.current_methane_kg,
            methane_reduction_kg=carbon_report.methane_reduction_kg,
            methane_co2e_tonnes=carbon_report.co2e_reduction_tonnes,
            methane_credits=carbon_report.estimated_credits,
            report_hash=carbon_report.report_hash,
            soc_estimate=soc_estimate,
        )

    return CombinedCarbonReport(
        farm_id=farm.id,
        crop_cycle_id=cycle.id,
        carbon_report_id=None,
        baseline_methane_kg=0.0,
        current_methane_kg=0.0,
        methane_reduction_kg=0.0,
        methane_co2e_tonnes=0.0,
        methane_credits=0,
        report_hash="",
        soc_estimate=soc_estimate,
    )
