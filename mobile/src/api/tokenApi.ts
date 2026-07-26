import apiClient from './client';
import type { CarbonToken, TokenStatus, PaginationParams } from '../types';

interface TokenListParams extends PaginationParams {
  status?: TokenStatus;
}

/** GET /tokens/my-wallet */
export async function getMyWalletApi(params?: TokenListParams): Promise<CarbonToken[]> {
  const { data } = await apiClient.get<CarbonToken[]>('/tokens/my-wallet', { params });
  return data;
}

/** GET /tokens/{token_id} */
export async function getTokenApi(tokenId: number): Promise<CarbonToken> {
  const { data } = await apiClient.get<CarbonToken>(`/tokens/${tokenId}`);
  return data;
}

/** POST /fpo/tokens/mint/{report_id} — FPO mints custodial token */
export async function mintFPOTokenApi(reportId: number): Promise<CarbonToken> {
  const { data } = await apiClient.post<CarbonToken>(`/fpo/tokens/mint/${reportId}`);
  return data;
}

/**
 * GET /fpo/tokens/minted-report-ids
 * Returns carbon_report_id list for tokens already minted under this FPO.
 * FPO only. Replaces the FARMER-only getMyWalletApi for mint eligibility checks.
 */
export async function getFPOMintedReportIdsApi(): Promise<number[]> {
  const { data } = await apiClient.get<number[]>('/fpo/tokens/minted-report-ids');
  return data;
}
