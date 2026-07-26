import enum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Enum as SAEnum, Date, Text,
)
from sqlalchemy.orm import relationship
from app.database import Base


# ─── Farm Status ───────────────────────────────────────────────────────────────

class FarmStatus(str, enum.Enum):
    DRAFT            = "DRAFT"             # newly created, not yet submitted
    PENDING_APPROVAL = "PENDING_APPROVAL"  # farmer has submitted for FPO review
    APPROVED         = "APPROVED"          # FPO has approved
    SUSPENDED        = "SUSPENDED"         # FPO has suspended (not accepting new MRV)
    ARCHIVED         = "ARCHIVED"          # farmer has archived (soft-closed)


# ─── Crop Cycle Status ─────────────────────────────────────────────────────────

class CropCycleStatus(str, enum.Enum):
    PLANNED   = "PLANNED"    # registered but not yet started
    ACTIVE    = "ACTIVE"     # sensors collecting data
    HARVESTED = "HARVESTED"  # crop harvested; MRV window closed
    VERIFIED  = "VERIFIED"   # carbon report verified
    CLOSED    = "CLOSED"     # fully closed; no further changes
    # Legacy values — retained for backward compatibility
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# ─── Farm Model ────────────────────────────────────────────────────────────────

class Farm(Base):
    __tablename__ = "farms"

    id              = Column(Integer, primary_key=True, index=True)
    farmer_id       = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    fpo_id          = Column(Integer, ForeignKey("fpo_profiles.id"), nullable=True, index=True)
    farm_name       = Column(String(255), nullable=False)
    land_area_acres = Column(Float, nullable=False)
    latitude        = Column(Float, nullable=False)
    longitude       = Column(Float, nullable=False)
    village         = Column(String(100), nullable=False)
    district        = Column(String(100), nullable=False)
    state           = Column(String(100), nullable=False)
    soil_type       = Column(String(100), nullable=False)
    water_source    = Column(String(100), nullable=False)

    # Legacy boolean — kept for backward compatibility; synced with farm_status
    is_approved = Column(Boolean, default=False, nullable=False)

    # Phase 11 lifecycle status
    farm_status  = Column(
        SAEnum(FarmStatus, native_enum=False),
        default=FarmStatus.DRAFT,
        server_default="DRAFT",
        nullable=False,
    )
    approved_at    = Column(DateTime(timezone=True), nullable=True)
    approved_by    = Column(Integer, ForeignKey("users.id"), nullable=True)
    archived_at    = Column(DateTime(timezone=True), nullable=True)
    archive_reason = Column(String(500), nullable=True)

    # Phase 11 GIS readiness
    farm_boundary_geojson  = Column(Text, nullable=True)
    boundary_area_hectares = Column(Float, nullable=True)
    boundary_area_acres    = Column(Float, nullable=True)

    # Soft-delete (pre-existing)
    is_deleted = Column(Boolean, default=False, nullable=False, server_default="false")
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    farmer             = relationship("User", back_populates="farms", foreign_keys=[farmer_id])
    approver           = relationship("User", foreign_keys=[approved_by])
    fpo                = relationship("FPOProfile", back_populates="farms", foreign_keys=[fpo_id])
    crop_cycles        = relationship("CropCycle", back_populates="farm", cascade="all, delete-orphan")
    sensor_readings    = relationship("SensorReading", back_populates="farm", cascade="all, delete-orphan")
    evidence_files     = relationship("EvidenceFile", back_populates="farm", cascade="all, delete-orphan")
    carbon_reports     = relationship("CarbonReport", back_populates="farm", cascade="all, delete-orphan")
    satellite_observations = relationship("SatelliteObservation", back_populates="farm", cascade="all, delete-orphan")
    drone_observations = relationship("DroneObservation", back_populates="farm", cascade="all, delete-orphan")
    # Phase 12.5 — SOC (informational only)
    soc_measurements = relationship("SOCMeasurement", back_populates="farm", cascade="all, delete-orphan")
    soc_reports      = relationship("SOCReport",      back_populates="farm", cascade="all, delete-orphan")


# ─── Crop Cycle Model ──────────────────────────────────────────────────────────

class CropCycle(Base):
    __tablename__ = "crop_cycles"

    id                 = Column(Integer, primary_key=True, index=True)
    farm_id            = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    crop_type          = Column(String(100), nullable=False)
    season             = Column(String(100), nullable=False)
    start_date         = Column(Date, nullable=False)
    end_date           = Column(Date, nullable=True)
    baseline_method    = Column(String(255), nullable=False)
    reduction_practice = Column(String(255), nullable=False)
    status             = Column(
        SAEnum(CropCycleStatus, native_enum=False),
        default=CropCycleStatus.ACTIVE,
        server_default="ACTIVE",
        nullable=False,
    )

    # Phase 11 lifecycle fields
    harvest_date   = Column(Date, nullable=True)
    closed_at      = Column(DateTime(timezone=True), nullable=True)
    yield_quantity = Column(Float, nullable=True)
    yield_unit     = Column(String(50), nullable=True)   # e.g. "tonnes", "quintals", "kg"

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    farm                   = relationship("Farm", back_populates="crop_cycles")
    sensor_readings        = relationship("SensorReading", back_populates="crop_cycle", cascade="all, delete-orphan")
    evidence_files         = relationship("EvidenceFile", back_populates="crop_cycle", cascade="all, delete-orphan")
    carbon_reports         = relationship("CarbonReport", back_populates="crop_cycle", cascade="all, delete-orphan")
    satellite_observations = relationship("SatelliteObservation", back_populates="crop_cycle", cascade="all, delete-orphan")
    drone_observations     = relationship("DroneObservation", back_populates="crop_cycle", cascade="all, delete-orphan")
    # Phase 12.5 — SOC (informational only)
    soc_measurements = relationship("SOCMeasurement", back_populates="crop_cycle", cascade="all, delete-orphan")
    soc_reports      = relationship("SOCReport",      back_populates="crop_cycle", cascade="all, delete-orphan")
