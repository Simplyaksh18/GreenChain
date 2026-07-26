import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database import Base


class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Recommendation(str, enum.Enum):
    APPROVE = "APPROVE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    REJECT = "REJECT"


class VerificationRequest(Base):
    __tablename__ = "verification_requests"

    id = Column(Integer, primary_key=True, index=True)
    carbon_report_id = Column(Integer, ForeignKey("carbon_reports.id"), nullable=False, index=True)
    verifier_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    status = Column(
        SAEnum(VerificationStatus),
        default=VerificationStatus.PENDING,
        nullable=False,
    )
    remarks = Column(String(1024), nullable=True)
    risk_score = Column(Float, default=0.0, nullable=False)
    risk_level = Column(SAEnum(RiskLevel), nullable=False)
    recommendation = Column(SAEnum(Recommendation), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    carbon_report = relationship("CarbonReport", back_populates="verification_requests")
    verifier = relationship("User", back_populates="verification_requests", foreign_keys=[verifier_id])
