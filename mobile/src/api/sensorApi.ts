import apiClient from './client';
import type { SensorReading, PaginationParams } from '../types';

export interface SimulateSensorsPayload {
  farm_id: number;
  crop_cycle_id: number;
  number_of_days: number;
}

export interface SimulateSensorsResponse {
  generated_readings: number;
  farm_id: number;
  crop_cycle_id: number;
  requested_days: number | null;
  capped_at_today: boolean;
}

export interface SensorSummary {
  crop_cycle_id: number;
  total_readings: number;
  avg_soil_moisture: number | null;
  avg_water_depth_cm: number | null;
  avg_temperature_c: number | null;
  avg_humidity: number | null;
  avg_methane: number | null;
  avg_data_quality_score: number | null; // 0–100 scale
}

/** GET /sensors/farm/{farm_id} */
export async function getSensorsByFarmApi(
  farmId: number,
  params?: PaginationParams,
): Promise<SensorReading[]> {
  const { data } = await apiClient.get<SensorReading[]>(`/sensors/farm/${farmId}`, { params });
  return data;
}

/** GET /sensors/crop-cycle/{crop_cycle_id} */
export async function getSensorsByCycleApi(
  cycleId: number,
  params?: PaginationParams,
): Promise<SensorReading[]> {
  const { data } = await apiClient.get<SensorReading[]>(`/sensors/crop-cycle/${cycleId}`, {
    params,
  });
  return data;
}

/** GET /sensors/summary/{crop_cycle_id} */
export async function getSensorSummaryApi(cycleId: number): Promise<SensorSummary> {
  const { data } = await apiClient.get<SensorSummary>(`/sensors/summary/${cycleId}`);
  return data;
}

/** POST /sensors/simulate */
export async function simulateSensorsApi(
  payload: SimulateSensorsPayload,
): Promise<SimulateSensorsResponse> {
  const { data } = await apiClient.post<SimulateSensorsResponse>('/sensors/simulate', payload);
  return data;
}

export interface ManualSensorReadingPayload {
  farm_id: number;
  crop_cycle_id: number;
  reading_time: string; // ISO datetime
  soil_moisture: number;   // 0–100
  water_depth_cm: number;  // 0–30
  temperature_c: number;   // 15–45
  humidity: number;        // 20–100
  rainfall_mm: number;     // 0–100
  data_quality_score: number; // 0–100
}

/** POST /sensors/readings — manual sensor reading */
export async function createManualSensorReadingApi(
  payload: ManualSensorReadingPayload,
): Promise<SensorReading> {
  const { data } = await apiClient.post<SensorReading>('/sensors/readings', payload);
  return data;
}
