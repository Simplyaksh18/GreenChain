import apiClient from './client';
import type { Farm, CropCycle, PaginationParams } from '../types';

interface FarmListParams extends PaginationParams {
  district?: string;
  state?: string;
  is_approved?: boolean;
  farm_status?: string;
}

export interface CreateFarmPayload {
  farm_name: string;
  land_area_acres: number;
  latitude: number;
  longitude: number;
  village: string;
  district: string;
  state: string;
  soil_type: string;
  water_source: string;
  fpo_id?: number | null;
}

export interface CreateCropCyclePayload {
  crop_type: string;
  season: string;
  start_date: string; // ISO date string
  end_date?: string | null;
  baseline_method: string;
  reduction_practice: string;
}

export interface UpdateCropCyclePayload {
  crop_type?: string;
  season?: string;
  start_date?: string;
  end_date?: string | null;
  baseline_method?: string;
  reduction_practice?: string;
  status?: string;
}

export interface HarvestCropCyclePayload {
  harvest_date: string;  // ISO date
  yield_quantity?: number;
  yield_unit?: string;
  end_date?: string;
}

export interface FarmBoundary {
  farm_id: number;
  farm_name: string;
  farm_boundary_geojson: string | null;
  boundary_area_hectares: number | null;
  boundary_area_acres: number | null;
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

export interface FPORegistrySummary {
  total_farmers: number;
  total_farms: number;
  approved_farms: number;
  pending_farms: number;
  suspended_farms: number;
  total_acreage: number;
  active_crop_cycles: number;
}

export interface CreditEligibility {
  report_id: number;
  eligible: boolean;
  reason: string;
  current: number;
  required: number;
  current_credits: number;
  baseline_methane_kg: number;
  current_methane_kg: number;
  methane_reduction_kg: number;
  required_methane_reduction_kg: number;
  gap_methane_kg: number | null;
  steps: Array<{
    step: number;
    label: string;
    value: number | string;
    unit: string;
    note?: string;
  }>;
}

export interface MRVImportResult {
  success: boolean;
  inserted: number;
  skipped_duplicates: number;
  total_rows: number;
  errors: string[];
}

/** GET /farms — role-aware farm list with optional filters and pagination */
export async function getFarmsApi(params?: FarmListParams): Promise<Farm[]> {
  const { data } = await apiClient.get<Farm[]>('/farms', { params });
  return data;
}

/** GET /farms/{farm_id} */
export async function getFarmApi(farmId: number): Promise<Farm> {
  const { data } = await apiClient.get<Farm>(`/farms/${farmId}`);
  return data;
}

/** GET /farms/{farm_id}/crop-cycles */
export async function getCropCyclesApi(farmId: number): Promise<CropCycle[]> {
  const { data } = await apiClient.get<CropCycle[]>(`/farms/${farmId}/crop-cycles`);
  return data;
}

/** POST /farms — farmer creates a new farm */
export async function createFarmApi(payload: CreateFarmPayload): Promise<Farm> {
  const { data } = await apiClient.post<Farm>('/farms', payload);
  return data;
}

/** POST /farms/{farm_id}/crop-cycles — farmer creates a new crop cycle */
export async function createCropCycleApi(
  farmId: number,
  payload: CreateCropCyclePayload,
): Promise<CropCycle> {
  const { data } = await apiClient.post<CropCycle>(`/farms/${farmId}/crop-cycles`, payload);
  return data;
}

/** PATCH /farms/{farm_id}/crop-cycles/{cycle_id} */
export async function updateCropCycleApi(
  farmId: number,
  cycleId: number,
  payload: UpdateCropCyclePayload,
): Promise<CropCycle> {
  const { data } = await apiClient.patch<CropCycle>(
    `/farms/${farmId}/crop-cycles/${cycleId}`,
    payload,
  );
  return data;
}

/** PATCH /farms/{farm_id}/crop-cycles/{cycle_id}/harvest */
export async function harvestCropCycleApi(
  farmId: number,
  cycleId: number,
  payload: HarvestCropCyclePayload,
): Promise<CropCycle> {
  const { data } = await apiClient.patch<CropCycle>(
    `/farms/${farmId}/crop-cycles/${cycleId}/harvest`,
    payload,
  );
  return data;
}

/** PATCH /farms/{farm_id}/crop-cycles/{cycle_id}/close */
export async function closeCropCycleApi(farmId: number, cycleId: number): Promise<CropCycle> {
  const { data } = await apiClient.patch<CropCycle>(
    `/farms/${farmId}/crop-cycles/${cycleId}/close`,
  );
  return data;
}

/** DELETE /farms/{farm_id} — soft delete */
export async function deleteFarmApi(farmId: number): Promise<{ message: string }> {
  const { data } = await apiClient.delete<{ message: string }>(`/farms/${farmId}`);
  return data;
}

/** PATCH /farms/{farm_id}/archive (FARMER) */
export async function archiveFarmApi(farmId: number, reason?: string): Promise<Farm> {
  const { data } = await apiClient.patch<Farm>(`/farms/${farmId}/archive`, { reason });
  return data;
}

/** PATCH /farms/{farm_id}/suspend (FPO) */
export async function suspendFarmApi(farmId: number, reason?: string): Promise<Farm> {
  const { data } = await apiClient.patch<Farm>(`/farms/${farmId}/suspend`, { reason });
  return data;
}

/** PATCH /farms/{farm_id}/restore (FPO) */
export async function restoreFarmApi(farmId: number): Promise<Farm> {
  const { data } = await apiClient.patch<Farm>(`/farms/${farmId}/restore`);
  return data;
}

/** PATCH /farms/{farm_id}/approve (FPO / via farms router) */
export async function approveFarmNewApi(farmId: number): Promise<Farm> {
  const { data } = await apiClient.patch<Farm>(`/farms/${farmId}/approve`);
  return data;
}

/** POST /fpo/farms/{farm_id}/approve (legacy endpoint) */
export async function approveFarmApi(farmId: number): Promise<Farm> {
  const { data } = await apiClient.post<Farm>(`/fpo/farms/${farmId}/approve`);
  return data;
}

/** GET /farms/{farm_id}/boundary */
export async function getFarmBoundaryApi(farmId: number): Promise<FarmBoundary> {
  const { data } = await apiClient.get<FarmBoundary>(`/farms/${farmId}/boundary`);
  return data;
}

/** PATCH /farms/{farm_id}/boundary */
export async function setFarmBoundaryApi(
  farmId: number,
  geojson: string,
  hectares?: number,
  acres?: number,
): Promise<FarmBoundary> {
  const { data } = await apiClient.patch<FarmBoundary>(`/farms/${farmId}/boundary`, {
    farm_boundary_geojson: geojson,
    boundary_area_hectares: hectares,
    boundary_area_acres: acres,
  });
  return data;
}

/** GET /fpo/registry/summary */
export async function getFPORegistrySummaryApi(): Promise<FPORegistrySummary> {
  const { data } = await apiClient.get<FPORegistrySummary>('/fpo/registry/summary');
  return data;
}

/** GET /fpo/registry/farms?farm_status_filter=... */
export async function getFPOFarmRegistryApi(statusFilter?: string): Promise<Farm[]> {
  const params = statusFilter ? { farm_status_filter: statusFilter } : {};
  const { data } = await apiClient.get<Farm[]>('/fpo/registry/farms', { params });
  return data;
}

/** GET /fpo/registry/farmers */
export async function getFPOFarmerRegistryApi(): Promise<FPOFarmerSummary[]> {
  const { data } = await apiClient.get<FPOFarmerSummary[]>('/fpo/registry/farmers');
  return data;
}

/** GET /fpo/registry/farmers/{farmer_id} */
export async function getFPOFarmerDetailApi(farmerId: number): Promise<any> {
  const { data } = await apiClient.get(`/fpo/registry/farmers/${farmerId}`);
  return data;
}

/** GET /credits/reports/{report_id}/eligibility */
export async function getCreditEligibilityApi(reportId: number): Promise<CreditEligibility> {
  const { data } = await apiClient.get<CreditEligibility>(`/credits/reports/${reportId}/eligibility`);
  return data;
}

/** GET /carbon-reports/{report_id}/detail */
export async function getReportDetailApi(reportId: number): Promise<any> {
  const { data } = await apiClient.get(`/carbon-reports/${reportId}/detail`);
  return data;
}
