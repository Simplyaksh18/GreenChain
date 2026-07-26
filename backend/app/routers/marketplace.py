"""
Marketplace — Phase 16 + Phase 22B.

Phase 22B changes (backward-compatible extension of Phase 16 contracts):

  * Listing creation now DECREMENTS FarmerCreditBalance.credits_available.
  * Listing cancellation returns unreserved unretired credits to the farmer
    balance and is BLOCKED while APPROVED or PAID orders reference it.
  * Order approval RESERVES quantity by decrementing
    MarketplaceListing.credits_available and stamping order.status = APPROVED.
    Reservation source of truth = credits_requested + status ∈ {APPROVED, PAID}.
  * Rejecting an APPROVED order RETURNS the reserved quantity to the listing.
  * Rejecting a PAID order is BLOCKED (Admin can still act — see mark_paid).
  * New POST /marketplace/orders/{id}/mark-paid records manual/test payment
    (never a real Razorpay Checkout).
  * Retirement now REQUIRES status = PAID (not APPROVED) and does NOT
    decrement listing.credits_available again — that happened at approval.
  * Self-purchase blocked: seller's FPO account or the seller farmer cannot
    order their own listing.
  * New GET /marketplace/my-orders returns the caller's own orders and
    permits buyer to fetch their own certificate.

RazorpayX is NOT invoked here. It remains the payout channel from FPO to
farmer, not buyer checkout.

Endpoints:
  POST   /marketplace/listings                    FPO
  GET    /marketplace/listings                    authenticated (any role)
  GET    /marketplace/listings/{id}               authenticated (any role)
  GET    /marketplace/listings/{id}/orders        FPO (owner) / ADMIN
  PATCH  /marketplace/listings/{id}               FPO (owner)
  POST   /marketplace/listings/{id}/cancel        FPO (owner)

  POST   /marketplace/orders                      authenticated buyer
  GET    /marketplace/orders                      FPO / ADMIN
  GET    /marketplace/orders/{id}                 FPO owner / ADMIN / order buyer
  POST   /marketplace/orders/{id}/approve         FPO (owner)
  POST   /marketplace/orders/{id}/reject          FPO (owner)
  POST   /marketplace/orders/{id}/mark-paid       FPO (owner) / ADMIN     [22B new]
  POST   /marketplace/orders/{id}/retire          FPO (owner) / ADMIN
  GET    /marketplace/orders/{id}/certificate     order buyer / FPO / ADMIN

  GET    /marketplace/my-orders                   authenticated (self)    [22B new]
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.carbon_token import CarbonToken
from app.models.farmer_credit_balance import FarmerCreditBalance, CreditBalanceStatus
from app.models.marketplace import (
    MarketplaceListing, ListingStatus,
    MarketplaceOrder, OrderStatus,
    RetirementCertificate, compute_certificate_hash,
)
from app.models.blockchain_transaction import (
    BlockchainTransaction, ActionType, MOCK_NETWORK, MOCK_CONTRACT_ADDRESS,
)

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])

_PAYMENT_METHOD_MANUAL = "MANUAL_TEST"
_RESERVED_STATUSES = (OrderStatus.APPROVED, OrderStatus.PAID)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fpo_profile_or_403(user: User, db: Session) -> FPOProfile:
    if user.role != UserRole.FPO:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FPO only")
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")
    return profile


def _fpo_profile_for(user: User, db: Session) -> Optional[FPOProfile]:
    """Return the caller's FPO profile if they are an FPO, else None."""
    if user.role != UserRole.FPO:
        return None
    return db.query(FPOProfile).filter(FPOProfile.user_id == user.id).first()


def _get_listing_or_404(listing_id: int, db: Session) -> MarketplaceListing:
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return listing


def _get_order_or_404(order_id: int, db: Session) -> MarketplaceOrder:
    order = db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def _listing_response(listing: MarketplaceListing) -> dict:
    return {
        "id": listing.id,
        "farmer_credit_balance_id": listing.farmer_credit_balance_id,
        "fpo_id": listing.fpo_id,
        "farmer_id": listing.farmer_id,
        "carbon_token_id": listing.carbon_token_id,
        "credits_listed": listing.credits_listed,
        "credits_available": listing.credits_available,
        "price_per_credit": listing.price_per_credit,
        "currency": listing.currency,
        "listing_status": listing.listing_status,
        "created_at": listing.created_at.isoformat() if listing.created_at else None,
        "updated_at": listing.updated_at.isoformat() if listing.updated_at else None,
    }


def _order_response(order: MarketplaceOrder, include_buyer_email: bool = False) -> dict:
    result = {
        "id": order.id,
        "listing_id": order.listing_id,
        "buyer_name": order.buyer_name,
        "buyer_organization": order.buyer_organization,
        "buyer_user_id": order.buyer_user_id,
        "credits_requested": order.credits_requested,
        "quoted_amount": order.quoted_amount,
        "order_status": order.order_status,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "payment_method": order.payment_method,
        "payment_reference": order.payment_reference,
    }
    if include_buyer_email:
        result["buyer_email"] = order.buyer_email
    return result


def _cert_response(cert: RetirementCertificate) -> dict:
    return {
        "id": cert.id,
        "order_id": cert.order_id,
        "token_id": cert.token_id,
        "buyer_name": cert.buyer_name,
        "credits_retired": cert.credits_retired,
        "retirement_reason": cert.retirement_reason,
        "certificate_hash": cert.certificate_hash,
        "created_at": cert.created_at.isoformat() if cert.created_at else None,
    }


def _lock(query):
    """
    Apply row-level lock if the dialect supports it. On SQLite this is a
    no-op (SQLite serializes writes anyway); on Postgres this issues
    SELECT ... FOR UPDATE.
    """
    try:
        return query.with_for_update()
    except Exception:  # noqa: BLE001
        return query


def _sum_reserved(db: Session, listing_id: int) -> int:
    """Sum credits currently reserved (APPROVED or PAID orders) for a listing."""
    from sqlalchemy import func
    total = (
        db.query(func.coalesce(func.sum(MarketplaceOrder.credits_requested), 0))
        .filter(
            MarketplaceOrder.listing_id == listing_id,
            MarketplaceOrder.order_status.in_(_RESERVED_STATUSES),
        )
        .scalar()
    )
    return int(total or 0)


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CreateListingRequest(BaseModel):
    farmer_credit_balance_id: int
    carbon_token_id: int
    credits_listed: int = Field(ge=1)
    price_per_credit: int = Field(ge=1, description="Price in paise (1 INR = 100 paise)")
    currency: str = "INR"


class UpdateListingRequest(BaseModel):
    price_per_credit: Optional[int] = Field(default=None, ge=1)
    listing_status: Optional[ListingStatus] = None


class CreateOrderRequest(BaseModel):
    listing_id: int
    buyer_name: str = Field(min_length=2, max_length=255)
    buyer_email: str = Field(max_length=255)
    buyer_organization: Optional[str] = Field(default=None, max_length=255)
    credits_requested: int = Field(ge=1)


class ApproveOrderRequest(BaseModel):
    remarks: Optional[str] = None


class RejectOrderRequest(BaseModel):
    remarks: str = Field(min_length=2)


class MarkPaidRequest(BaseModel):
    payment_reference: Optional[str] = Field(default=None, max_length=255)


class RetireOrderRequest(BaseModel):
    retirement_reason: Optional[str] = Field(default="Marketplace purchase", max_length=500)


# ── POST /marketplace/listings ────────────────────────────────────────────────

@router.post("/listings", status_code=status.HTTP_201_CREATED)
def create_listing(
    payload: CreateListingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FPO lists credits. Decrements the underlying FarmerCreditBalance so the
    same credits cannot be re-listed elsewhere.
    """
    profile = _fpo_profile_or_403(current_user, db)

    balance = _lock(
        db.query(FarmerCreditBalance).filter(
            FarmerCreditBalance.id == payload.farmer_credit_balance_id,
            FarmerCreditBalance.fpo_id == profile.id,
        )
    ).first()
    if not balance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credit balance not found or does not belong to your FPO",
        )
    if balance.status not in (CreditBalanceStatus.TOKENIZED, CreditBalanceStatus.EARNED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Balance must be TOKENIZED or EARNED to list. Current status: {balance.status.value}",
        )
    if payload.credits_listed > balance.credits_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot list {payload.credits_listed} credits — "
                f"only {balance.credits_available} unlisted available on this balance."
            ),
        )

    token = db.query(CarbonToken).filter(
        CarbonToken.id == payload.carbon_token_id,
        CarbonToken.fpo_id == profile.id,
    ).first()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found or does not belong to your FPO",
        )

    # Reserve on the balance — this is the key Phase 22B change.
    balance.credits_available -= payload.credits_listed

    listing = MarketplaceListing(
        farmer_credit_balance_id=payload.farmer_credit_balance_id,
        fpo_id=profile.id,
        farmer_id=balance.farmer_id,
        carbon_token_id=payload.carbon_token_id,
        credits_listed=payload.credits_listed,
        credits_available=payload.credits_listed,
        price_per_credit=payload.price_per_credit,
        currency=payload.currency,
        listing_status=ListingStatus.ACTIVE,
    )
    db.add(balance)
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return _listing_response(listing)


# ── GET /marketplace/listings ──────────────────────────────────────────────────

@router.get("/listings")
def list_listings(
    listing_status: Optional[str] = Query(default=None, alias="status"),
    fpo_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List marketplace listings.
      * FPO caller  → sees only own listings.
      * Admin       → sees all (optionally filter by fpo_id).
      * Any other authenticated role (farmer, verifier, buyer) → sees ACTIVE
        listings across all FPOs so buyers can browse.
    """
    q = db.query(MarketplaceListing)

    if current_user.role == UserRole.FPO:
        profile = _fpo_profile_for(current_user, db)
        if profile:
            q = q.filter(MarketplaceListing.fpo_id == profile.id)
    elif current_user.role == UserRole.ADMIN:
        if fpo_id:
            q = q.filter(MarketplaceListing.fpo_id == fpo_id)
    else:
        q = q.filter(MarketplaceListing.listing_status == ListingStatus.ACTIVE)

    if listing_status:
        try:
            q = q.filter(MarketplaceListing.listing_status == ListingStatus(listing_status))
        except ValueError:
            pass

    listings = q.order_by(MarketplaceListing.id.desc()).offset(offset).limit(limit).all()
    return [_listing_response(l) for l in listings]


# ── GET /marketplace/listings/{id} ────────────────────────────────────────────

@router.get("/listings/{listing_id}")
def get_listing(
    listing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = _get_listing_or_404(listing_id, db)
    return _listing_response(listing)


# ── GET /marketplace/listings/{id}/orders ────────────────────────────────────

@router.get("/listings/{listing_id}/orders")
def get_listing_orders(
    listing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Orders for a specific listing. FPO owner + Admin only.
    Always returns [] rather than 404 when there are no orders.
    """
    listing = _get_listing_or_404(listing_id, db)

    if current_user.role == UserRole.FPO:
        profile = _fpo_profile_or_403(current_user, db)
        if listing.fpo_id != profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Listing does not belong to your FPO",
            )
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FPO or Admin only")

    orders = (
        db.query(MarketplaceOrder)
        .filter(MarketplaceOrder.listing_id == listing_id)
        .order_by(MarketplaceOrder.id.desc())
        .all()
    )
    return [_order_response(o, include_buyer_email=True) for o in orders]


# ── PATCH /marketplace/listings/{id} ──────────────────────────────────────────

@router.patch("/listings/{listing_id}")
def update_listing(
    listing_id: int,
    payload: UpdateListingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FPO can update price or pause/resume their listing. No inventory change."""
    profile = _fpo_profile_or_403(current_user, db)
    listing = _get_listing_or_404(listing_id, db)
    if listing.fpo_id != profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Listing does not belong to your FPO")
    if listing.listing_status == ListingStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot update a cancelled listing")

    if payload.price_per_credit is not None:
        listing.price_per_credit = payload.price_per_credit
    if payload.listing_status is not None:
        if payload.listing_status == ListingStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use POST /marketplace/listings/{id}/cancel to cancel",
            )
        if payload.listing_status == ListingStatus.ACTIVE and listing.credits_available <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot resume: no credits available on this listing",
            )
        listing.listing_status = payload.listing_status

    listing.updated_at = datetime.now(timezone.utc)
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return _listing_response(listing)


# ── POST /marketplace/listings/{id}/cancel ────────────────────────────────────

@router.post("/listings/{listing_id}/cancel")
def cancel_listing(
    listing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancel a listing and return unreserved unretired credits to the farmer
    balance. Blocked while any APPROVED or PAID orders exist against it —
    those must be rejected first, or (if PAID) retired.
    """
    profile = _fpo_profile_or_403(current_user, db)
    listing = _lock(
        db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id)
    ).first()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.fpo_id != profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Listing does not belong to your FPO")
    if listing.listing_status == ListingStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Listing already cancelled")

    blocking = db.query(MarketplaceOrder).filter(
        MarketplaceOrder.listing_id == listing_id,
        MarketplaceOrder.order_status.in_(_RESERVED_STATUSES),
    ).count()
    if blocking > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot cancel: listing has APPROVED or PAID orders. Reject or retire them first.",
        )

    # Return the still-available (unreserved, unretired) credits.
    returnable = listing.credits_available
    if returnable > 0:
        balance = _lock(
            db.query(FarmerCreditBalance).filter(
                FarmerCreditBalance.id == listing.farmer_credit_balance_id
            )
        ).first()
        if balance:
            balance.credits_available += returnable
            db.add(balance)

    listing.credits_available = 0
    listing.listing_status = ListingStatus.CANCELLED
    listing.updated_at = datetime.now(timezone.utc)
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return _listing_response(listing)


# ── POST /marketplace/orders ──────────────────────────────────────────────────

@router.post("/orders", status_code=status.HTTP_201_CREATED)
def create_order(
    payload: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Buyer submits an order (INTERESTED). No inventory reservation happens
    here — reservation is at approval time.

    Self-purchase is blocked: the seller FPO account and the seller farmer
    cannot order their own listing.
    """
    listing = _get_listing_or_404(payload.listing_id, db)
    if listing.listing_status != ListingStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Listing is not active (status: {listing.listing_status.value})",
        )

    # Self-purchase guard.
    if current_user.id == listing.farmer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot buy credits from your own farm.",
        )
    seller_profile = db.query(FPOProfile).filter(FPOProfile.id == listing.fpo_id).first()
    if seller_profile and seller_profile.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot buy from your own FPO listing.",
        )

    if payload.credits_requested > listing.credits_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot request {payload.credits_requested} credits — "
                f"only {listing.credits_available} still available on this listing."
            ),
        )

    quoted_amount = payload.credits_requested * listing.price_per_credit

    order = MarketplaceOrder(
        listing_id=payload.listing_id,
        buyer_name=payload.buyer_name,
        buyer_email=payload.buyer_email,
        buyer_organization=payload.buyer_organization,
        buyer_user_id=current_user.id,
        credits_requested=payload.credits_requested,
        quoted_amount=quoted_amount,
        order_status=OrderStatus.INTERESTED,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return _order_response(order, include_buyer_email=True)


# ── GET /marketplace/orders ───────────────────────────────────────────────────

@router.get("/orders")
def list_orders(
    listing_id: Optional[int] = Query(default=None),
    order_status: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FPO / Admin: list orders. FPO sees only their listings' orders."""
    if current_user.role not in (UserRole.FPO, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FPO or Admin only")

    q = db.query(MarketplaceOrder)

    if current_user.role == UserRole.FPO:
        profile = _fpo_profile_for(current_user, db)
        if profile:
            fpo_listing_ids = (
                db.query(MarketplaceListing.id)
                .filter(MarketplaceListing.fpo_id == profile.id)
                .all()
            )
            ids = [r[0] for r in fpo_listing_ids]
            q = q.filter(MarketplaceOrder.listing_id.in_(ids))

    if listing_id:
        q = q.filter(MarketplaceOrder.listing_id == listing_id)
    if order_status:
        try:
            q = q.filter(MarketplaceOrder.order_status == OrderStatus(order_status))
        except ValueError:
            pass

    orders = q.order_by(MarketplaceOrder.id.desc()).offset(offset).limit(limit).all()
    return [_order_response(o, include_buyer_email=True) for o in orders]


# ── GET /marketplace/my-orders (Phase 22B) ────────────────────────────────────

@router.get("/my-orders")
def list_my_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return orders the current authenticated user submitted. Any role may
    call — this is the buyer-side listing.
    """
    orders = (
        db.query(MarketplaceOrder)
        .filter(MarketplaceOrder.buyer_user_id == current_user.id)
        .order_by(MarketplaceOrder.id.desc())
        .all()
    )
    return [_order_response(o, include_buyer_email=True) for o in orders]


# ── GET /marketplace/orders/{id} ──────────────────────────────────────────────

@router.get("/orders/{order_id}")
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _get_order_or_404(order_id, db)

    # Access rules:
    #   - Admin: yes
    #   - Owning FPO: yes
    #   - Buyer (order.buyer_user_id == current_user.id): yes
    if current_user.role == UserRole.ADMIN:
        return _order_response(order, include_buyer_email=True)
    if order.buyer_user_id == current_user.id:
        return _order_response(order, include_buyer_email=True)
    if current_user.role == UserRole.FPO:
        listing = _get_listing_or_404(order.listing_id, db)
        profile = _fpo_profile_for(current_user, db)
        if profile and listing.fpo_id == profile.id:
            return _order_response(order, include_buyer_email=True)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this order")


# ── POST /marketplace/orders/{id}/approve ────────────────────────────────────

@router.post("/orders/{order_id}/approve")
def approve_order(
    order_id: int,
    payload: ApproveOrderRequest = ApproveOrderRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FPO approves an INTERESTED order. Atomically decrements listing.credits_available
    (the reservation). Concurrent approvals cannot oversubscribe because the row
    lock serializes reads.
    """
    profile = _fpo_profile_or_403(current_user, db)

    order = _lock(
        db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id)
    ).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    listing = _lock(
        db.query(MarketplaceListing).filter(MarketplaceListing.id == order.listing_id)
    ).first()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.fpo_id != profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Order does not belong to your FPO")
    if order.order_status != OrderStatus.INTERESTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only approve INTERESTED orders. Current: {order.order_status.value}",
        )
    if listing.listing_status != ListingStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot approve on a {listing.listing_status.value} listing",
        )
    if order.credits_requested > listing.credits_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Insufficient inventory — only {listing.credits_available} credits "
                f"remain on this listing (requested {order.credits_requested})."
            ),
        )

    # Reserve.
    listing.credits_available -= order.credits_requested
    if listing.credits_available == 0:
        listing.listing_status = ListingStatus.SOLD_OUT
    listing.updated_at = datetime.now(timezone.utc)
    order.order_status = OrderStatus.APPROVED

    db.add(listing)
    db.add(order)
    db.commit()
    db.refresh(order)
    return _order_response(order, include_buyer_email=True)


# ── POST /marketplace/orders/{id}/reject ─────────────────────────────────────

@router.post("/orders/{order_id}/reject")
def reject_order(
    order_id: int,
    payload: RejectOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reject an order.
      * INTERESTED → REJECTED (no inventory change)
      * APPROVED → REJECTED (reservation is RELEASED back to listing)
      * PAID     → BLOCKED (400) — payment must be reversed manually first
      * REJECTED / RETIRED → BLOCKED
    """
    profile = _fpo_profile_or_403(current_user, db)

    order = _lock(
        db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id)
    ).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    listing = _lock(
        db.query(MarketplaceListing).filter(MarketplaceListing.id == order.listing_id)
    ).first()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.fpo_id != profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Order does not belong to your FPO")

    if order.order_status == OrderStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot reject a PAID order. Reverse the payment manually first.",
        )
    if order.order_status not in (OrderStatus.INTERESTED, OrderStatus.APPROVED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject order in status {order.order_status.value}",
        )

    if order.order_status == OrderStatus.APPROVED:
        # Release the reservation.
        listing.credits_available += order.credits_requested
        if listing.listing_status == ListingStatus.SOLD_OUT and listing.credits_available > 0:
            listing.listing_status = ListingStatus.ACTIVE
        listing.updated_at = datetime.now(timezone.utc)
        db.add(listing)

    order.order_status = OrderStatus.REJECTED
    db.add(order)
    db.commit()
    db.refresh(order)
    return _order_response(order, include_buyer_email=True)


# ── POST /marketplace/orders/{id}/mark-paid  (Phase 22B) ─────────────────────

@router.post("/orders/{order_id}/mark-paid")
def mark_order_paid(
    order_id: int,
    payload: MarkPaidRequest = MarkPaidRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually mark an APPROVED order as PAID. This is a TEST/MANUAL record,
    NOT a real payment gateway integration. RazorpayX is not touched.

    Idempotent: calling on an already-PAID order returns the same PAID state
    without changing the recorded payment metadata.
    """
    if current_user.role not in (UserRole.FPO, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FPO or Admin only")

    order = _lock(
        db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id)
    ).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    # FPO must own the underlying listing.
    if current_user.role == UserRole.FPO:
        listing = _get_listing_or_404(order.listing_id, db)
        profile = _fpo_profile_for(current_user, db)
        if not profile or listing.fpo_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Order does not belong to your FPO")

    if order.order_status == OrderStatus.PAID:
        # Idempotent success.
        return {
            **_order_response(order, include_buyer_email=True),
            "message": "Payment recorded in test/manual mode",
            "idempotent": True,
        }
    if order.order_status != OrderStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only APPROVED orders can be marked paid. Current: {order.order_status.value}",
        )

    order.order_status = OrderStatus.PAID
    order.paid_at = datetime.now(timezone.utc)
    order.paid_by_user_id = current_user.id
    order.payment_method = _PAYMENT_METHOD_MANUAL
    order.payment_reference = payload.payment_reference
    db.add(order)
    db.commit()
    db.refresh(order)
    return {
        **_order_response(order, include_buyer_email=True),
        "message": "Payment recorded in test/manual mode",
        "idempotent": False,
    }


# ── POST /marketplace/orders/{id}/retire ─────────────────────────────────────

@router.post("/orders/{order_id}/retire", status_code=status.HTTP_201_CREATED)
def retire_order(
    order_id: int,
    payload: RetireOrderRequest = RetireOrderRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retire the reserved credits for a PAID order.

    Reservation subtraction happened at approval — we do NOT decrement
    listing.credits_available again here. We do:
      * create RetirementCertificate
      * create BlockchainTransaction (TOKEN_RETIRE mock)
      * transition order INTERESTED→…→RETIRED

    Attempting to retire a non-PAID order is BLOCKED (Phase 22B change —
    previously APPROVED was accepted).
    """
    if current_user.role not in (UserRole.FPO, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FPO or Admin only")

    order = _lock(
        db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id)
    ).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    listing = _lock(
        db.query(MarketplaceListing).filter(MarketplaceListing.id == order.listing_id)
    ).first()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    if current_user.role == UserRole.FPO:
        profile = _fpo_profile_for(current_user, db)
        if not profile or listing.fpo_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Order does not belong to your FPO")

    if order.order_status != OrderStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order must be PAID to retire. Current: {order.order_status.value}",
        )
    if order.certificate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This order has already been retired.",
        )

    now = datetime.now(timezone.utc)
    cert_hash = compute_certificate_hash(
        order_id=order.id,
        token_id=listing.carbon_token_id,
        buyer_name=order.buyer_name,
        credits_retired=order.credits_requested,
        created_at_iso=now.isoformat(),
    )
    cert = RetirementCertificate(
        order_id=order.id,
        token_id=listing.carbon_token_id,
        buyer_name=order.buyer_name,
        credits_retired=order.credits_requested,
        retirement_reason=payload.retirement_reason,
        certificate_hash=cert_hash,
        created_at=now,
    )
    db.add(cert)

    # NOTE: listing.credits_available is NOT decremented here — the
    # reservation at approval already removed the quantity from the pool.
    # We only update sold-out state if it wasn't already.
    if listing.credits_available == 0 and listing.listing_status != ListingStatus.SOLD_OUT:
        listing.listing_status = ListingStatus.SOLD_OUT
    listing.updated_at = now
    db.add(listing)

    order.order_status = OrderStatus.RETIRED
    db.add(order)

    token = db.query(CarbonToken).filter(CarbonToken.id == listing.carbon_token_id).first()
    if token:
        tx = BlockchainTransaction(
            carbon_report_id=token.carbon_report_id,
            tx_hash=f"0x{cert_hash[:64]}",
            blockchain_network=MOCK_NETWORK,
            contract_address=MOCK_CONTRACT_ADDRESS,
            action_type=ActionType.TOKEN_RETIRE,
            created_at=now,
        )
        db.add(tx)

    db.commit()
    db.refresh(cert)
    return _cert_response(cert)


# ── GET /marketplace/orders/{id}/certificate ─────────────────────────────────

@router.get("/orders/{order_id}/certificate")
def get_retirement_certificate(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Certificate for a retired order. Accessible to:
      * Admin
      * Owning FPO
      * The buyer who submitted the order (order.buyer_user_id == caller)
    """
    order = _get_order_or_404(order_id, db)
    if not order.certificate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No certificate yet — order not retired")

    if current_user.role == UserRole.ADMIN:
        return _cert_response(order.certificate)
    if order.buyer_user_id == current_user.id:
        return _cert_response(order.certificate)
    if current_user.role == UserRole.FPO:
        listing = _get_listing_or_404(order.listing_id, db)
        profile = _fpo_profile_for(current_user, db)
        if profile and listing.fpo_id == profile.id:
            return _cert_response(order.certificate)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this certificate")
