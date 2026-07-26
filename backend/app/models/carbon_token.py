import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class TokenStatus(str, enum.Enum):
    MINTED    = "MINTED"
    RETIRED   = "RETIRED"
    SUSPENDED = "SUSPENDED"


TOKEN_STANDARD = "ERC1155_MOCK"


class CarbonToken(Base):
    __tablename__ = "carbon_tokens"

    id               = Column(Integer, primary_key=True, index=True)
    carbon_report_id = Column(Integer, ForeignKey("carbon_reports.id"), nullable=False, unique=True, index=True)
    farmer_id        = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_id         = Column(String(64), nullable=False, unique=True)
    token_standard   = Column(String(32), nullable=False, default=TOKEN_STANDARD)
    credit_amount    = Column(Integer, nullable=False)
    status           = Column(Enum(TokenStatus), nullable=False, default=TokenStatus.MINTED)
    minted_tx_hash   = Column(String(66), nullable=True)
    minted_at        = Column(DateTime(timezone=True), nullable=True)
    # Phase 9: custodial model fields
    fpo_id                = Column(Integer, ForeignKey("fpo_profiles.id"), nullable=True)
    beneficiary_farmer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    custodial_owner_type  = Column(String(20), nullable=False, default="FPO")
    created_at       = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # relationships
    carbon_report = relationship("CarbonReport", back_populates="carbon_token")
    farmer        = relationship("User", back_populates="carbon_tokens", foreign_keys=[farmer_id])
    fpo           = relationship("FPOProfile", foreign_keys=[fpo_id])
    beneficiary_farmer = relationship("User", foreign_keys=[beneficiary_farmer_id])
