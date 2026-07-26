/**
 * Razorpay Checkout API — Phase 17.
 *
 * Two calls:
 *  1. createRazorpayOrder   → backend creates Razorpay Order; returns order_id + key_id
 *  2. verifyRazorpayPayment → backend verifies HMAC; marks payout/order COMPLETED
 *
 * Uses the shared apiClient (axios) — Bearer token is injected by the auth interceptor.
 *
 * SECURITY: RAZORPAY_KEY_SECRET never leaves the backend.
 * key_id (public test key) is returned and passed to RazorpayCheckout.open().
 */
import { apiClient } from './client';

export type RazorpayPurpose = 'FARMER_PAYOUT' | 'MARKETPLACE_ORDER';

export interface CreateOrderRequest {
  purpose: RazorpayPurpose;
  reference_id: number;   // payout.id or marketplace_order.id
  amount: number;          // in RUPEES (₹) — backend converts to paise
  currency?: string;       // default "INR"
}

export interface CreateOrderResponse {
  payment_record_id: number;  // passed back in verifyRazorpayPayment
  order_id: string;           // Razorpay order_id → RazorpayCheckout.open({ order_id })
  amount_paise: number;       // amount × 100 → RazorpayCheckout.open({ amount })
  currency: string;
  key_id: string;             // rzp_test_xxx → RazorpayCheckout.open({ key })
}

export interface VerifyPaymentRequest {
  payment_record_id: number;
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export type PaymentStatus = 'CREATED' | 'COMPLETED' | 'FAILED';

export interface RazorpayPaymentResponse {
  id: number;
  purpose: RazorpayPurpose;
  reference_id: number;
  razorpay_order_id: string;
  razorpay_payment_id: string | null;
  signature_verified: boolean;
  amount_paise: number;
  currency: string;
  status: PaymentStatus;
  failure_reason: string | null;
  created_at: string;
  completed_at: string | null;
}

/**
 * Step 1 of the Razorpay Checkout flow.
 * Call this before opening RazorpayCheckout.open().
 *
 * @param body   - purpose, reference_id, amount (rupees), currency
 * @returns CreateOrderResponse — use order_id, amount_paise, key_id for the checkout
 * @throws AxiosError on network or backend failure
 */
export async function createRazorpayOrder(
  body: CreateOrderRequest,
): Promise<CreateOrderResponse> {
  const resp = await apiClient.post<CreateOrderResponse>(
    '/payments/razorpay/create-order',
    { currency: 'INR', ...body },
  );
  return resp.data;
}

/**
 * Step 3 of the Razorpay Checkout flow (step 2 is the native checkout UI).
 * Call this after RazorpayCheckout.open() succeeds with payment data.
 *
 * @param body   - payment_record_id (from step 1), razorpay_order_id, razorpay_payment_id, razorpay_signature
 * @returns RazorpayPaymentResponse — check status === "COMPLETED"
 * @throws AxiosError on invalid signature or other failure
 */
export async function verifyRazorpayPayment(
  body: VerifyPaymentRequest,
): Promise<RazorpayPaymentResponse> {
  const resp = await apiClient.post<RazorpayPaymentResponse>(
    '/payments/razorpay/verify',
    body,
  );
  return resp.data;
}
