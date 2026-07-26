"""
FarmerCreditBalance — Phase 9 Custodial Model.

Digital-twin ledger tracking farmer-level carbon credit ownership.

The on-chain token is held by the FPO vault; this table is the authoritative
database record of how many credits belong to which farmer under which FPO.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class CreditBalanceStatus(str, enum.Enum):
    EARNED      = "EARNED"       # Report verified; credits calculated but token not yet minted
    TOKENIZED   = "TOKENIZED"    # Token minted to FPO vault; farmer credits locked
    DISTRIBUTED = "DISTRIBUTED"  # Full payout completed; no available credits remain
    HELD        = "HELD"         # Temporarily on hold (admin action)
    CANCELLED   = "CANCELLED"    # Credits cancelled (e.g. report reversal)


class FarmerCreditBalance(Base):
    __tablename__ = "farmer_credit_balances"

    id                = Column(Integer, primary_key=True, index=True)
    farmer_id         = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    fpo_id            = Column(Integer, ForeignKey("fpo_profiles.id"), nullable=False, index=True)
    carbon_report_id  = Column(
        Integer, ForeignKey("carbon_reports.id"),
        nullable=False, unique=True, index=True,
    )
    carbon_token_id   = Column(Integer, ForeignKey("carbon_tokens.id"), nullable=True)
    credits_earned    = Column(Integer, nullable=False, default=0)
    credits_distributed = Column(Integer, nullable=False, default=0)
    credits_available = Column(Integer, nullable=False, default=0)
    status            = Column(
        SAEnum(CreditBalanceStatus),
        nullable=False,
        default=CreditBalanceStatus.EARNED,
    )
    created_at        = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at        = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    farmer       = relationship("User", foreign_keys=[farmer_id])
    fpo          = relationship("FPOProfile", foreign_keys=[fpo_id])
    carbon_report = relationship("CarbonReport")
    carbon_token  = relationship("CarbonToken", foreign_keys=[carbon_token_id])
    payouts       = relationship("Payout", back_populates="credit_balance")
