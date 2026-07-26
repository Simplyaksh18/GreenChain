"""
Marketplace models — Phase 16: Registry & Marketplace.

Three new tables:
  marketplace_listings    — FPO lists credits for sale
  marketplace_orders      — Buyer expresses interest / orders credits
  retirement_certificates — Immutable record of credit retirement
"""
import enum
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Enum as SAEnum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


# ── Listing ────────────────────────────────────────────────────────────────────

class ListingStatus(str, enum.Enum):
    ACTIVE    = "ACTIVE"
    PAUSED    = "PAUSED"
    SOLD_OUT  = "SOLD_OUT"
    CANCELLED = "CANCELLED"


class MarketplaceListing(Base):
    """
    FPO lists available carbon credits for sale.
    credits_available tracks remaining supply as orders are placed/retired.
    """
    __tablename__ = "marketplace_listings"

    id                      = Column(Integer, primary_key=True, index=True)
    farmer_credit_balance_id = Column(
        Integer, ForeignKey("farmer_credit_balances.id"), nullable=False, index=True
    )
    fpo_id                  = Column(Integer, ForeignKey("fpo_profiles.id"), nullable=False, index=True)
    farmer_id               = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    carbon_token_id         = Column(Integer, ForeignKey("carbon_tokens.id"), nullable=False, index=True)
    credits_listed          = Column(Integer, nullable=False)   # total listed (immutable)
    credits_available       = Column(Integer, nullable=False)   # decreases as orders retire
    price_per_credit        = Column(Integer, nullable=False)   # in paise (INR smallest unit)
    currency                = Column(String(10), nullable=False, default="INR")
    listing_status          = Column(
        SAEnum(ListingStatus, native_enum=False),
        nullable=False,
        default=ListingStatus.ACTIVE,
    )
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

    # Relationships
    credit_balance = relationship("FarmerCreditBalance", foreign_keys=[farmer_credit_balance_id])
    fpo            = relationship("FPOProfile", foreign_keys=[fpo_id])
    farmer         = relationship("User", foreign_keys=[farmer_id])
    carbon_token   = relationship("CarbonToken", foreign_keys=[carbon_token_id])
    orders         = relationship("MarketplaceOrder", back_populates="listing")


# ── Order ──────────────────────────────────────────────────────────────────────

class OrderStatus(str, enum.Enum):
    INTERESTED = "INTERESTED"  # buyer submitted interest
    APPROVED   = "APPROVED"    # FPO approved the order
    REJECTED   = "REJECTED"    # FPO rejected the order
    PAID       = "PAID"        # payment confirmed (manual confirmation for now)
    RETIRED    = "RETIRED"     # credits have been retired


class MarketplaceOrder(Base):
    """
    Buyer order against a marketplace listing.
    Buyers are external — no GreenChain account required to place an order.
    """
    __tablename__ = "marketplace_orders"

    id                  = Column(Integer, primary_key=True, index=True)
    listing_id          = Column(
        Integer, ForeignKey("marketplace_listings.id"), nullable=False, index=True
    )
    buyer_name          = Column(String(255), nullable=False)
    buyer_email         = Column(String(255), nullable=False)
    buyer_organization  = Column(String(255), nullable=True)
    credits_requested   = Column(Integer, nullable=False)
    quoted_amount       = Column(Integer, nullable=False)   # credits_requested × price_per_credit (paise)
    order_status        = Column(
        SAEnum(OrderStatus, native_enum=False),
        nullable=False,
        default=OrderStatus.INTERESTED,
    )
    # Buyer identity (Phase 22B) — populated when authenticated user submits.
    # Left nullable for backfill compatibility with pre-22B orders.
    buyer_user_id       = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at          = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    # Phase 22B — manual/test payment tracking. NOT connected to Razorpay
    # Checkout; RazorpayX remains for FPO→farmer payouts only.
    paid_at             = Column(DateTime(timezone=True), nullable=True)
    paid_by_user_id     = Column(Integer, ForeignKey("users.id"), nullable=True)
    payment_reference   = Column(String(255), nullable=True)
    payment_method      = Column(String(50), nullable=True)  # 'MANUAL_TEST' when set

    # Relationships
    listing     = relationship("MarketplaceListing", back_populates="orders")
    certificate = relationship("RetirementCertificate", back_populates="order", uselist=False)


# ── Retirement Certificate ─────────────────────────────────────────────────────

class RetirementCertificate(Base):
    """
    Immutable retirement record for a completed marketplace order.
    certificate_hash is SHA-256 of (order_id + token_id + buyer_name + credits_retired + timestamp).
    """
    __tablename__ = "retirement_certificates"

    id                 = Column(Integer, primary_key=True, index=True)
    order_id           = Column(
        Integer, ForeignKey("marketplace_orders.id"),
        nullable=False, unique=True, index=True,
    )
    token_id           = Column(
        Integer, ForeignKey("carbon_tokens.id"), nullable=False, index=True
    )
    buyer_name         = Column(String(255), nullable=False)
    credits_retired    = Column(Integer, nullable=False)
    retirement_reason  = Column(String(500), nullable=True, default="Marketplace purchase")
    certificate_hash   = Column(String(64), nullable=False)  # 64-char hex SHA-256
    created_at         = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    order = relationship("MarketplaceOrder", back_populates="certificate")
    token = relationship("CarbonToken", foreign_keys=[token_id])


def compute_certificate_hash(
    order_id: int,
    token_id: int,
    buyer_name: str,
    credits_retired: int,
    created_at_iso: str,
) -> str:
    """
    Deterministic SHA-256 hash for a retirement certificate.
    Used to verify certificate integrity independently of the database.
    """
    payload = json.dumps({
        "order_id": order_id,
        "token_id": token_id,
        "buyer_name": buyer_name,
        "credits_retired": credits_retired,
        "created_at": created_at_iso,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
