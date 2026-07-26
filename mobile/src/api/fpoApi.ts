import apiClient from './client';
import type { Farm } from '../types';

export interface FPOFarmer {
  id: number;
  name: string;
  email: string;
  is_active: boolean;
  is_approved: boolean;
  created_at: string;
}

export interface FPOListItem {
  id: number;
  organization_name: string;
  registration_number: string;
  district: string;
  state: string;
}

/** GET /fpo/list — all FPO organizations (any authenticated user can call this) */
export async function getFPOListApi(): Promise<FPOListItem[]> {
  const { data } = await apiClient.get<FPOListItem[]>('/fpo/list');
  return data;
}

/** GET /fpo/farmers — list farmers belonging to this FPO */
export async function getFPOFarmersListApi(): Promise<FPOFarmer[]> {
  const { data } = await apiClient.get<FPOFarmer[]>('/fpo/farmers');
  return data;
}

/** GET /fpo/farms — list all farms linked to this FPO */
export async function getFPOFarmsApi(): Promise<Farm[]> {
  const { data } = await apiClient.get<Farm[]>('/fpo/farms');
  return data;
}

export interface MintableReport {
  report_id: number;
  farm_id: number;
  farm_name: string;
  farmer_id: number | null;
  farmer_name: string;
  estimated_credits: number;
  co2e_reduction_tonnes: number;
  report_status: string;
  verified_at: string | null;
  created_at: string;
}

export interface MintHistoryItem {
  db_id: number;
  token_id: string;
  report_id: number;
  farm_id: number | null;
  farm_name: string;
  farmer_id: number;
  farmer_name: string;
  credit_amount: number;
  minted_at: string | null;
  minted_tx_hash: string | null;
  status: string;
  // Phase 17: real blockchain fields
  blockchain_network: string | null;
  contract_address: string | null;
}

/** GET /fpo/mintable-reports — VERIFIED reports not yet minted */
export async function getFPOMintableReportsApi(): Promise<MintableReport[]> {
  const { data } = await apiClient.get<MintableReport[]>('/fpo/mintable-reports');
  return data;
}

/** GET /fpo/mint-history — all tokens minted by this FPO */
export async function getFPOMintHistoryApi(): Promise<MintHistoryItem[]> {
  const { data } = await apiClient.get<MintHistoryItem[]>('/fpo/mint-history');
  return data;
}

export interface FPOFarmerSummary {
  farmer_id: number;
  name: string;
  email: string;
  total_farms: number;
  approved_farms: number;
  active_crop_cycles: number;
  total_available_credits: number;
}

/** GET /fpo/registry/farmers — enriched farmer list */
export async function getFPOFarmerRegistryApi(): Promise<FPOFarmerSummary[]> {
  const { data } = await apiClient.get<FPOFarmerSummary[]>('/fpo/registry/farmers');
  return data;
}

/** GET /fpo/registry/farms — all farms with lifecycle info */
export async function getFPOFarmRegistryApi(farmStatusFilter?: string): Promise<Farm[]> {
  const params = farmStatusFilter ? { farm_status_filter: farmStatusFilter } : undefined;
  const { data } = await apiClient.get<Farm[]>('/fpo/registry/farms', { params });
  return data;
}

/** GET /fpo/registry/summary */
export async function getFPORegistrySummaryApi(): Promise<Record<string, number>> {
  const { data } = await apiClient.get<Record<string, number>>('/fpo/registry/summary');
  return data;
}

/** GET /fpo/registry/farmers/{farmer_id} */
export async function getFPOFarmerDetailApi(farmerId: number): Promise<any> {
  const { data } = await apiClient.get(`/fpo/registry/farmers/${farmerId}`);
  return data;
}

/** GET /fpo/operations-dashboard — Phase 15 Operations Dashboard */
export async function getFPOOperationsDashboardApi(): Promise<any> {
  const { data } = await apiClient.get('/fpo/operations-dashboard');
  return data;
}
