"""
DroneObservation model — Phase 7.

Captures ground-truth vegetation cover, standing water, and anomaly score
from drone surveys linked to a farm and crop cycle.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship

from app.database import Base


class DroneSource(str, enum.Enum):
    DRONE_SIMULATED = "DRONE_SIMULATED"
    DRONE_MANUAL = "DRONE_MANUAL"
    DRONE_IMPORTED = "DRONE_IMPORTED"


class DroneObservation(Base):
    __tablename__ = "drone_observations"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    crop_cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=True, index=True)

    observation_date = Column(Date, nullable=False)

    vegetation_cover_percent = Column(Float, nullable=False)   # 0–100
    standing_water_percent = Column(Float, nullable=False)     # 0–100
    anomaly_score = Column(Float, nullable=False, default=0.0) # 0–100

    # Optional reference to a stored image (path, URL, or object key)
    image_reference = Column(String(500), nullable=True)

    source = Column(
        # native_enum=False: store as VARCHAR, not a PostgreSQL native enum type.
        # Migration 010 added this column as String(20); keeping native_enum=False
        # ensures SQLAlchemy never emits ::dronesource casts, which would fail
        # because the 'dronesource' pg_type was never created in the database.
        SAEnum(DroneSource, native_enum=False),
        nullable=False,
        default=DroneSource.DRONE_SIMULATED,
        server_default="DRONE_SIMULATED",
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    farm = relationship("Farm", back_populates="drone_observations")
    crop_cycle = relationship("CropCycle", back_populates="drone_observations")
