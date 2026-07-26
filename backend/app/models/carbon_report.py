import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database import Base


class ReportStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class CarbonReport(Base):
    __tablename__ = "carbon_reports"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    crop_cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=False, index=True)
    baseline_methane_kg = Column(Float, nullable=False)
    current_methane_kg = Column(Float, nullable=False)
    methane_reduction_kg = Column(Float, nullable=False)
    co2e_reduction_tonnes = Column(Float, nullable=False)
    estimated_credits = Column(Integer, nullable=False)
    report_hash = Column(String(64), nullable=False)
    status = Column(SAEnum(ReportStatus), default=ReportStatus.DRAFT, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    farm = relationship("Farm", back_populates="carbon_reports")
    crop_cycle = relationship("CropCycle", back_populates="carbon_reports")
    verification_requests = relationship(
        "VerificationRequest",
        back_populates="carbon_report",
        cascade="all, delete-orphan",
    )
    blockchain_transactions = relationship(
        "BlockchainTransaction",
        back_populates="carbon_report",
        cascade="all, delete-orphan",
    )
    carbon_token = relationship(
        "CarbonToken",
        back_populates="carbon_report",
        uselist=False,
        cascade="all, delete-orphan",
    )
