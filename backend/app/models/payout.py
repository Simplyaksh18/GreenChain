"""
Payout — Phase 9 Custodial Model.

Records simulated carbon credit payout events from FPO to farmer.
No real payment gateway in MVP; status transitions are manual.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class PayoutStatus(str, enum.Enum):
    INITIATED  = "INITIATED"
    PROCESSING = "PROCESSING"
    COMPLETED  = "COMPLETED"
    FAILED     = "FAILED"
    CANCELLED  = "CANCELLED"


class Payout(Base):
    __tablename__ = "payouts"

    id                = Column(Integer, primary_key=True, index=True)
    farmer_id         = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    fpo_id            = Column(Integer, ForeignKey("fpo_profiles.id"), nullable=False, index=True)
    credit_balance_id = Column(
        Integer, ForeignKey("farmer_credit_balances.id"), nullable=False, index=True
    )
    amount_credits    = Column(Integer, nullable=False)
    price_per_credit  = Column(Integer, nullable=False)     # in smallest currency unit (paise)
    payout_amount     = Column(Integer, nullable=False)     # = amount_credits * price_per_credit
    currency          = Column(String(10), nullable=False, default="INR")
    payout_method     = Column(String(50), nullable=True)
    status            = Column(
        SAEnum(PayoutStatus),
        nullable=False,
        default=PayoutStatus.INITIATED,
    )
    initiated_by      = Column(Integer, ForeignKey("users.id"), nullable=False)
    initiated_at      = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at          = Column(DateTime(timezone=True), nullable=True)
    remarks               = Column(String(500), nullable=True)
    # Phase 10A: idempotency + provider reference for future RazorpayX integration
    idempotency_key       = Column(String(100), nullable=True, unique=True, index=True)
    provider_reference_id = Column(String(200), nullable=True)   # RazorpayX payout_id when live
    completed_by          = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    farmer         = relationship("User", foreign_keys=[farmer_id])
    initiator      = relationship("User", foreign_keys=[initiated_by])
    completer      = relationship("User", foreign_keys=[completed_by])
    fpo            = relationship("FPOProfile", foreign_keys=[fpo_id])
    credit_balance = relationship("FarmerCreditBalance", back_populates="payouts")
