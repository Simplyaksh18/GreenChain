"""
soc_engine.py — SOC estimation logic.

Estimation pipeline
───────────────────
1.  Resolve baseline %SOC:
      LAB measurement      → highest priority (conf 0.95)
      MANUAL measurement   → (conf 0.80)
      Bhuvan/NRSC layers   → (conf 0.75)
      Copernicus obs        → (conf 0.70)
      District-level fallback (Tamil Nadu defaults) → (conf 0.25)

2.  Estimate current %SOC from available satellite observations:
      mean(NDVI) over crop cycle as vegetation biomass proxy
      apply crop-type and practice multipliers
      add to baseline
      Provider confidence factored by data source quality.

3.  Compute SOC change → tonnes → CO₂e → credits

4.  Build confidence breakdown, diagnostics, recommendations.

Formulas & assumptions
──────────────────────
* Bulk density    : 1.3 g/cm³  (IPCC Tier 1; typical Indian Vertisol/Alfisol)
* Sampling depth  : 0.30 m     (IPCC Tier 1 standard)
* Soil mass/ha    : 3,900 t    (10,000 m² × 0.30 m × 1,300 kg/m³)
* C → CO₂e       : × 44/12    (molecular weight ratio)
* NDVI proxy α   : 0.12 %SOC per NDVI unit above 0.30 (Ghimire et al. 2012,
                   ISRIC soil carbon mapping, tropical South Asian systems)
* Credits         : floor(CO₂e tonnes); INFORMATIONAL ONLY in Phase 12.5

References
──────────
- IPCC 2006/2019 Tier 1 Guidelines for National Greenhouse Gas Inventories,
  Volume 4 Agriculture, Forestry and Other Land Use, Chapter 2.
- Ghimire R. et al. (2012). "Soil Carbon Sequestration under Paddy and Dryland
  Cropping Systems", Journal of Soil Science 63:403–412.
- Poeplau C. & Don A. (2015). "Carbon sequestration in agricultural soils via
  cultivation of cover crops", Agriculture Ecosystems & Environment 200:33–41.
- ISRIC World Soil Information (2017). SoilGrids250m for SOC baseline mapping.
"""
from __future__ import annotations

import math
import statistics
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from app.services.soc.soc_models import (
    SOCDiagnostics,
    SOCEstimate,
    BULK_DENSITY_G_CM3,
    SAMPLING_DEPTH_M,
    SOIL_MASS_T_PER_HA,
    C_TO_CO2E,
    SOC_FALLBACK_LOW,
    SOC_FALLBACK_MEDIUM,
    SOC_FALLBACK_HIGH,
    NDVI_SOC_ALPHA,
    NDVI_BASELINE_THRESHOLD,
    MIN_SATELLITE_OBS,
    CROP_SOC_FACTORS,
    PRACTICE_SOC_FACTORS,
    PROVIDER_CONFIDENCE,
    REAL_COPERNICUS_SOURCES,
    REAL_BHUVAN_SOURCES,
    SIMULATED_SOURCES,
)


# ── Soil type → SOC fallback bucket mapping ───────────────────────────────────
_SOIL_SOC_BUCKET: Dict[str, str] = {
    "clay":       "medium",
    "clay loam":  "medium",
    "loam":       "medium",
    "sandy loam": "low",
    "sandy":      "low",
    "sand":       "low",
    "silt":       "medium",
    "silt loam":  "medium",
    "black":      "high",    # Vertisols (cotton-growing black soil)
    "red":        "low",
    "laterite":   "low",
    "organic":    "high",
    "peat":       "high",
}

# ── Source-label mapping ──────────────────────────────────────────────────────
_SOURCE_LABELS: Dict[str, str] = {
    "LAB":                 "Measured from lab SOC test",
    "MANUAL":              "Manual soil-test entry",
    "COPERNICUS":          "Derived from Copernicus observations",
    "SENTINEL_2":          "Derived from Copernicus (Sentinel-2) observations",
    "LANDSAT_8":           "Derived from Copernicus (Landsat-8) observations",
    "BHUVAN":              "Derived from Bhuvan/NRSC soil layers",
    "SATELLITE_MANUAL":    "Derived from manually uploaded satellite data",
    "SATELLITE_IMPORTED":  "Derived from imported satellite observations",
    "SATELLITE_SIMULATED": "Derived from simulated satellite data",
    "ESTIMATED":           "Estimated from fallback model",
}


def _soil_type_to_fallback(soil_type: str) -> float:
    """Map farm.soil_type string → SOC fallback %."""
    bucket = _SOIL_SOC_BUCKET.get(soil_type.lower().strip(), "medium")
    return {
        "low":    SOC_FALLBACK_LOW,
        "medium": SOC_FALLBACK_MEDIUM,
        "high":   SOC_FALLBACK_HIGH,
    }[bucket]


def _crop_factor(crop_type: str) -> float:
    """SOC accumulation multiplier by crop type."""
    return CROP_SOC_FACTORS.get(crop_type.lower().strip(), CROP_SOC_FACTORS["default"])


def _practice_factor(reduction_practice: str, baseline_method: str) -> float:
    """SOC accumulation multiplier by management practice."""
    combined = (reduction_practice + " " + baseline_method).lower()
    for key, val in PRACTICE_SOC_FACTORS.items():
        if key in combined:
            return val
    return PRACTICE_SOC_FACTORS["default"]


def _classify_obs_source(source_tag: str) -> str:
    """
    Map a satellite_observations.source tag to a canonical provider class:
      'COPERNICUS' | 'BHUVAN' | 'SIMULATED' | 'MANUAL' | 'IMPORTED'
    """
    tag = source_tag.upper()
    if tag in REAL_COPERNICUS_SOURCES:
        return "COPERNICUS"
    if tag in REAL_BHUVAN_SOURCES:
        if tag == "SATELLITE_MANUAL":
            return "MANUAL"
        if tag == "SATELLITE_IMPORTED":
            return "IMPORTED"
        return "BHUVAN"
    return "SIMULATED"


def _best_obs_provider(source_tags: List[str]) -> str:
    """
    Given a list of source tags on observations used, return the best provider class.
    Priority: COPERNICUS > BHUVAN > MANUAL > IMPORTED > SIMULATED
    """
    classes = [_classify_obs_source(t) for t in source_tags]
    for cls in ("COPERNICUS", "BHUVAN", "MANUAL", "IMPORTED", "SIMULATED"):
        if cls in classes:
            return cls
    return "SIMULATED"


def _provider_conf_for_obs(source_tags: List[str]) -> float:
    """Observation-layer provider confidence based on best available source."""
    best = _best_obs_provider(source_tags)
    mapping = {
        "COPERNICUS": PROVIDER_CONFIDENCE["COPERNICUS"],
        "BHUVAN":     PROVIDER_CONFIDENCE["BHUVAN"],
        "MANUAL":     PROVIDER_CONFIDENCE["SATELLITE_MANUAL"],
        "IMPORTED":   PROVIDER_CONFIDENCE["SATELLITE_IMPORTED"],
        "SIMULATED":  PROVIDER_CONFIDENCE["SATELLITE_SIMULATED"],
    }
    return mapping.get(best, 0.45)


def _ndvi_list_to_soc_gain(
    ndvi_values: List[float],
    crop_factor: float,
    practice_factor: float,
    crop_duration_days: int,
) -> float:
    """
    Derive Δ%SOC for one season from a list of NDVI values.

    Formula:
        mean_ndvi_above_threshold = max(0, mean(NDVI) - NDVI_BASELINE_THRESHOLD)
        duration_fraction         = crop_duration_days / 120   (120-day ref season)
        Δ%SOC = α × mean_ndvi_above_threshold × duration_fraction
                  × crop_factor × practice_factor

    Returns 0.0 if mean NDVI ≤ threshold (no net SOC gain expected).
    """
    if not ndvi_values:
        return 0.0

    mean_ndvi = statistics.mean(ndvi_values)
    ndvi_above = max(0.0, mean_ndvi - NDVI_BASELINE_THRESHOLD)
    if ndvi_above <= 0:
        return 0.0

    duration_fraction = max(0.1, min(2.0, crop_duration_days / 120.0))
    delta_soc = (
        NDVI_SOC_ALPHA
        * ndvi_above
        * duration_fraction
        * crop_factor
        * practice_factor
    )
    return round(delta_soc, 4)


def _soc_tonnes_co2e_credits(
    delta_soc_percent: float,
    land_area_acres: float,
) -> tuple[float, float, int]:
    """
    Convert Δ%SOC → (soc_tonnes, co2e_tonnes, credits) for a given farm area.

    land_area_acres is converted to hectares (1 acre = 0.404686 ha).

    Formula:
        soc_t = (Δ%SOC / 100) × soil_mass_t_ha × area_ha
        co2e  = soc_t × C_TO_CO2E
        credits = floor(co2e)
    """
    area_ha = land_area_acres * 0.404686
    soc_tonnes = (delta_soc_percent / 100.0) * SOIL_MASS_T_PER_HA * area_ha
    co2e = soc_tonnes * C_TO_CO2E
    credits = math.floor(co2e)
    return round(soc_tonnes, 4), round(co2e, 4), credits


def _build_recommendations(
    baseline_source: str,
    n_sat_obs: int,
    satellite_provider: str,
    crop_cycle_found: bool,
) -> List[str]:
    """
    Produce actionable recommendations to improve confidence.
    """
    recs: List[str] = []
    if baseline_source == "ESTIMATED":
        recs.append("Upload a lab SOC measurement to replace the fallback baseline and raise confidence to 95%.")
    elif baseline_source == "MANUAL":
        recs.append("Provide a lab-certified SOC test to further improve baseline accuracy.")
    if n_sat_obs < MIN_SATELLITE_OBS:
        recs.append(
            f"Add more satellite observations (currently {n_sat_obs}; "
            f"minimum {MIN_SATELLITE_OBS} recommended for reliable NDVI-based estimation)."
        )
    if satellite_provider == "SIMULATED":
        recs.append(
            "Connect real satellite provider (Copernicus or Bhuvan) to replace simulated observations."
        )
    if not crop_cycle_found:
        recs.append("Register a crop cycle to enable season-specific SOC estimation.")
    if n_sat_obs > 0 and n_sat_obs < 10:
        recs.append("Increase observation history across multiple growing seasons for a stronger confidence score.")
    recs.append("Verify farm boundary accuracy — incorrect area affects SOC tonnage calculations.")
    return recs


def estimate_soc(
    *,
    land_area_acres: float,
    soil_type: str,
    crop_type: str,
    reduction_practice: str,
    baseline_method: str,
    crop_start_date: Optional[date],
    crop_end_date: Optional[date],
    soc_measurements: Sequence[Any],          # SOCMeasurement ORM objects
    satellite_observations: Sequence[Any],    # SatelliteObservation ORM objects
) -> SOCEstimate:
    """
    Main SOC estimation function.  All parameters come from existing platform data.

    Parameters
    ----------
    land_area_acres       : farm.land_area_acres
    soil_type             : farm.soil_type
    crop_type             : crop_cycle.crop_type
    reduction_practice    : crop_cycle.reduction_practice
    baseline_method       : crop_cycle.baseline_method
    crop_start_date       : crop_cycle.start_date
    crop_end_date         : crop_cycle.end_date (may be None for active cycles)
    soc_measurements      : filtered list of SOCMeasurement for this farm/cycle
    satellite_observations: filtered list of SatelliteObservation for this farm/cycle

    Returns
    -------
    SOCEstimate dataclass with all calculation details and methodology notes.
    """
    sources_detail: List[str] = []
    methodology_parts: List[str] = []
    area_ha = round(land_area_acres * 0.404686, 4)

    # ── Step 1: Resolve baseline %SOC ────────────────────────────────────────
    baseline_soc: Optional[float] = None
    baseline_source: str = "ESTIMATED"
    baseline_confidence: float = 0.25

    lab_measurements    = [m for m in soc_measurements if m.soc_source == "LAB"]
    manual_measurements = [m for m in soc_measurements if m.soc_source == "MANUAL"]
    bhuvan_measurements = [m for m in soc_measurements if m.soc_source == "BHUVAN"]
    copernicus_measurements = [m for m in soc_measurements if m.soc_source == "COPERNICUS"]

    if lab_measurements:
        lab_sorted = sorted(lab_measurements, key=lambda m: m.created_at, reverse=True)
        baseline_soc = lab_sorted[0].soc_percent
        baseline_source = "LAB"
        baseline_confidence = PROVIDER_CONFIDENCE["LAB"]
        sources_detail.append(f"LAB(id={lab_sorted[0].id},{baseline_soc:.3f}%)")
        methodology_parts.append(
            f"Baseline %SOC from lab measurement id={lab_sorted[0].id} "
            f"({baseline_soc:.3f}%). Confidence: {baseline_confidence}."
        )
    elif manual_measurements:
        manual_sorted = sorted(manual_measurements, key=lambda m: m.created_at, reverse=True)
        baseline_soc = manual_sorted[0].soc_percent
        baseline_source = "MANUAL"
        baseline_confidence = PROVIDER_CONFIDENCE["MANUAL"]
        sources_detail.append(f"MANUAL(id={manual_sorted[0].id},{baseline_soc:.3f}%)")
        methodology_parts.append(
            f"Baseline %SOC from manual entry id={manual_sorted[0].id} "
            f"({baseline_soc:.3f}%). Confidence: {baseline_confidence}."
        )
    elif bhuvan_measurements:
        bhuvan_sorted = sorted(bhuvan_measurements, key=lambda m: m.created_at, reverse=True)
        baseline_soc = bhuvan_sorted[0].soc_percent
        baseline_source = "BHUVAN"
        baseline_confidence = PROVIDER_CONFIDENCE["BHUVAN"]
        sources_detail.append(f"BHUVAN(id={bhuvan_sorted[0].id},{baseline_soc:.3f}%)")
        methodology_parts.append(
            f"Baseline %SOC from Bhuvan/NRSC soil layer id={bhuvan_sorted[0].id} "
            f"({baseline_soc:.3f}%). Confidence: {baseline_confidence}."
        )
    elif copernicus_measurements:
        cop_sorted = sorted(copernicus_measurements, key=lambda m: m.created_at, reverse=True)
        baseline_soc = cop_sorted[0].soc_percent
        baseline_source = "COPERNICUS"
        baseline_confidence = PROVIDER_CONFIDENCE["COPERNICUS"]
        sources_detail.append(f"COPERNICUS(id={cop_sorted[0].id},{baseline_soc:.3f}%)")
        methodology_parts.append(
            f"Baseline %SOC from Copernicus observation id={cop_sorted[0].id} "
            f"({baseline_soc:.3f}%). Confidence: {baseline_confidence}."
        )
    else:
        fallback_val = _soil_type_to_fallback(soil_type)
        baseline_soc = fallback_val
        baseline_source = "ESTIMATED"
        baseline_confidence = PROVIDER_CONFIDENCE["ESTIMATED"]
        sources_detail.append(f"ESTIMATED(soil_type={soil_type},{baseline_soc:.3f}%)")
        methodology_parts.append(
            f"Baseline %SOC estimated from soil type '{soil_type}' → "
            f"{baseline_soc:.3f}% (Tamil Nadu / South Indian district-level fallback). "
            f"LAB or MANUAL measurement recommended for higher confidence."
        )

    # ── Step 2: Gather NDVI series from satellite observations ────────────────
    ndvi_values: List[float] = []
    ndwi_values: List[float] = []
    satellite_source_tags: List[str] = []
    obs_dates: List[str] = []

    for obs in satellite_observations:
        ndvi = getattr(obs, "ndvi", None)
        ndwi = getattr(obs, "ndwi", None)
        if ndvi is not None:
            ndvi_values.append(float(ndvi))
        if ndwi is not None:
            ndwi_values.append(float(ndwi))
        # Use .value to get the clean string for (str, enum.Enum) members.
        # Python 3.12+ changed str(StrEnum) to return "ClassName.member" which
        # breaks our source-tag comparisons.  .value always gives the raw string.
        src_raw = getattr(obs, "source", "SATELLITE_SIMULATED")
        src = src_raw.value if hasattr(src_raw, "value") else str(src_raw)
        if src not in satellite_source_tags:
            satellite_source_tags.append(src)
        obs_date = getattr(obs, "observation_date", None)
        if obs_date:
            obs_dates.append(str(obs_date))

    # ── Step 3: Determine provider class & confidence ─────────────────────────
    satellite_provider = _best_obs_provider(satellite_source_tags) if satellite_source_tags else "SIMULATED"
    provider_confidence = _provider_conf_for_obs(satellite_source_tags) if satellite_source_tags else 0.0

    # ── Step 4: Estimate Δ%SOC ────────────────────────────────────────────────
    cf  = _crop_factor(crop_type)
    pf  = _practice_factor(reduction_practice, baseline_method)

    crop_duration_days = 120  # default
    if crop_start_date:
        end = crop_end_date or date.today()
        crop_duration_days = max(1, (end - crop_start_date).days)

    sat_confidence: float = 0.0
    delta_soc: float = 0.0
    mean_ndvi_val: Optional[float] = None

    if len(ndvi_values) >= MIN_SATELLITE_OBS:
        delta_soc = _ndvi_list_to_soc_gain(ndvi_values, cf, pf, crop_duration_days)
        mean_ndvi_val = round(statistics.mean(ndvi_values), 4)
        # Base observation confidence scales with count (35% + 5% per obs, cap 70%)
        obs_confidence = min(0.70, 0.35 + 0.05 * len(ndvi_values))
        # Weight by provider quality
        sat_confidence = round(obs_confidence * provider_confidence / 0.85, 3)
        sat_confidence = min(0.85, sat_confidence)
        sources_detail += satellite_source_tags or ["SATELLITE_SIMULATED"]
        methodology_parts.append(
            f"Δ%SOC estimated from {len(ndvi_values)} satellite NDVI observations "
            f"(provider: {satellite_provider}). "
            f"mean(NDVI)={mean_ndvi_val:.4f}; "
            f"threshold={NDVI_BASELINE_THRESHOLD}; α={NDVI_SOC_ALPHA}; "
            f"crop_factor={cf}; practice_factor={pf}; "
            f"duration={crop_duration_days} days → Δ%SOC={delta_soc:.4f}."
        )
    elif ndvi_values:
        delta_soc = _ndvi_list_to_soc_gain(ndvi_values, cf, pf, crop_duration_days)
        mean_ndvi_val = round(statistics.mean(ndvi_values), 4)
        sat_confidence = round(0.30 * provider_confidence / 0.85, 3)
        sources_detail += satellite_source_tags or ["SATELLITE_SIMULATED"]
        methodology_parts.append(
            f"Δ%SOC estimated from {len(ndvi_values)} satellite observation(s) "
            f"(fewer than minimum {MIN_SATELLITE_OBS} recommended). "
            f"Δ%SOC={delta_soc:.4f}. Low confidence — add more observations."
        )
    else:
        delta_soc = round(0.04 * cf * pf * (crop_duration_days / 120.0), 4)
        sat_confidence = 0.20
        methodology_parts.append(
            f"No satellite NDVI data available. Δ%SOC estimated as 0.04% × "
            f"crop_factor({cf}) × practice_factor({pf}) × duration_fraction "
            f"= {delta_soc:.4f}%. Minimum confidence — add satellite observations."
        )

    # ── Step 5: Compute current SOC ───────────────────────────────────────────
    current_soc = round(baseline_soc + delta_soc, 4)

    # ── Step 6: Convert to mass, CO₂e, credits ────────────────────────────────
    soc_tonnes, co2e_tonnes, soc_credits = _soc_tonnes_co2e_credits(
        delta_soc, land_area_acres
    )

    # ── Step 7: Combined confidence score ────────────────────────────────────
    # Weighted average: baseline confidence × 0.5 + sat/obs confidence × 0.5
    combined_confidence = round(baseline_confidence * 0.5 + sat_confidence * 0.5, 3)

    # ── Step 8: Determine primary source and source label ────────────────────
    if baseline_source in ("LAB", "MANUAL", "BHUVAN", "COPERNICUS"):
        primary_source = baseline_source
    elif len(ndvi_values) >= MIN_SATELLITE_OBS:
        # Map to canonical provider name for primary source
        primary_source = satellite_provider
        if satellite_provider == "COPERNICUS" and satellite_source_tags:
            # Use the exact tag for label lookup
            primary_source = satellite_source_tags[0]
    else:
        primary_source = "ESTIMATED"

    source_label = _SOURCE_LABELS.get(primary_source, f"Derived from {primary_source}")

    # Append confidence reason to source_label
    if primary_source in ("LAB", "MANUAL"):
        confidence_reason = "direct soil measurement"
    elif satellite_provider == "COPERNICUS":
        confidence_reason = "real Copernicus satellite observations"
    elif satellite_provider == "BHUVAN":
        confidence_reason = "Bhuvan/NRSC satellite observations"
    elif satellite_provider == "SIMULATED":
        confidence_reason = "simulated satellite data — connect real provider for higher accuracy"
    else:
        confidence_reason = "fallback estimation model"

    # ── Step 9: Confidence breakdown ─────────────────────────────────────────
    confidence_breakdown: Dict[str, Any] = {
        "baseline_source":          baseline_source,
        "baseline_confidence":      round(baseline_confidence * 100),
        "observation_source":       satellite_provider if ndvi_values else "NO_DATA",
        "observation_confidence":   round(sat_confidence * 100),
        "provider_confidence":      round(provider_confidence * 100),
        "crop_cycle_confidence":    round(min(1.0, crop_duration_days / 120.0) * 70),
        "final_confidence":         round(combined_confidence * 100),
        "reason": (
            f"Confidence is based on {confidence_reason}. "
            f"Baseline from {baseline_source} ({round(baseline_confidence*100)}%). "
            f"Observations from {satellite_provider} ({len(ndvi_values)} NDVI readings). "
            f"Combined: {round(combined_confidence * 100)}%."
        ),
    }

    # ── Step 10: Diagnostics ─────────────────────────────────────────────────
    diagnostics = SOCDiagnostics(
        provider_used=satellite_provider,
        observation_count=len(ndvi_values),
        ndvi_average=mean_ndvi_val,
        farm_area_ha=area_ha,
        bulk_density=BULK_DENSITY_G_CM3,
        soil_depth_cm=SAMPLING_DEPTH_M * 100,
        observation_dates=obs_dates[:20],     # cap to 20 for response size
        baseline_soc_source=baseline_source,
        calculation_version="v1",
    )

    # ── Step 11: Recommendations ─────────────────────────────────────────────
    recommendations = _build_recommendations(
        baseline_source=baseline_source,
        n_sat_obs=len(ndvi_values),
        satellite_provider=satellite_provider,
        crop_cycle_found=True,
    )

    # ── Methodology record ────────────────────────────────────────────────────
    methodology_parts.append(
        f"SOC mass formula: Δ%SOC/100 × {SOIL_MASS_T_PER_HA} t/ha × area_ha. "
        f"area={land_area_acres:.2f} acres = {area_ha:.3f} ha. "
        f"soc_tonnes={soc_tonnes:.4f}. "
        f"CO₂e = soc_tonnes × {C_TO_CO2E:.4f} = {co2e_tonnes:.4f} tCO₂e. "
        f"soc_credits = floor({co2e_tonnes:.4f}) = {soc_credits}. "
        f"INFORMATIONAL ONLY — not mintable in Phase 12.5."
    )
    methodology_notes = " | ".join(methodology_parts)

    return SOCEstimate(
        baseline_soc_percent=round(baseline_soc, 4),
        current_soc_percent=round(current_soc, 4),
        soc_gain_percent=round(delta_soc, 4),
        estimated_soc_tonnes=soc_tonnes,
        soc_co2e_tonnes=co2e_tonnes,
        soc_credits=soc_credits,
        confidence_score=combined_confidence,
        source_used=primary_source,
        sources_detail=sources_detail,
        methodology_notes=methodology_notes,
        source_label=source_label,
        confidence_breakdown=confidence_breakdown,
        diagnostics=diagnostics,
        recommendations=recommendations,
    )
