import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, Float, DateTime, ForeignKey,
    Enum as SAEnum, String,
)
from sqlalchemy.orm import relationship
from app.database import Base


class SensorSourceType(str, enum.Enum):
    SIMULATED = "SIMULATED"
    MANUAL = "MANUAL"
    IMPORTED = "IMPORTED"
    HIGH_EMISSION_DEMO = "HIGH_EMISSION_DEMO"   # Demo/test data with engineered methane values


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    crop_cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=False, index=True)
    reading_time = Column(DateTime(timezone=True), nullable=False)
    soil_moisture = Column(Float, nullable=False)          # 0-100
    water_depth_cm = Column(Float, nullable=False)         # 0-30
    temperature_c = Column(Float, nullable=False)          # 15-45
    humidity = Column(Float, nullable=False)               # 20-100
    rainfall_mm = Column(Float, nullable=False)            # 0-100
    estimated_methane = Column(Float, nullable=False)      # kg CH4 / day
    data_quality_score = Column(Float, nullable=False)     # 0-100
    source_type = Column(
        SAEnum(SensorSourceType), default=SensorSourceType.SIMULATED, nullable=False
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    farm = relationship("Farm", back_populates="sensor_readings")
    crop_cycle = relationship("CropCycle", back_populates="sensor_readings")
