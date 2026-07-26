"""
SOC (Soil Organic Carbon) models — Phase 12.5

Two tables:
  soc_measurements — lab / manual / satellite-derived SOC % readings
  soc_reports      — calculated SOC estimates and credit figures

SOC credits are informational only.  They must NOT flow through the minting,
custodial balance, payout, or registry submission pipelines.
Only methane credits are mintable in Phase 12.5.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, Float, String, Text, DateTime,
    ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ── Source enum ────────────────────────────────────────────────────────────────

class SOCSource(str, enum.Enum):
    LAB        = "LAB"        # wet-chemistry / loss-on-ignition lab result
    MANUAL     = "MANUAL"     # manually entered field estimate
    COPERNICUS = "COPERNICUS" # derived from Copernicus normalised scene
    BHUVAN     = "BHUVAN"     # derived from Bhuvan normalised layer
    ESTIMATED  = "ESTIMATED"  # algorithmic fallback using available metadata


# ── SOCMeasurement — individual SOC % data points ─────────────────────────────

class SOCMeasurement(Base):
    """
    One SOC % measurement attached to a farm and optionally a crop cycle.

    soc_percent      : measured or estimated soil organic carbon percentage (0–100)
    soc_source       : data provenance (LAB | MANUAL | COPERNICUS | BHUVAN | ESTIMATED)
    confidence_score : 0.0–1.0; higher = more reliable
    notes            : free-text provenance, method, or caveats
    """
    __tablename__ = "soc_measurements"

    id            = Column(Integer, primary_key=True, index=True)
    farm_id       = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    crop_cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=True, index=True)

    soc_percent      = Column(Float, nullable=False)
    soc_source       = Column(SAEnum(SOCSource, native_enum=False), nullable=False)
    confidence_score = Column(Float, nullable=False, default=1.0)
    notes            = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    farm       = relationship("Farm", back_populates="soc_measurements")
    crop_cycle = relationship("CropCycle", back_populates="soc_measurements")


# ── SOCReport — calculated SOC estimate for one crop cycle ────────────────────

class SOCReport(Base):
    """
    Calculated SOC estimate for a farm/crop-cycle pair.

    baseline_soc    : SOC % at crop-cycle start (from measurement priority chain)
    current_soc     : SOC % at end of cycle (observed or estimated)
    soc_gain        : Δ%SOC = current − baseline
    soc_co2e        : tCO₂e sequestered this cycle
    soc_credits     : integer credits (informational only — NOT mintable)
    confidence_score: propagated from source data
    sources_used    : comma-separated list of SOCSource values used
    methodology     : free-text formula/assumption record for auditors
    """
    __tablename__ = "soc_reports"

    id            = Column(Integer, primary_key=True, index=True)
    farm_id       = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    crop_cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=False, index=True)

    baseline_soc     = Column(Float, nullable=False)
    current_soc      = Column(Float, nullable=False)
    soc_gain         = Column(Float, nullable=False)
    soc_co2e         = Column(Float, nullable=False)   # tonnes CO₂e
    soc_credits      = Column(Integer, nullable=False)  # informational only

    confidence_score = Column(Float, nullable=False, default=0.0)
    sources_used     = Column(String(255), nullable=False, default="ESTIMATED")
    methodology      = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    farm       = relationship("Farm", back_populates="soc_reports")
    crop_cycle = relationship("CropCycle", back_populates="soc_reports")
