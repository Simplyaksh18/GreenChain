"""
Razorpay Checkout router — Phase 17.

POST /payments/razorpay/create-order   — authenticated; FPO for payouts, any role for marketplace
POST /payments/razorpay/verify         — authenticated; verifies HMAC, updates ledger

How it works
────────────
1. Mobile calls create-order → backend creates a Razorpay Order via API → returns order_id + key_id.
2. Mobile opens RazorpayCheckout.open({ key, order_id, amount, ... }).
3. User pays with test card / UPI.
4. Razorpay returns { razorpay_payment_id, razorpay_order_id, razorpay_signature } to mobile.
5. Mobile calls verify → backend verifies HMAC SHA-256 signature server-side.
6. If valid: mark RazorpayPayment.status=COMPLETED, update linked payout/order.
7. If invalid: mark FAILED, do not update ledger.

SECURITY
────────
- RAZORPAY_KEY_SECRET is read from env only, never stored or returned.
- key_id (public test key) is safe to return to mobile.
- razorpay_signature is stored for audit; it is not a secret value.
- create-order validates that the requesting user owns the linked payout/order.
"""
import hashlib
import hmac
import logging
from datetime import datetime, timezone

import razorpay
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.marketplace import MarketplaceOrder, OrderStatus
from app.models.payout import Payout, PayoutStatus
from app.models.razorpay_payment import (
    RazorpayPayment,
    RazorpayPaymentPurpose,
    RazorpayPaymentStatus,
)
from app.models.user import User
from app.models.fpo import FPOProfile
from app.schemas.razorpay_schema import (
    CreateOrderRequest,
    CreateOrderResponse,
    PaymentResponse,
    VerifyPaymentRequest,
)
from app.services.payout_provider import _razorpay_env

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["Payments"])


# ── Razorpay client helper ─────────────────────────────────────────────────────

def _get_razorpay_client() -> razorpay.Client:
    """Return an authenticated Razorpay client. Raises 503 if keys not configured."""
    key_id     = _razorpay_env("RAZORPAY_KEY_ID")
    key_secret = _razorpay_env("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Razorpay not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in environment.",
        )
    return razorpay.Client(auth=(key_id, key_secret))


def _get_key_id() -> str:
    key_id = _razorpay_env("RAZORPAY_KEY_ID")
    if not key_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAZORPAY_KEY_ID not configured.",
        )
    return key_id


# ── POST /payments/razorpay/create-order ─────────────────────────────────────

@router.post(
    "/razorpay/create-order",
    response_model=CreateOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_razorpay_order(
    payload: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Razorpay Order and record it in razorpay_payments.

    Caller passes amount in RUPEES (₹). Backend converts to paise (× 100) for Razorpay.
    Returns order_id and key_id — mobile uses these to open RazorpayCheckout.
    """
    # ── Ownership validation ───────────────────────────────────────────────────
    if payload.purpose == RazorpayPaymentPurpose.FARMER_PAYOUT:
        payout = db.query(Payout).filter(Payout.id == payload.reference_id).first()
        if not payout:
            raise HTTPException(status_code=404, detail="Payout not found.")
        # Must be FPO that owns the payout
        fpo = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
        if not fpo or payout.fpo_id != fpo.id:
            raise HTTPException(status_code=403, detail="You do not own this payout.")
        if payout.status != PayoutStatus.INITIATED:
            raise HTTPException(
                status_code=400,
                detail=f"Payout is in status {payout.status.value}. Only INITIATED payouts can be paid.",
            )
    elif payload.purpose == RazorpayPaymentPurpose.MARKETPLACE_ORDER:
        order = db.query(MarketplaceOrder).filter(MarketplaceOrder.id == payload.reference_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Marketplace order not found.")
        if order.buyer_id != current_user.id:
            raise HTTPException(status_code=403, detail="You do not own this marketplace order.")
        if order.status != OrderStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail=f"Order must be APPROVED before payment. Current status: {order.status.value}.",
            )

    # ── Convert amount: rupees → paise ────────────────────────────────────────
    amount_paise = payload.amount * 100

    # ── Create Razorpay Order ─────────────────────────────────────────────────
    client = _get_razorpay_client()
    receipt = f"gc-{payload.purpose.value[:3].lower()}-{payload.reference_id}"
    try:
        rz_order = client.order.create({
            "amount":   amount_paise,
            "currency": payload.currency,
            "receipt":  receipt,
            "notes": {
                "purpose":      payload.purpose.value,
                "reference_id": str(payload.reference_id),
                "platform":     "GreenChain",
            },
        })
    except Exception as exc:
        logger.error("Razorpay create order failed | reference_id=%s error=%s", payload.reference_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Razorpay order creation failed: {exc}",
        )

    razorpay_order_id = rz_order["id"]
    logger.info(
        "Razorpay order created | purpose=%s reference_id=%s order_id=%s amount_paise=%s",
        payload.purpose.value, payload.reference_id, razorpay_order_id, amount_paise,
    )

    # ── Persist RazorpayPayment record ────────────────────────────────────────
    rz_payment = RazorpayPayment(
        purpose           = payload.purpose,
        reference_id      = payload.reference_id,
        razorpay_order_id = razorpay_order_id,
        amount_paise      = amount_paise,
        currency          = payload.currency,
        status            = RazorpayPaymentStatus.CREATED,
        initiated_by      = current_user.id,
        created_at        = datetime.now(timezone.utc),
    )
    db.add(rz_payment)
    db.commit()
    db.refresh(rz_payment)

    return CreateOrderResponse(
        payment_record_id = rz_payment.id,
        order_id          = razorpay_order_id,
        amount_paise      = amount_paise,
        currency          = payload.currency,
        key_id            = _get_key_id(),
    )


# ── POST /payments/razorpay/verify ────────────────────────────────────────────

@router.post(
    "/razorpay/verify",
    response_model=PaymentResponse,
)
def verify_razorpay_payment(
    payload: VerifyPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify Razorpay payment signature server-side.

    Expected HMAC:
      SHA-256(razorpay_order_id + "|" + razorpay_payment_id, key=RAZORPAY_KEY_SECRET)

    On success:
      - RazorpayPayment.status = COMPLETED
      - Linked payout marked COMPLETED / marketplace order marked PAID

    On failure:
      - RazorpayPayment.status = FAILED
      - Ledger NOT updated
      - 400 returned to mobile
    """
    # ── Load the payment record ───────────────────────────────────────────────
    rz_payment = db.query(RazorpayPayment).filter(
        RazorpayPayment.id == payload.payment_record_id
    ).first()
    if not rz_payment:
        raise HTTPException(status_code=404, detail="Payment record not found.")
    if rz_payment.initiated_by != current_user.id:
        raise HTTPException(status_code=403, detail="You did not initiate this payment.")
    if rz_payment.status != RazorpayPaymentStatus.CREATED:
        raise HTTPException(
            status_code=400,
            detail=f"Payment already in status {rz_payment.status.value}.",
        )

    # ── HMAC signature verification ───────────────────────────────────────────
    key_secret = _razorpay_env("RAZORPAY_KEY_SECRET")
    if not key_secret:
        raise HTTPException(status_code=503, detail="RAZORPAY_KEY_SECRET not configured.")

    msg       = f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}"
    expected  = hmac.new(
        key_secret.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    is_valid  = hmac.compare_digest(expected, payload.razorpay_signature)

    now = datetime.now(timezone.utc)

    if not is_valid:
        # ── Signature mismatch — mark FAILED, do not update ledger ────────────
        logger.warning(
            "Razorpay signature invalid | payment_record_id=%s order_id=%s payment_id=%s",
            rz_payment.id, payload.razorpay_order_id, payload.razorpay_payment_id,
        )
        rz_payment.status         = RazorpayPaymentStatus.FAILED
        rz_payment.failure_reason = "Signature verification failed."
        rz_payment.razorpay_payment_id = payload.razorpay_payment_id
        rz_payment.razorpay_signature  = payload.razorpay_signature
        rz_payment.signature_verified  = False
        db.add(rz_payment)
        db.commit()
        db.refresh(rz_payment)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment signature invalid. Payout not completed.",
        )

    # ── Signature valid — update payment record ───────────────────────────────
    rz_payment.razorpay_payment_id = payload.razorpay_payment_id
    rz_payment.razorpay_signature  = payload.razorpay_signature
    rz_payment.signature_verified  = True
    rz_payment.status              = RazorpayPaymentStatus.COMPLETED
    rz_payment.completed_at        = now
    db.add(rz_payment)

    logger.info(
        "Razorpay signature verified | payment_record_id=%s order_id=%s payment_id=%s purpose=%s reference_id=%s",
        rz_payment.id, payload.razorpay_order_id, payload.razorpay_payment_id,
        rz_payment.purpose.value, rz_payment.reference_id,
    )

    # ── Update linked ledger record ───────────────────────────────────────────
    if rz_payment.purpose == RazorpayPaymentPurpose.FARMER_PAYOUT:
        _complete_payout(db, rz_payment.reference_id, payload.razorpay_payment_id, now)

    elif rz_payment.purpose == RazorpayPaymentPurpose.MARKETPLACE_ORDER:
        _pay_marketplace_order(db, rz_payment.reference_id, payload.razorpay_payment_id, now)

    db.commit()
    db.refresh(rz_payment)
    return rz_payment


# ── Ledger update helpers ─────────────────────────────────────────────────────

def _complete_payout(db: Session, payout_id: int, payment_id: str, now: datetime) -> None:
    """Mark the payout COMPLETED and deduct from farmer credit balance."""
    from app.models.farmer_credit_balance import FarmerCreditBalance, CreditBalanceStatus

    payout = db.query(Payout).filter(Payout.id == payout_id).first()
    if not payout:
        logger.error("_complete_payout: payout %s not found", payout_id)
        return
    if payout.status != PayoutStatus.INITIATED:
        logger.warning(
            "_complete_payout: payout %s already in status %s — skipping",
            payout_id, payout.status.value,
        )
        return

    # Deduct credits from farmer balance
    balance = db.query(FarmerCreditBalance).filter(
        FarmerCreditBalance.id == payout.credit_balance_id
    ).first()
    if balance:
        balance.credits_distributed += payout.amount_credits
        balance.credits_available   -= payout.amount_credits
        if balance.credits_available <= 0:
            balance.credits_available = 0
            balance.status = CreditBalanceStatus.DISTRIBUTED
        balance.updated_at = now
        db.add(balance)

    payout.status                = PayoutStatus.COMPLETED
    payout.completed_at          = now
    payout.provider_reference_id = payment_id   # Razorpay payment_id as reference
    payout.remarks               = f"Paid via Razorpay Checkout. payment_id={payment_id}"
    db.add(payout)
    logger.info("Payout %s marked COMPLETED via Razorpay payment %s", payout_id, payment_id)


def _pay_marketplace_order(db: Session, order_id: int, payment_id: str, now: datetime) -> None:
    """Mark marketplace order PAID."""
    order = db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id).first()
    if not order:
        logger.error("_pay_marketplace_order: order %s not found", order_id)
        return
    if order.status != OrderStatus.APPROVED:
        logger.warning(
            "_pay_marketplace_order: order %s in status %s — skipping",
            order_id, order.status.value,
        )
        return

    order.status = OrderStatus.PAID
    db.add(order)
    logger.info("Marketplace order %s marked PAID via Razorpay payment %s", order_id, payment_id)
