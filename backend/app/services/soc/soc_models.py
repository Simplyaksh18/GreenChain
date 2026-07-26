"""
soc_models.py — Dataclasses for SOC calculation results.

These are pure Python data containers; no SQLAlchemy / Pydantic dependency.
They are produced by soc_engine.py and consumed by soc_service.py and the
router layer.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Constants ─────────────────────────────────────────────────────────────────

# IPCC Tier 1 soil parameters for tropical / South Asian agricultural soils
BULK_DENSITY_G_CM3   = 1.3      # g/cm³ — typical Vertisol / Alfisol
SAMPLING_DEPTH_M     = 0.30     # 0–30 cm layer (IPCC Tier 1 standard)
SOIL_MASS_T_PER_HA   = (        # tonnes of soil per ha in 0–30 cm layer
    10_000          # m² per ha
    * SAMPLING_DEPTH_M           # depth (m)
    * BULK_DENSITY_G_CM3 * 1000  # kg/m³
    / 1000                       # → tonnes
)  # = 3,900 t/ha

# C → CO₂ conversion: 1 tonne C = 44/12 tonnes CO₂
C_TO_CO2E = 44.0 / 12.0         # ≈ 3.6667

# Fallback SOC % baselines (Tamil Nadu / South Indian rice soils)
SOC_FALLBACK_LOW    = 0.40      # degraded / sandy soils
SOC_FALLBACK_MEDIUM = 0.65      # typical Vertisol / Alfisol
SOC_FALLBACK_HIGH   = 0.90      # well-managed or organic soils

# NDVI proxy coefficient — Δ%SOC per unit of mean NDVI above threshold
# Derived from Ghimire et al. (2012) and ISRIC Soil Carbon mapping studies
# for 0–30 cm depth in South Asian tropical systems.
NDVI_SOC_ALPHA           = 0.12   # %SOC gain per NDVI unit above threshold
NDVI_BASELINE_THRESHOLD  = 0.30   # NDVI below which no net SOC gain assumed

# Minimum observations needed to use satellite-based estimation (else fallback)
MIN_SATELLITE_OBS = 3

# ── Provider source tag sets ──────────────────────────────────────────────────
# Used by soc_engine to classify observation quality.

# Real-provider source tags (non-simulated observations)
REAL_COPERNICUS_SOURCES = frozenset({"SENTINEL_2", "LANDSAT_8"})
REAL_BHUVAN_SOURCES     = frozenset({"BHUVAN", "SATELLITE_MANUAL", "SATELLITE_IMPORTED"})
SIMULATED_SOURCES       = frozenset({"SATELLITE_SIMULATED"})

# Provider confidence multipliers (applied to observation confidence)
PROVIDER_CONFIDENCE: Dict[str, float] = {
    "LAB":                 0.95,
    "MANUAL":              0.80,
    "COPERNICUS":          0.85,   # Sentinel-2 / real Copernicus obs
    "BHUVAN":              0.80,   # Bhuvan/NRSC soil layers
    "SENTINEL_2":          0.85,
    "LANDSAT_8":           0.80,
    "SATELLITE_MANUAL":    0.75,
    "SATELLITE_IMPORTED":  0.70,
    "SATELLITE_SIMULATED": 0.45,
    "ESTIMATED":           0.25,
}


# ── Crop type SOC multipliers ─────────────────────────────────────────────────
# Relative SOC accumulation potential by crop type.
# Source: IPCC 2019 Refinement, Table 5.5; Poeplau & Don 2015.
CROP_SOC_FACTORS: dict[str, float] = {
    "paddy":     1.00,   # flooded rice — high residue return
    "rice":      1.00,
    "wheat":     0.85,
    "sugarcane": 1.20,   # high biomass / residue
    "maize":     0.90,
    "cotton":    0.85,
    "soybean":   0.88,
    "pulses":    0.95,
    "groundnut": 0.90,
    "default":   0.80,
}

# ── Practice SOC multipliers ─────────────────────────────────────────────────
PRACTICE_SOC_FACTORS: dict[str, float] = {
    "sri":               1.10,   # System of Rice Intensification — stronger root biomass
    "awd":               0.95,   # Alternate Wetting and Drying
    "no-till":           1.15,
    "mulching":          1.10,
    "cover crop":        1.08,
    "organic amendment": 1.20,
    "default":           1.00,
}


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class SOCDiagnostics:
    """
    Auditable inputs used by the SOC calculation.
    Returned alongside SOCEstimate for transparency.
    """
    provider_used:         str            # primary data source
    observation_count:     int            # number of satellite/SOC obs used
    ndvi_average:          Optional[float]  # mean NDVI used (None if no sat obs)
    farm_area_ha:          float
    bulk_density:          float          # g/cm³ — always 1.3 (IPCC Tier 1)
    soil_depth_cm:         float          # always 30 cm
    calculation_version:   str = "v1"
    observation_dates:     List[str] = field(default_factory=list)  # ISO dates
    baseline_soc_source:   str = "ESTIMATED"
    soc_gain_formula:      str = (
        "Δ%SOC = α × max(0, mean(NDVI) − 0.30) × (days/120) × crop_factor × practice_factor"
    )
    co2e_conversion:       str = "soc_tonnes × 44/12"


@dataclass
class SOCEstimate:
    """
    SOC estimation result for one farm/crop-cycle.

    All area figures are expressed per whole farm (not per hectare).
    """
    baseline_soc_percent:  float          # %SOC at cycle start
    current_soc_percent:   float          # %SOC at cycle end (estimated or observed)
    soc_gain_percent:      float          # Δ%SOC = current − baseline
    estimated_soc_tonnes:  float          # tonnes of SOC gained (whole farm)
    soc_co2e_tonnes:       float          # tCO₂e (× C_TO_CO2E)
    soc_credits:           int            # floor(soc_co2e_tonnes); INFORMATIONAL
    confidence_score:      float          # 0–1
    source_used:           str            # "LAB", "MANUAL", "COPERNICUS", "ESTIMATED", …
    sources_detail:        List[str] = field(default_factory=list)
    methodology_notes:     str = ""

    # ── Phase 13 additions ────────────────────────────────────────────────────
    source_label:          str = ""       # human-readable source description
    confidence_breakdown:  Dict[str, Any] = field(default_factory=dict)
    diagnostics:           Optional[SOCDiagnostics] = None
    recommendations:       List[str] = field(default_factory=list)

    @property
    def is_informational_only(self) -> bool:
        """SOC credits must NOT be minted in Phase 12.5."""
        return True


@dataclass
class CombinedCarbonReport:
    """
    Full combined carbon report: methane section + SOC section + totals.

    Minting rules (Phase 12.5):
      mintable_credits         = methane_credits   (only)
      total_potential_credits  = methane_credits + soc_credits (display only)
    """
    # ── Identifiers ──────────────────────────────────────────────────────────
    farm_id:        int
    crop_cycle_id:  int
    carbon_report_id: Optional[int]

    # ── Methane section (from existing CarbonReport) ─────────────────────────
    baseline_methane_kg:    float
    current_methane_kg:     float
    methane_reduction_kg:   float
    methane_co2e_tonnes:    float   # = co2e_reduction_tonnes
    methane_credits:        int     # MINTABLE
    report_hash:            str

    # ── SOC section (informational) ─────────────────────────────────────────
    soc_estimate: Optional[SOCEstimate]

    # ── Combined totals ──────────────────────────────────────────────────────
    @property
    def soc_credits(self) -> int:
        return self.soc_estimate.soc_credits if self.soc_estimate else 0

    @property
    def total_potential_credits(self) -> int:
        """Methane + SOC; for display purposes only."""
        return self.methane_credits + self.soc_credits

    @property
    def mintable_credits(self) -> int:
        """Only methane credits are mintable in Phase 12.5."""
        return self.methane_credits
