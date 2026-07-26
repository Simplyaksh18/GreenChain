/**
 * Phase 16 — Registry & Marketplace API client
 *
 * Public registry:  no auth required
 * Marketplace:      FPO (listings, order mgmt), Buyer (orders), Admin (oversight)
 *
 * Security rules enforced here:
 *  - No Razorpay secrets ever sent from mobile
 *  - Never send or read raw bank/UPI details
 */
import apiClient from './client';

// ── Types ──────────────────────────────────────────────────────────────────────

export interface PublicReport {
  id: number;
  farm_id: number;
  farm_name: string | null;
  district: string | null;
  state: string | null;
  fpo_name: string | null;
  crop_type: string | null;
  season: string | null;
  baseline_method: string | null;
  reduction_practice: string | null;
  verified_co2e_tonnes: number;
  estimated_credits: number;
  report_status: string;
  report_hash_short: string | null;
  verification_status: string | null;
  evidence_count: number;
  created_at: string | null;
}

export interface PublicToken {
  id: number;
  token_id: string;
  token_standard: string | null;
  credit_amount: number;
  status: string;
  carbon_report_id: number;
  farm_name: string | null;
  district: string | null;
  state: string | null;
  verified_co2e_tonnes: number | null;
  minted_tx_hash_short: string | null;
  minted_at: string | null;
  created_at: string | null;
}

export interface PublicFarm {
  id: number;
  farm_name: string;
  village: string | null;
  district: string | null;
  state: string | null;
  land_area_acres: number;
  boundary_area_hectares: number | null;
  fpo_name: string | null;
  farm_status: string;
  total_reports: number;
  verified_reports: number;
  total_tokens: number;
}

export interface MarketplaceListing {
  id: number;
  farmer_credit_balance_id: number;
  fpo_id: number;
  farmer_id: number | null;
  carbon_token_id: number;
  credits_listed: number;
  credits_available: number;
  price_per_credit: number;
  currency: string;
  listing_status: string;
  created_at: string;
  updated_at: string | null;
}

export interface MarketplaceOrder {
  id: number;
  listing_id: number;
  buyer_name: string;
  buyer_email?: string;
  buyer_organization: string | null;
  credits_requested: number;
  quoted_amount: number;
  order_status: string;
  created_at: string;
}

export interface RetirementCertificate {
  id: number;
  order_id: number;
  token_id: number;
  buyer_name: string;
  credits_retired: number;
  retirement_reason: string | null;
  certificate_hash: string;
  created_at: string;
}

export interface CreateListingParams {
  farmer_credit_balance_id: number;
  carbon_token_id: number;
  credits_listed: number;
  price_per_credit: number;
  currency?: string;
}

export interface CreateOrderParams {
  listing_id: number;
  buyer_name: string;
  buyer_email: string;
  buyer_organization?: string;
  credits_requested: number;
}

// ── Public Registry ────────────────────────────────────────────────────────────

export interface RegistryFilters {
  state?: string;
  district?: string;
  crop_type?: string;
  status?: string;
  credit_min?: number;
  credit_max?: number;
  vintage_year?: number;
  fpo_id?: number;
  limit?: number;
  offset?: number;
}

/** GET /registry/public/reports — no auth required */
export async function getPublicReports(filters?: RegistryFilters): Promise<PublicReport[]> {
  const { data } = await apiClient.get('/registry/public/reports', { params: filters });
  return data;
}

/** GET /registry/public/reports/{id} */
export async function getPublicReport(reportId: number): Promise<PublicReport> {
  const { data } = await apiClient.get(`/registry/public/reports/${reportId}`);
  return data;
}

/** GET /registry/public/tokens */
export async function getPublicTokens(filters?: {
  state?: string;
  district?: string;
  status?: string;
  credit_min?: number;
  credit_max?: number;
  limit?: number;
  offset?: number;
}): Promise<PublicToken[]> {
  const { data } = await apiClient.get('/registry/public/tokens', { params: filters });
  return data;
}

/** GET /registry/public/tokens/{id} */
export async function getPublicToken(tokenId: number): Promise<PublicToken> {
  const { data } = await apiClient.get(`/registry/public/tokens/${tokenId}`);
  return data;
}

/** GET /registry/public/farms/{id} */
export async function getPublicFarm(farmId: number): Promise<PublicFarm> {
  const { data } = await apiClient.get(`/registry/public/farms/${farmId}`);
  return data;
}

// ── Marketplace: Listings (FPO) ────────────────────────────────────────────────

/** GET /marketplace/listings — FPO sees own listings */
export async function getFPOListings(): Promise<MarketplaceListing[]> {
  const { data } = await apiClient.get('/marketplace/listings');
  return data;
}

/** POST /marketplace/listings — FPO creates listing */
export async function createListing(params: CreateListingParams): Promise<MarketplaceListing> {
  const { data } = await apiClient.post('/marketplace/listings', params);
  return data;
}

/** PATCH /marketplace/listings/{id} — FPO updates price or pauses */
export async function updateListing(
  listingId: number,
  updates: { price_per_credit?: number; listing_status?: string }
): Promise<MarketplaceListing> {
  const { data } = await apiClient.patch(`/marketplace/listings/${listingId}`, updates);
  return data;
}

/** POST /marketplace/listings/{id}/cancel */
export async function cancelListing(listingId: number): Promise<MarketplaceListing> {
  const { data } = await apiClient.post(`/marketplace/listings/${listingId}/cancel`);
  return data;
}

// ── Marketplace: Orders ────────────────────────────────────────────────────────

/** GET /marketplace/listings/{id}/orders — FPO sees orders for a listing */
export async function getListingOrders(listingId: number): Promise<MarketplaceOrder[]> {
  const { data } = await apiClient.get(`/marketplace/listings/${listingId}/orders`);
  return data;
}

/** GET /marketplace/orders — FPO/Admin sees all orders */
export async function getAllOrders(): Promise<MarketplaceOrder[]> {
  const { data } = await apiClient.get('/marketplace/orders');
  return data;
}

/** POST /marketplace/orders — Buyer submits interest */
export async function submitOrder(params: CreateOrderParams): Promise<MarketplaceOrder> {
  const { data } = await apiClient.post('/marketplace/orders', params);
  return data;
}

/** POST /marketplace/orders/{id}/approve — FPO approves */
export async function approveOrder(orderId: number): Promise<MarketplaceOrder> {
  const { data } = await apiClient.post(`/marketplace/orders/${orderId}/approve`);
  return data;
}

/** POST /marketplace/orders/{id}/reject — FPO rejects */
export async function rejectOrder(orderId: number, remarks?: string): Promise<MarketplaceOrder> {
  const { data } = await apiClient.post(`/marketplace/orders/${orderId}/reject`, { remarks });
  return data;
}

/** POST /marketplace/orders/{id}/retire — FPO retires credits */
export async function retireOrder(
  orderId: number,
  retirementReason?: string
): Promise<RetirementCertificate> {
  const { data } = await apiClient.post(`/marketplace/orders/${orderId}/retire`, {
    retirement_reason: retirementReason,
  });
  return data;
}

/** GET /marketplace/orders/{id}/certificate */
export async function getRetirementCertificate(orderId: number): Promise<RetirementCertificate> {
  const { data } = await apiClient.get(`/marketplace/orders/${orderId}/certificate`);
  return data;
}

// ── Phase 22B — buyer + payment endpoints ────────────────────────────────────

export interface MyOrder extends MarketplaceOrder {
  paid_at?: string | null;
  payment_method?: string | null;
  payment_reference?: string | null;
  buyer_user_id?: number | null;
}

/**
 * GET /marketplace/my-orders — orders the current authenticated user submitted.
 * Any role may call.
 */
export async function getMyOrders(): Promise<MyOrder[]> {
  const { data } = await apiClient.get('/marketplace/my-orders');
  return data;
}

/**
 * GET /marketplace/listings — active listings across FPOs (non-FPO, non-admin
 * callers only see ACTIVE listings, which is what we want for buyer browse).
 */
export async function browseActiveListings(): Promise<MarketplaceListing[]> {
  const { data } = await apiClient.get('/marketplace/listings');
  return data;
}

/**
 * POST /marketplace/orders/{id}/mark-paid — FPO/Admin records a manual/test
 * payment. NOT a real payment gateway. Idempotent on already-PAID orders.
 */
export async function markOrderPaid(
  orderId: number,
  paymentReference?: string,
): Promise<MarketplaceOrder & { message: string; idempotent: boolean }> {
  const { data } = await apiClient.post(`/marketplace/orders/${orderId}/mark-paid`, {
    payment_reference: paymentReference,
  });
  return data;
}
