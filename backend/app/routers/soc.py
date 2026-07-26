"""
soc.py — Phase 12.5 SOC (Soil Organic Carbon) router.

Endpoints:

  POST   /soc/farms/{farm_id}/measurements              — add a SOC measurement
  GET    /soc/farms/{farm_id}/measurements              — list measurements for a farm
  GET    /soc/farms/{farm_id}/crop-cycles/{cycle_id}/estimate  — live SOC estimate
  POST   /soc/farms/{farm_id}/crop-cycles/{cycle_id}/report    — generate + save SOC report
  GET    /soc/farms/{farm_id}/crop-cycles/{cycle_id}/report    — retrieve saved SOC report
  GET    /soc/farms/{farm_id}/crop-cycles/{cycle_id}/combined  — full methane + SOC report
  GET    /soc/farms/{farm_id}/overview                  — farm-level SOC summary

Minting rules (Phase 12.5):
  Only methane credits are mintable.
  SOC credits are informational and must NOT be passed to the minting,
  custodial balance, payout, or registry submission pipelines.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.farm import Farm, CropCycle
from app.models.fpo import FPOProfile
from app.models.soc import SOCMeasurement, SOCReport
from app.models.user import User, UserRole
from app.schemas.soc_schema import (
    CombinedReportResponse,
    FarmSOCOverviewResponse,
    MethaneSectionResponse,
    SOCConfidenceBreakdown,
    SOCDiagnosticsResponse,
    SOCEstimateResponse,
    SOCMeasurementCreate,
    SOCMeasurementResponse,
    SOCReportResponse,
    SOCSectionResponse,
)
from app.services.soc.soc_service import (
    build_soc_overview,
    get_combined_report,
    run_soc_estimate,
    save_soc_report,
)

router = APIRouter(prefix="/soc", tags=["SOC — Soil Organic Carbon"])


# ── Helper: convert engine dataclasses → Pydantic schema objects ───────────────

def _breakdown_schema(est) -> Optional[SOCConfidenceBreakdown]:
    bd = est.confidence_breakdown
    if not bd:
        return None
    return SOCConfidenceBreakdown(
        baseline_source=bd.get("baseline_source", "ESTIMATED"),
        baseline_confidence=bd.get("baseline_confidence", 0),
        observation_source=bd.get("observation_source", "NO_DATA"),
        observation_confidence=bd.get("observation_confidence", 0),
        provider_confidence=bd.get("provider_confidence", 0),
        crop_cycle_confidence=bd.get("crop_cycle_confidence", 0),
        final_confidence=bd.get("final_confidence", 0),
        reason=bd.get("reason", ""),
    )


def _diagnostics_schema(est) -> Optional[SOCDiagnosticsResponse]:
    d = est.diagnostics
    if not d:
        return None
    return SOCDiagnosticsResponse(
        provider_used=d.provider_used,
        observation_count=d.observation_count,
        ndvi_average=d.ndvi_average,
        farm_area_ha=d.farm_area_ha,
        bulk_density=d.bulk_density,
        soil_depth_cm=d.soil_depth_cm,
        calculation_version=d.calculation_version,
        observation_dates=d.observation_dates,
        baseline_soc_source=d.baseline_soc_source,
        soc_gain_formula=d.soc_gain_formula,
        co2e_conversion=d.co2e_conversion,
    )


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _farm_or_404(farm_id: int, db: Session) -> Farm:
    farm = db.query(Farm).filter(Farm.id == farm_id, Farm.is_deleted.is_(False)).first()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    return farm


def _cycle_or_404(cycle_id: int, farm_id: int, db: Session) -> CropCycle:
    cycle = (
        db.query(CropCycle)
        .filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id)
        .first()
    )
    if not cycle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop cycle not found")
    return cycle


def _assert_access(farm: Farm, current_user: User, db: Session) -> None:
    """FARMER (own), FPO (linked), VERIFIER/ADMIN (all)."""
    if current_user.role in (UserRole.ADMIN, UserRole.VERIFIER):
        return
    if current_user.role == UserRole.FARMER:
        if farm.farmer_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return
    if current_user.role == UserRole.FPO:
        profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
        if not profile or farm.fpo_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _assert_write_access(farm: Farm, current_user: User, db: Session) -> None:
    """FARMER (own), FPO (linked), ADMIN. VERIFIER read-only."""
    if current_user.role == UserRole.VERIFIER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verifiers may view but not create SOC data",
        )
    _assert_access(farm, current_user, db)


# ── POST /soc/farms/{farm_id}/measurements ────────────────────────────────────

@router.post(
    "/farms/{farm_id}/measurements",
    response_model=SOCMeasurementResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_soc_measurement(
    farm_id: int,
    payload: SOCMeasurementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a SOC % measurement for a farm.

    Use soc_source=LAB or MANUAL for direct measurements.
    Use COPERNICUS or BHUVAN for satellite-derived inputs.
    ESTIMATED is set by the system during automatic estimation.
    """
    farm = _farm_or_404(farm_id, db)
    _assert_write_access(farm, current_user, db)

    if payload.crop_cycle_id:
        _cycle_or_404(payload.crop_cycle_id, farm_id, db)

    m = SOCMeasurement(
        farm_id=farm_id,
        crop_cycle_id=payload.crop_cycle_id,
        soc_percent=payload.soc_percent,
        soc_source=payload.soc_source,
        confidence_score=payload.confidence_score,
        notes=payload.notes,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


# ── GET /soc/farms/{farm_id}/measurements ────────────────────────────────────

@router.get(
    "/farms/{farm_id}/measurements",
    response_model=List[SOCMeasurementResponse],
)
def list_soc_measurements(
    farm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all SOC measurements for a farm, newest first."""
    farm = _farm_or_404(farm_id, db)
    _assert_access(farm, current_user, db)
    return (
        db.query(SOCMeasurement)
        .filter(SOCMeasurement.farm_id == farm_id)
        .order_by(SOCMeasurement.created_at.desc())
        .all()
    )


# ── GET /soc/farms/{farm_id}/crop-cycles/{cycle_id}/estimate ─────────────────

@router.get(
    "/farms/{farm_id}/crop-cycles/{cycle_id}/estimate",
    response_model=SOCEstimateResponse,
)
def get_soc_estimate(
    farm_id: int,
    cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Compute a live SOC estimate from existing platform data.

    Uses: satellite observations (NDVI/NDWI), SOC measurements, crop cycle
    metadata, and farm metadata.  Does NOT persist the estimate.
    Call POST .../report to save it.
    """
    farm = _farm_or_404(farm_id, db)
    _assert_access(farm, current_user, db)
    cycle = _cycle_or_404(cycle_id, farm_id, db)

    est = run_soc_estimate(db, farm, cycle)
    return SOCEstimateResponse(
        baseline_soc_percent=est.baseline_soc_percent,
        current_soc_percent=est.current_soc_percent,
        soc_gain_percent=est.soc_gain_percent,
        estimated_soc_tonnes=est.estimated_soc_tonnes,
        soc_co2e_tonnes=est.soc_co2e_tonnes,
        soc_credits=est.soc_credits,
        confidence_score=est.confidence_score,
        source_used=est.source_used,
        sources_detail=est.sources_detail,
        methodology_notes=est.methodology_notes,
        is_informational_only=True,
        source_label=est.source_label,
        confidence_breakdown=_breakdown_schema(est),
        diagnostics=_diagnostics_schema(est),
        recommendations=est.recommendations,
    )


# ── POST /soc/farms/{farm_id}/crop-cycles/{cycle_id}/report ──────────────────

@router.post(
    "/farms/{farm_id}/crop-cycles/{cycle_id}/report",
    response_model=SOCReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_soc_report(
    farm_id: int,
    cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate and persist a SOC report for a farm/crop-cycle.

    Overwrites any existing SOC report for the same cycle.
    SOC credits in this report are INFORMATIONAL ONLY (not mintable).
    """
    farm = _farm_or_404(farm_id, db)
    _assert_write_access(farm, current_user, db)
    cycle = _cycle_or_404(cycle_id, farm_id, db)

    est = run_soc_estimate(db, farm, cycle)
    report = save_soc_report(db, farm_id, cycle_id, est)
    return report


# ── GET /soc/farms/{farm_id}/crop-cycles/{cycle_id}/report ───────────────────

@router.get(
    "/farms/{farm_id}/crop-cycles/{cycle_id}/report",
    response_model=SOCReportResponse,
)
def get_soc_report(
    farm_id: int,
    cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve the most-recently saved SOC report for a crop cycle."""
    farm = _farm_or_404(farm_id, db)
    _assert_access(farm, current_user, db)
    _cycle_or_404(cycle_id, farm_id, db)

    report = (
        db.query(SOCReport)
        .filter(SOCReport.farm_id == farm_id, SOCReport.crop_cycle_id == cycle_id)
        .order_by(SOCReport.created_at.desc())
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SOC report found. Call POST .../report to generate one.",
        )
    return report


# ── GET /soc/farms/{farm_id}/crop-cycles/{cycle_id}/combined ─────────────────

@router.get(
    "/farms/{farm_id}/crop-cycles/{cycle_id}/combined",
    response_model=CombinedReportResponse,
)
def get_combined_carbon_report(
    farm_id: int,
    cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Full combined carbon report: Methane section + SOC section + totals.

    Minting rules:
      mintable_credits        = methane_credits (only)
      total_potential_credits = methane_credits + soc_credits (display only)

    SOC credits are informational and must NOT be submitted to the minting,
    custodial balance, payout, or registry submission pipelines.
    """
    farm = _farm_or_404(farm_id, db)
    _assert_access(farm, current_user, db)
    cycle = _cycle_or_404(cycle_id, farm_id, db)

    combined = get_combined_report(db, farm, cycle)
    est = combined.soc_estimate

    return CombinedReportResponse(
        farm_id=farm.id,
        crop_cycle_id=cycle.id,
        carbon_report_id=combined.carbon_report_id,
        methane_section=MethaneSectionResponse(
            baseline_methane_kg=combined.baseline_methane_kg,
            current_methane_kg=combined.current_methane_kg,
            methane_reduction_kg=combined.methane_reduction_kg,
            methane_co2e_tonnes=combined.methane_co2e_tonnes,
            methane_credits=combined.methane_credits,
            report_hash=combined.report_hash,
        ),
        soc_section=SOCSectionResponse(
            baseline_soc_percent=est.baseline_soc_percent if est else 0.0,
            current_soc_percent=est.current_soc_percent if est else 0.0,
            soc_gain_percent=est.soc_gain_percent if est else 0.0,
            soc_co2e_tonnes=est.soc_co2e_tonnes if est else 0.0,
            soc_credits=est.soc_credits if est else 0,
            sources_used=est.sources_detail if est else [],
            confidence_score=est.confidence_score if est else 0.0,
            is_informational_only=True,
            source_label=est.source_label if est else "",
            confidence_breakdown=_breakdown_schema(est) if est else None,
            diagnostics=_diagnostics_schema(est) if est else None,
            recommendations=est.recommendations if est else [],
        ),
        methane_credits=combined.methane_credits,
        soc_credits=combined.soc_credits,
        total_potential_credits=combined.total_potential_credits,
        mintable_credits=combined.mintable_credits,
    )


# ── GET /soc/farms/{farm_id}/overview ────────────────────────────────────────

@router.get(
    "/farms/{farm_id}/overview",
    response_model=FarmSOCOverviewResponse,
)
def get_farm_soc_overview(
    farm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Farm Detail SOC Overview.

    Returns a rich status-driven response so the mobile always knows exactly
    what SOC data is available and what to show.

    data_status values:
      REPORT_AVAILABLE          — saved SOC report exists (is_persisted=True)
      LIVE_ESTIMATE             — no saved report but satellite obs exist; live calc
      INSUFFICIENT_SATELLITE_DATA — crop cycle exists but no satellite observations
      NO_CROP_CYCLE             — no crop cycle registered for this farm

    Never returns empty when usable satellite or crop cycle data exists.
    SOC credits are INFORMATIONAL ONLY — not mintable in Phase 12.5.
    """
    farm = _farm_or_404(farm_id, db)
    _assert_access(farm, current_user, db)

    result = build_soc_overview(db, farm)

    return FarmSOCOverviewResponse(
        farm_id=result.farm_id,
        farm_name=result.farm_name,
        data_status=result.data_status,
        is_persisted=result.is_persisted,
        crop_cycle_id=result.crop_cycle_id,
        baseline_soc_percent=result.baseline_soc_percent,
        current_soc_percent=result.current_soc_percent,
        soc_gain_percent=result.soc_gain_percent,
        soc_co2e=result.soc_co2e,
        soc_credits=result.soc_credits,
        confidence_score=result.confidence_score,
        sources_used=result.sources_used,
        message=result.message,
        satellite_observation_count=result.satellite_observation_count,
        crop_cycle_found=result.crop_cycle_found,
        baseline_source=result.baseline_source,
        missing_requirements=result.missing_requirements,
        is_informational_only=True,
        source_label=result.source_label,
        confidence_breakdown=_breakdown_schema(result.soc_estimate) if result.soc_estimate else None,
        diagnostics=_diagnostics_schema(result.soc_estimate) if result.soc_estimate else None,
        recommendations=result.recommendations,
    )
