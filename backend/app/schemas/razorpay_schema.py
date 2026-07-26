"""Pydantic schemas for Razorpay Checkout — Phase 17."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.razorpay_payment import RazorpayPaymentPurpose, RazorpayPaymentStatus


class CreateOrderRequest(BaseModel):
    purpose:      RazorpayPaymentPurpose
    reference_id: int = Field(ge=1, description="payout.id or marketplace_order.id")
    amount:       int = Field(ge=1, description="Amount in RUPEES (₹) — converted to paise internally")
    currency:     str = Field(default="INR", max_length=10)


class CreateOrderResponse(BaseModel):
    """Returned to mobile — used to open RazorpayCheckout.open()."""
    payment_record_id: int          # razorpay_payments.id — passed back in verify call
    order_id:          str          # Razorpay order_id (order_XXX)
    amount_paise:      int          # amount * 100 — for Razorpay SDK `amount` field
    currency:          str
    key_id:            str          # rzp_test_xxx — mobile passes this to RazorpayCheckout
    # NEVER include key_secret here


class VerifyPaymentRequest(BaseModel):
    payment_record_id:    int    # razorpay_payments.id — returned by create-order
    razorpay_order_id:    str
    razorpay_payment_id:  str
    razorpay_signature:   str


class PaymentResponse(BaseModel):
    id:                  int
    purpose:             RazorpayPaymentPurpose
    reference_id:        int
    razorpay_order_id:   str
    razorpay_payment_id: Optional[str]
    signature_verified:  bool
    amount_paise:        int
    currency:            str
    status:              RazorpayPaymentStatus
    failure_reason:      Optional[str]
    created_at:          datetime
    completed_at:        Optional[datetime]

    model_config = {"from_attributes": True}
