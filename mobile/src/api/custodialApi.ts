/**
 * custodialApi.ts — Phase 9 Custodial Model API calls
 *
 * Farmer:
 *   GET  /credits/my-balance
 *   POST /farmers/payout-details
 *   GET  /farmers/payout-details
 *   GET  /farmers/payouts
 *
 * FPO:
 *   PATCH /fpo/profile/wallet
 *   GET   /fpo/profile/wallet
 *   GET   /fpo/credits/farmers
 *   POST  /fpo/payouts/initiate
 *   POST  /fpo/payouts/{id}/complete
 *   GET   /fpo/payouts
 *
 * Admin:
 *   GET  /admin/credits/summary
 *   GET  /admin/payouts
 */
import apiClient from './client';
import type {
  FarmerCreditSummary,
  FarmerCreditBalance,
  EnrichedFarmerCreditBalance,
  FarmerPayoutDetails,
  Payout,
  FPOWallet,
  PaginationParams,
} from '../types';

// ── Farmer ─────────────────────────────────────────────────────────────────────

export async function getMyCreditBalance(): Promise<FarmerCreditSummary> {
  const res = await apiClient.get('/credits/my-balance');
  return res.data;
}

export async function upsertPayoutDetails(body: {
  preferred_payout_method?: 'UPI' | 'BANK_TRANSFER';
  upi_id?: string;
  bank_account_holder_name?: string;
  bank_account_number?: string;
  ifsc_code?: string;
  bank_name?: string;
}): Promise<FarmerPayoutDetails> {
  const res = await apiClient.post('/farmers/payout-details', body);
  return res.data;
}

export async function getPayoutDetails(): Promise<FarmerPayoutDetails> {
  const res = await apiClient.get('/farmers/payout-details');
  return res.data;
}

export async function getMyPayouts(params?: PaginationParams): Promise<Payout[]> {
  const res = await apiClient.get('/farmers/payouts', { params });
  return res.data;
}

// ── FPO ────────────────────────────────────────────────────────────────────────

export async function updateFPOWallet(body: {
  wallet_address?: string;
  vault_identifier?: string;
  wallet_network?: string;
}): Promise<FPOWallet> {
  const res = await apiClient.patch('/fpo/profile/wallet', body);
  return res.data;
}

export async function getFPOWallet(): Promise<FPOWallet> {
  const res = await apiClient.get('/fpo/profile/wallet');
  return res.data;
}

export async function getFPOFarmerBalances(): Promise<EnrichedFarmerCreditBalance[]> {
  const res = await apiClient.get('/fpo/credits/farmers');
  return res.data;
}

export async function getFPOFarmerPayoutDetails(balanceId: number): Promise<{
  farmer_id: number;
  farmer_name: string | null;
  farmer_email: string | null;
  preferred_payout_method: 'UPI' | 'BANK_TRANSFER' | null;
  /** Phase 10A: FPO sees masked UPI only */
  upi_id_masked: string | null;
  bank_account_holder_name: string | null;
  bank_account_number_masked: string | null;
  ifsc_code: string | null;
  payout_details_verified: boolean;
  has_payout_details: boolean;
}> {
  const res = await apiClient.get(`/fpo/credits/farmers/${balanceId}/payout-details`);
  return res.data;
}

export async function verifyFPOWallet(): Promise<import('../types').FPOWalletVerifyResponse> {
  const res = await apiClient.post('/fpo/profile/wallet/verify', {});
  return res.data;
}

export async function verifyPayoutDetails(): Promise<import('../types').FarmerPayoutDetails> {
  const res = await apiClient.post('/farmers/payout-details/verify');
  return res.data;
}

export async function initiatePayoutApi(body: {
  credit_balance_id: number;
  amount_credits: number;
  price_per_credit: number;
  currency?: string;
  remarks?: string;
}): Promise<Payout> {
  const res = await apiClient.post('/fpo/payouts/initiate', body);
  return res.data;
}

export async function completePayoutApi(
  payoutId: number,
  body?: { remarks?: string },
): Promise<Payout> {
  const res = await apiClient.post(`/fpo/payouts/${payoutId}/complete`, body ?? {});
  return res.data;
}

export async function getFPOPayouts(params?: PaginationParams): Promise<Payout[]> {
  const res = await apiClient.get('/fpo/payouts', { params });
  return res.data;
}

// ── Admin ──────────────────────────────────────────────────────────────────────

export async function getAdminCreditSummary() {
  const res = await apiClient.get('/admin/credits/summary');
  return res.data;
}

export async function getAdminPayouts(params?: PaginationParams): Promise<Payout[]> {
  const res = await apiClient.get('/admin/payouts', { params });
  return res.data;
}
