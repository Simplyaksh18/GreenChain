import apiClient from './client';
import type {
  MobileDashboardResponse,
  SatelliteObservation,
  DroneObservation,
  PaginationParams,
} from '../types';

/** GET /mobile/dashboard — role-aware */
export async function getMobileDashboardApi(): Promise<MobileDashboardResponse> {
  const { data } = await apiClient.get<MobileDashboardResponse>('/mobile/dashboard');
  return data;
}

interface SatelliteParams extends PaginationParams {
  crop_cycle_id?: number;
}

/** GET /satellite/{farm_id} */
export async function getSatelliteObsApi(
  farmId: number,
  params?: SatelliteParams,
): Promise<SatelliteObservation[]> {
  const { data } = await apiClient.get<SatelliteObservation[]>(`/satellite/${farmId}`, { params });
  return data;
}

/** GET /drone/{farm_id} */
export async function getDroneObsApi(
  farmId: number,
  params?: SatelliteParams,
): Promise<DroneObservation[]> {
  const { data } = await apiClient.get<DroneObservation[]>(`/drone/${farmId}`, { params });
  return data;
}
