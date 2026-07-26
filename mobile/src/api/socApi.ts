/**
 * socApi.ts — Phase 12.5 / Phase 13 SOC (Soil Organic Carbon) client
 *
 * All SOC credits are INFORMATIONAL ONLY.
 * They must NOT be passed to the minting, custodial balance,
 * payout, or registry submission flows.
 * Only methane credits are mintable in Phase 12.5.
 */
import apiClient from './client';

// ── Types ──────────────────────────────────────────────────────────────────────

export type SOCSourceType = 'LAB' | 'MANUAL' | 'COPERNICUS' | 'BHUVAN' | 'ESTIMATED';

export interface SOCMeasurement {
  id: number;
  farm_id: number;
  crop_cycle_id: number | null;
  soc_percent: number;
  soc_source: SOCSourceType;
  confidence_score: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

// ── Phase 13: confidence breakdown & diagnostics ───────────────────────────────

export interface SOCConfidenceBreakdown {
  baseline_source: string;
  baseline_confidence: number;      // 0–100
  observation_source: string;
  observation_confidence: number;   // 0–100
  provider_confidence: number;      // 0–100
  crop_cycle_confidence: number;    // 0–100
  final_confidence: number;         // 0–100
  reason: string;
}

export interface SOCDiagnostics {
  provider_used: string;
  observation_count: number;
  ndvi_average: number | null;
  farm_area_ha: number;
  bulk_density: number;
  soil_depth_cm: number;
  calculation_version: string;
  observation_dates: string[];
  baseline_soc_source: string;
  soc_gain_formula: string;
  co2e_conversion: string;
}

export interface SOCEstimate {
  baseline_soc_percent: number;
  current_soc_percent: number;
  soc_gain_percent: number;
  estimated_soc_tonnes: number;
  soc_co2e_tonnes: number;
  /** INFORMATIONAL ONLY — not mintable */
  soc_credits: number;
  confidence_score: number;
  source_used: string;
  sources_detail: string[];
  methodology_notes: string;
  /** Always true in Phase 12.5 */
  is_informational_only: true;

  // Phase 13
  source_label: string;
  confidence_breakdown: SOCConfidenceBreakdown | null;
  diagnostics: SOCDiagnostics | null;
  recommendations: string[];
}

export interface SOCReport {
  id: number;
  farm_id: number;
  crop_cycle_id: number;
  baseline_soc: number;
  current_soc: number;
  soc_gain: number;
  soc_co2e: number;
  /** INFORMATIONAL ONLY — not mintable */
  soc_credits: number;
  confidence_score: number;
  sources_used: string;
  methodology: string | null;
  created_at: string;
  /** Always true in Phase 12.5 */
  is_informational_only: true;
}

export interface MethaneSectionData {
  baseline_methane_kg: number;
  current_methane_kg: number;
  methane_reduction_kg: number;
  methane_co2e_tonnes: number;
  methane_credits: number;
  report_hash: string;
}

export interface SOCSectionData {
  baseline_soc_percent: number;
  current_soc_percent: number;
  soc_gain_percent: number;
  soc_co2e_tonnes: number;
  /** INFORMATIONAL ONLY — not mintable */
  soc_credits: number;
  sources_used: string[];
  confidence_score: number;
  is_informational_only: true;

  // Phase 13
  source_label: string;
  confidence_breakdown: SOCConfidenceBreakdown | null;
  diagnostics: SOCDiagnostics | null;
  recommendations: string[];
}

export interface CombinedCarbonReport {
  farm_id: number;
  crop_cycle_id: number;
  carbon_report_id: number | null;
  methane_section: MethaneSectionData;
  soc_section: SOCSectionData;
  /** Mintable — only methane credits */
  methane_credits: number;
  /** Informational — never mintable in Phase 12.5 */
  soc_credits: number;
  /** methane_credits + soc_credits — display only */
  total_potential_credits: number;
  /** = methane_credits; what gets minted */
  mintable_credits: number;
  minting_note: string;
}

/**
 * data_status values — drives mobile SOC card rendering:
 *   REPORT_AVAILABLE          — saved SOC report; show full figures
 *   LIVE_ESTIMATE             — no saved report but satellite obs exist; show live estimate
 *   INSUFFICIENT_SATELLITE_DATA — crop cycle exists but no satellite obs
 *   NO_CROP_CYCLE             — no crop cycle registered
 */
export type SOCDataStatus =
  | 'REPORT_AVAILABLE'
  | 'LIVE_ESTIMATE'
  | 'INSUFFICIENT_SATELLITE_DATA'
  | 'NO_CROP_CYCLE';

export interface FarmSOCOverview {
  farm_id: number;
  farm_name: string;

  // Status
  data_status: SOCDataStatus;
  is_persisted: boolean;
  crop_cycle_id: number | null;

  // SOC figures (null when status is INSUFFICIENT_SATELLITE_DATA or NO_CROP_CYCLE)
  baseline_soc_percent: number | null;
  current_soc_percent: number | null;
  soc_gain_percent: number | null;
  soc_co2e: number | null;
  /** INFORMATIONAL ONLY — not mintable */
  soc_credits: number | null;
  confidence_score: number | null;
  sources_used: string[];
  message: string;

  // Diagnostics
  satellite_observation_count: number;
  crop_cycle_found: boolean;
  baseline_source: string | null;
  missing_requirements: string[];

  /** Always true in Phase 12.5 */
  is_informational_only: true;

  // Phase 13
  source_label: string;
  confidence_breakdown: SOCConfidenceBreakdown | null;
  diagnostics: SOCDiagnostics | null;
  recommendations: string[];
}

// ── Payment status ─────────────────────────────────────────────────────────────

export interface PaymentStatus {
  provider: string;
  mode: string;
  configured: boolean;
  execution_enabled: boolean;
  simulated?: boolean;
  key_id_set?: boolean;
  secret_set?: boolean;
  account_number_set?: boolean;
}

// ── API functions ──────────────────────────────────────────────────────────────

/** POST /soc/farms/{farmId}/measurements */
export async function addSOCMeasurement(
  farmId: number,
  payload: {
    soc_percent: number;
    soc_source: SOCSourceType;
    confidence_score?: number;
    notes?: string;
    crop_cycle_id?: number;
  },
): Promise<SOCMeasurement> {
  const { data } = await apiClient.post<SOCMeasurement>(
    `/soc/farms/${farmId}/measurements`,
    payload,
  );
  return data;
}

/** GET /soc/farms/{farmId}/measurements */
export async function listSOCMeasurements(farmId: number): Promise<SOCMeasurement[]> {
  const { data } = await apiClient.get<SOCMeasurement[]>(
    `/soc/farms/${farmId}/measurements`,
  );
  return data;
}

/** GET /soc/farms/{farmId}/crop-cycles/{cycleId}/estimate */
export async function getSOCEstimate(
  farmId: number,
  cycleId: number,
): Promise<SOCEstimate> {
  const { data } = await apiClient.get<SOCEstimate>(
    `/soc/farms/${farmId}/crop-cycles/${cycleId}/estimate`,
  );
  return data;
}

/** POST /soc/farms/{farmId}/crop-cycles/{cycleId}/report */
export async function generateSOCReport(
  farmId: number,
  cycleId: number,
): Promise<SOCReport> {
  const { data } = await apiClient.post<SOCReport>(
    `/soc/farms/${farmId}/crop-cycles/${cycleId}/report`,
  );
  return data;
}

/** GET /soc/farms/{farmId}/crop-cycles/{cycleId}/report */
export async function getSOCReport(
  farmId: number,
  cycleId: number,
): Promise<SOCReport> {
  const { data } = await apiClient.get<SOCReport>(
    `/soc/farms/${farmId}/crop-cycles/${cycleId}/report`,
  );
  return data;
}

/** GET /soc/farms/{farmId}/crop-cycles/{cycleId}/combined */
export async function getCombinedCarbonReport(
  farmId: number,
  cycleId: number,
): Promise<CombinedCarbonReport> {
  const { data } = await apiClient.get<CombinedCarbonReport>(
    `/soc/farms/${farmId}/crop-cycles/${cycleId}/combined`,
  );
  return data;
}

/** GET /soc/farms/{farmId}/overview */
export async function getFarmSOCOverview(farmId: number): Promise<FarmSOCOverview> {
  const { data } = await apiClient.get<FarmSOCOverview>(
    `/soc/farms/${farmId}/overview`,
  );
  return data;
}

/** GET /system/payment-status */
export async function getPaymentStatus(): Promise<PaymentStatus> {
  const { data } = await apiClient.get<PaymentStatus>('/system/payment-status');
  return data;
}
