import apiClient from './client';
import type { SatelliteObservation, DroneObservation, PaginationParams } from '../types';

interface ObsParams extends PaginationParams {
  crop_cycle_id?: number;
}

/** GET /satellite/{farm_id} */
export async function getSatelliteObservationsApi(
  farmId: number,
  params?: ObsParams,
): Promise<SatelliteObservation[]> {
  const { data } = await apiClient.get<SatelliteObservation[]>(`/satellite/${farmId}`, { params });
  return data;
}

/** GET /drone/{farm_id} */
export async function getDroneObservationsApi(
  farmId: number,
  params?: ObsParams,
): Promise<DroneObservation[]> {
  const { data } = await apiClient.get<DroneObservation[]>(`/drone/${farmId}`, { params });
  return data;
}

export interface EvidenceFile {
  id: number;
  farm_id: number;
  crop_cycle_id: number | null;
  file_url: string;
  file_type: string;
  description: string | null;
  uploaded_by: number;
  created_at: string;
}

/** GET /evidence/crop-cycle/{crop_cycle_id} */
export async function getEvidenceByCycleApi(cycleId: number): Promise<EvidenceFile[]> {
  const { data } = await apiClient.get<EvidenceFile[]>(`/evidence/crop-cycle/${cycleId}`);
  return data;
}

export interface ManualSatelliteObservationPayload {
  farm_id: number;
  crop_cycle_id?: number | null;
  observation_date: string; // ISO date YYYY-MM-DD
  ndvi: number;             // -1.0 to 1.0
  ndwi: number;             // -1.0 to 1.0
  vegetation_health: 'POOR' | 'FAIR' | 'GOOD' | 'EXCELLENT';
  flood_risk?: 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH';
  cloud_cover_percent?: number;
}

/** POST /satellite/observations — manual satellite observation */
export async function createManualSatelliteObservationApi(
  payload: ManualSatelliteObservationPayload,
): Promise<SatelliteObservation> {
  const { data } = await apiClient.post<SatelliteObservation>('/satellite/observations', payload);
  return data;
}

export interface ManualDroneObservationPayload {
  farm_id: number;
  crop_cycle_id?: number | null;
  observation_date: string; // ISO date YYYY-MM-DD
  vegetation_cover_percent: number; // 0–100
  standing_water_percent: number;   // 0–100
  anomaly_score?: number;           // 0–100
  image_reference?: string | null;
}

/** POST /drone/observations — manual drone observation */
export async function createManualDroneObservationApi(
  payload: ManualDroneObservationPayload,
): Promise<DroneObservation> {
  const { data } = await apiClient.post<DroneObservation>('/drone/observations', payload);
  return data;
}

// ── High-Emission Demo MRV ────────────────────────────────────────────────────

export type HighEmissionScenario =
  | 'DAIRY_SRI_LOW'
  | 'DAIRY_BIODIGESTER'
  | 'MIXED_LIVESTOCK_BIOCHAR'
  | 'BUFFALO_BIODIGESTER'
  | 'EDGE_CERTIFICATE_ONLY';

export interface HighEmissionDemoResponse {
  success: boolean;
  scenario: string;
  scenario_description: string;
  livestock_note: string;
  farm_id: number;
  crop_cycle_id: number;
  /** Number of sensor readings inserted (field name from backend: sensor_readings_generated) */
  sensor_readings_generated: number;
  /** Number of satellite observations inserted */
  satellite_observations_generated: number;
  /** Number of drone observations inserted */
  drone_observations_generated: number;
  expected_co2e_reduction_tonnes: number;
  expected_credits: number;
  baseline_methane_kg_day: number;
  current_methane_kg_day: number;
  demo_label: string;
  message: string;
  warning: string;
}

export interface ScenarioInfo {
  key: string;
  label: string;
  description: string;
  livestock_type: string;
  intervention: string;
  expected_credits_min: number;
  expected_credits_max: number;
  expected_co2e_min: number;
  expected_co2e_max: number;
}

/** POST /mrv/demo/high-emission */
export async function generateHighEmissionDemoApi(
  farmId: number,
  cropCycleId: number,
  scenario: HighEmissionScenario,
  days?: number,
): Promise<HighEmissionDemoResponse> {
  const { data } = await apiClient.post<HighEmissionDemoResponse>('/mrv/demo/high-emission', {
    farm_id: farmId,
    crop_cycle_id: cropCycleId,
    scenario,
    days: days ?? 30,
  });
  return data;
}

/** GET /mrv/demo/scenarios */
export async function getMrvScenariosApi(): Promise<ScenarioInfo[]> {
  const { data } = await apiClient.get<ScenarioInfo[]>('/mrv/demo/scenarios');
  return data;
}
