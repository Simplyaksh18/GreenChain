"""
FarmerProfile — Phase 9 Custodial Model.

Stores farmer payout / disbursement details.
Farmers never hold blockchain wallet addresses;
credits are tracked as database balances, payouts done via UPI/Bank.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class PayoutMethod(str, enum.Enum):
    UPI           = "UPI"
    BANK_TRANSFER = "BANK_TRANSFER"


class FarmerProfile(Base):
    __tablename__ = "farmer_profiles"

    id                      = Column(Integer, primary_key=True, index=True)
    user_id                 = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    preferred_payout_method = Column(SAEnum(PayoutMethod), nullable=True)
    upi_id                  = Column(String(100), nullable=True)
    bank_account_holder_name= Column(String(255), nullable=True)
    # Stored encrypted/masked; full number never returned via API
    bank_account_number     = Column(String(30), nullable=True)
    ifsc_code               = Column(String(11), nullable=True)
    bank_name               = Column(String(100), nullable=True)  # Phase 10A audit: bank name for display
    # Phase 10A: payout verification fields
    payout_details_verified    = Column(Boolean, nullable=False, default=False)
    payout_details_verified_at = Column(DateTime(timezone=True), nullable=True)
    payout_verification_method = Column(String(50), nullable=True)  # e.g. "FORMAT_CHECK", "PENNY_DROP"
    created_at              = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at              = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="farmer_profile")
