"""
SatelliteObservation model — Phase 7.

Stores NDVI, NDWI, vegetation health, and flood risk from satellite imagery
(simulated or real) linked to a farm and crop cycle.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime,
    ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import relationship

from app.database import Base


class SatelliteSource(str, enum.Enum):
    SATELLITE_SIMULATED = "SATELLITE_SIMULATED"
    SENTINEL_2 = "SENTINEL_2"
    LANDSAT_8 = "LANDSAT_8"
    SATELLITE_MANUAL = "SATELLITE_MANUAL"
    SATELLITE_IMPORTED = "SATELLITE_IMPORTED"


class VegetationHealth(str, enum.Enum):
    POOR = "POOR"
    FAIR = "FAIR"
    GOOD = "GOOD"
    EXCELLENT = "EXCELLENT"


class FloodRisk(str, enum.Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SatelliteObservation(Base):
    __tablename__ = "satellite_observations"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    crop_cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=True, index=True)

    observation_date = Column(Date, nullable=False)

    # Normalised Difference Vegetation Index  –1.0 to +1.0
    ndvi = Column(Float, nullable=False)
    # Normalised Difference Water Index  –1.0 to +1.0
    ndwi = Column(Float, nullable=False)

    # native_enum=False on all enum columns: migration 010 converted satellite
    # columns to VARCHAR; native_enum=False keeps SQLAlchemy consistent with the
    # actual column types and avoids ::typename casts on PostgreSQL.
    vegetation_health = Column(SAEnum(VegetationHealth, native_enum=False), nullable=False)
    flood_risk = Column(SAEnum(FloodRisk, native_enum=False), nullable=False, default=FloodRisk.NONE)
    cloud_cover_percent = Column(Float, nullable=False, default=0.0)

    source = Column(
        SAEnum(SatelliteSource, native_enum=False),
        nullable=False,
        default=SatelliteSource.SATELLITE_SIMULATED,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    farm = relationship("Farm", back_populates="satellite_observations")
    crop_cycle = relationship("CropCycle", back_populates="satellite_observations")
