"""
soc_schema.py — Pydantic request/response schemas for Phase 12.5 / Phase 13 SOC module.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator

from app.models.soc import SOCSource


# ── SOC Measurement ────────────────────────────────────────────────────────────

class SOCMeasurementCreate(BaseModel):
    soc_percent:      float
    soc_source:       SOCSource
    confidence_score: float = 1.0
    notes:            Optional[str] = None
    crop_cycle_id:    Optional[int] = None

    @field_validator("soc_percent")
    @classmethod
    def _pct_range(cls, v: float) -> float:
        if not (0.0 <= v <= 100.0):
            raise ValueError("soc_percent must be between 0 and 100")
        return v

    @field_validator("confidence_score")
    @classmethod
    def _conf_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence_score must be between 0.0 and 1.0")
        return v


class SOCMeasurementResponse(BaseModel):
    id:               int
    farm_id:          int
    crop_cycle_id:    Optional[int]
    soc_percent:      float
    soc_source:       SOCSource
    confidence_score: float
    notes:            Optional[str]
    created_at:       datetime
    updated_at:       datetime

    model_config = {"from_attributes": True}


# ── Confidence Breakdown ───────────────────────────────────────────────────────

class SOCConfidenceBreakdown(BaseModel):
    """Explainable per-component confidence scores (0–100 scale)."""
    baseline_source:       str
    baseline_confidence:   int     # 0–100
    observation_source:    str
    observation_confidence: int    # 0–100
    provider_confidence:   int     # 0–100
    crop_cycle_confidence: int     # 0–100
    final_confidence:      int     # 0–100
    reason:                str


# ── SOC Diagnostics ───────────────────────────────────────────────────────────

class SOCDiagnosticsResponse(BaseModel):
    """Auditable inputs used by the SOC calculation."""
    provider_used:       str
    observation_count:   int
    ndvi_average:        Optional[float]
    farm_area_ha:        float
    bulk_density:        float
    soil_depth_cm:       float
    calculation_version: str
    observation_dates:   List[str] = []
    baseline_soc_source: str
    soc_gain_formula:    str
    co2e_conversion:     str


# ── SOC Estimate (transient — not a DB row) ────────────────────────────────────

class SOCEstimateResponse(BaseModel):
    baseline_soc_percent:   float
    current_soc_percent:    float
    soc_gain_percent:       float
    estimated_soc_tonnes:   float
    soc_co2e_tonnes:        float
    soc_credits:            int
    confidence_score:       float
    source_used:            str
    sources_detail:         List[str]
    methodology_notes:      str
    is_informational_only:  bool = True

    # Phase 13 additions
    source_label:           str = ""
    confidence_breakdown:   Optional[SOCConfidenceBreakdown] = None
    diagnostics:            Optional[SOCDiagnosticsResponse] = None
    recommendations:        List[str] = []


# ── SOC Report (persisted) ─────────────────────────────────────────────────────

class SOCReportResponse(BaseModel):
    id:               int
    farm_id:          int
    crop_cycle_id:    int
    baseline_soc:     float
    current_soc:      float
    soc_gain:         float
    soc_co2e:         float
    soc_credits:      int
    confidence_score: float
    sources_used:     str
    methodology:      Optional[str]
    created_at:       datetime
    is_informational_only: bool = True   # always True in Phase 12.5

    model_config = {"from_attributes": True}


# ── Combined Carbon + SOC report ───────────────────────────────────────────────

class MethaneSectionResponse(BaseModel):
    baseline_methane_kg:   float
    current_methane_kg:    float
    methane_reduction_kg:  float
    methane_co2e_tonnes:   float
    methane_credits:       int
    report_hash:           str


class SOCSectionResponse(BaseModel):
    baseline_soc_percent:  float
    current_soc_percent:   float
    soc_gain_percent:      float
    soc_co2e_tonnes:       float
    soc_credits:           int          # informational only
    sources_used:          List[str]
    confidence_score:      float
    is_informational_only: bool = True

    # Phase 13 additions
    source_label:          str = ""
    confidence_breakdown:  Optional[SOCConfidenceBreakdown] = None
    diagnostics:           Optional[SOCDiagnosticsResponse] = None
    recommendations:       List[str] = []


class CombinedReportResponse(BaseModel):
    farm_id:        int
    crop_cycle_id:  int
    carbon_report_id: Optional[int]

    methane_section:  MethaneSectionResponse
    soc_section:      SOCSectionResponse

    # ── Combined totals (Phase 12.5) ────────────────────────────────────────
    methane_credits:        int           # MINTABLE
    soc_credits:            int           # INFORMATIONAL ONLY
    total_potential_credits: int          # methane + soc (display only)
    mintable_credits:       int           # = methane_credits

    minting_note: str = (
        "Phase 12.5: Only methane credits are mintable. "
        "SOC credits are informational and will be enabled in a future phase."
    )


# ── Farm SOC overview (Farm Detail screen) ─────────────────────────────────────

class FarmSOCOverviewResponse(BaseModel):
    farm_id:         int
    farm_name:       str

    # ── Status ──────────────────────────────────────────────────────────────
    data_status:     str
    is_persisted:    bool
    crop_cycle_id:   Optional[int] = None

    # ── SOC figures (None when no estimate possible) ─────────────────────────
    baseline_soc_percent: Optional[float] = None
    current_soc_percent:  Optional[float] = None
    soc_gain_percent:     Optional[float] = None
    soc_co2e:             Optional[float] = None
    soc_credits:          Optional[int]   = None
    confidence_score:     Optional[float] = None
    sources_used:         List[str]        = []
    message:              str              = ""

    # ── Diagnostics ──────────────────────────────────────────────────────────
    satellite_observation_count: int        = 0
    crop_cycle_found:            bool       = False
    baseline_source:             Optional[str] = None
    missing_requirements:        List[str]  = []

    # ── Always informational ─────────────────────────────────────────────────
    is_informational_only: bool = True

    # ── Phase 13 additions ───────────────────────────────────────────────────
    source_label:          str = ""
    confidence_breakdown:  Optional[SOCConfidenceBreakdown] = None
    diagnostics:           Optional[SOCDiagnosticsResponse] = None
    recommendations:       List[str] = []
