import apiClient from './client';
import type { VerificationRequest, TokenSummary, SystemStatus } from '../types';

/** GET /admin/risk-reports */
export async function getRiskReportsApi(): Promise<VerificationRequest[]> {
  const { data } = await apiClient.get<VerificationRequest[]>('/admin/risk-reports');
  return data;
}

/** GET /admin/token-summary */
export async function getTokenSummaryApi(): Promise<TokenSummary> {
  const { data } = await apiClient.get<TokenSummary>('/admin/token-summary');
  return data;
}

/** GET /system/status */
export async function getSystemStatusApi(): Promise<SystemStatus> {
  const { data } = await apiClient.get<SystemStatus>('/system/status');
  return data;
}

/** GET /system/payment-status — authenticated; returns boolean flags only, no secrets. */
export interface PaymentStatus {
  provider: string;           // "mock" | "razorpayx"
  mode: string;               // "mock" | "test" | "live"
  configured: boolean;
  execution_enabled: boolean;
  simulated: boolean;
  key_id_set?: boolean;
  secret_set?: boolean;
  account_number_set?: boolean;
}

export async function getPaymentStatusApi(): Promise<PaymentStatus> {
  const { data } = await apiClient.get<PaymentStatus>('/system/payment-status');
  return data;
}

/** GET /fpo/farmers */
export async function getFPOFarmersApi() {
  const { data } = await apiClient.get('/fpo/farmers');
  return data;
}
