import apiClient from './client';
import type { CarbonReport, ReportStatus, PaginationParams } from '../types';

interface ReportListParams extends PaginationParams {
  status?: ReportStatus;
}

/** GET /carbon-reports/farm/{farm_id} */
export async function getReportsByFarmApi(
  farmId: number,
  params?: ReportListParams,
): Promise<CarbonReport[]> {
  const { data } = await apiClient.get<CarbonReport[]>(`/carbon-reports/farm/${farmId}`, {
    params,
  });
  return data;
}

/** GET /carbon-reports/{report_id} */
export async function getReportApi(reportId: number): Promise<CarbonReport> {
  const { data } = await apiClient.get<CarbonReport>(`/carbon-reports/${reportId}`);
  return data;
}

/**
 * POST /carbon-reports/generate/{crop_cycle_id}
 * Requires ≥7 sensor readings. Returns 400 with InsufficientReadingsError otherwise.
 */
export async function generateReportApi(cropCycleId: number): Promise<CarbonReport> {
  const { data } = await apiClient.post<CarbonReport>(
    `/carbon-reports/generate/${cropCycleId}`,
  );
  return data;
}

/**
 * POST /carbon-reports/{report_id}/submit
 * Transitions DRAFT → SUBMITTED and creates a VerificationRequest.
 */
export async function submitReportApi(reportId: number): Promise<CarbonReport> {
  const { data } = await apiClient.post<CarbonReport>(
    `/carbon-reports/${reportId}/submit`,
    {},
  );
  return data;
}
