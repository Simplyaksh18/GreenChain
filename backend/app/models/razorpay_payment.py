"""
RazorpayPayment — Phase 17: Razorpay Checkout Demo.

Tracks every Razorpay Checkout order created through GreenChain.
Supports two purposes:
  - FARMER_PAYOUT       → links to payouts.id
  - MARKETPLACE_ORDER   → links to marketplace_orders.id

reference_id is NOT a DB FK (polymorphic reference) — validated in the router.

After verify succeeds:
  - status         → COMPLETED
  - razorpay_payment_id set
  - signature_verified = True
  - linked record (payout or marketplace_order) updated accordingly

SECURITY NOTES:
  - RAZORPAY_KEY_SECRET is never stored here.
  - razorpay_signature stored for audit trail only (not a secret).
  - completed_at is set when verification succeeds.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Enum as SAEnum, ForeignKey

from app.database import Base


class RazorpayPaymentPurpose(str, enum.Enum):
    FARMER_PAYOUT     = "FARMER_PAYOUT"
    MARKETPLACE_ORDER = "MARKETPLACE_ORDER"


class RazorpayPaymentStatus(str, enum.Enum):
    CREATED   = "CREATED"     # order created, awaiting user payment
    COMPLETED = "COMPLETED"   # signature verified, ledger updated
    FAILED    = "FAILED"      # verification failed or payment rejected


class RazorpayPayment(Base):
    __tablename__ = "razorpay_payments"

    id                   = Column(Integer, primary_key=True, index=True)
    purpose              = Column(SAEnum(RazorpayPaymentPurpose), nullable=False)
    reference_id         = Column(Integer, nullable=False, index=True)  # polymorphic — not a FK
    razorpay_order_id    = Column(String(100), nullable=False, unique=True, index=True)
    razorpay_payment_id  = Column(String(100), nullable=True)   # set on successful verification
    # Signature stored for audit — not used after verification
    razorpay_signature   = Column(String(500), nullable=True)
    signature_verified   = Column(Boolean, nullable=False, default=False)
    amount_paise         = Column(Integer, nullable=False)       # Razorpay order amount in paise
    currency             = Column(String(10), nullable=False, default="INR")
    status               = Column(
        SAEnum(RazorpayPaymentStatus),
        nullable=False,
        default=RazorpayPaymentStatus.CREATED,
    )
    failure_reason       = Column(String(500), nullable=True)
    initiated_by         = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at           = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at         = Column(DateTime(timezone=True), nullable=True)
