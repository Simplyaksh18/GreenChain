/**
 * aiApi.ts — Phase 18 AI Layer API client.
 *
 * Thin wrappers around the 4 AI endpoints. All calls are read-only.
 * Responses always include `disclaimer` and `ai_mode`.
 */

import apiClient from './client';

// ── Shared types ──────────────────────────────────────────────────────────────

export interface AIInsight {
  type: 'info' | 'positive' | 'warning' | 'risk' | 'action';
  title?: string;
  message: string;
}

const DISCLAIMER =
  'AI-generated assistance. Final decision is based on verified MRV records and human judgment.';

// ── MRV Summary ───────────────────────────────────────────────────────────────

export interface MRVSummaryResponse {
  farm_id: number;
  farm_name: string;
  has_carbon_report: boolean;
  latest_report_id: number | null;
  report_status: string | null;
  summary: string | null;
  insights: AIInsight[];
  data_completeness: number;
  data_completeness_pct: number;   // backward-compat alias
  confidence_label: string;        // "High" / "Medium" / "Low"
  confidence_level: 'HIGH' | 'MEDIUM' | 'LOW';
  next_best_action: string;
  ai_mode: string;
  disclaimer: string;
}

export async function getMRVSummary(farmId: number): Promise<MRVSummaryResponse> {
  const res = await apiClient.post<MRVSummaryResponse>(`/ai/mrv-summary/${farmId}`);
  return res.data;
}

// ── Verification Assist ───────────────────────────────────────────────────────

export interface VerificationAssistResponse {
  verification_request_id: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  risk_explanation: string;
  evidence_checklist: string[];
  fraud_flags: string[];
  suggested_questions: string[];
  recommendation: 'APPROVE' | 'REVIEW' | 'REJECT';
  recommendation_note: string;
  ai_mode: string;
  disclaimer: string;
}

export async function getVerificationAssist(
  verificationRequestId: number,
): Promise<VerificationAssistResponse> {
  const res = await apiClient.post<VerificationAssistResponse>(
    `/ai/verification-assist/${verificationRequestId}`,
  );
  return res.data;
}

// ── FPO Action Summary ────────────────────────────────────────────────────────

export interface FPOActionItem {
  category: string;
  count: number;
  message: string;
  action?: string;
}

export interface FPOActionSummaryResponse {
  action_items: FPOActionItem[];
  summary: string;
  ai_mode: string;
  disclaimer: string;
}

export async function getFPOActionSummary(): Promise<FPOActionSummaryResponse> {
  const res = await apiClient.post<FPOActionSummaryResponse>('/ai/fpo/action-summary');
  return res.data;
}

// ── Farmer Help ───────────────────────────────────────────────────────────────

export type FarmerHelpTopic =
  | 'explain_credits'
  | 'why_zero_credits'
  | 'missing_data'
  | 'improve_mrv'
  | 'general';

export interface FarmerHelpRequest {
  topic: FarmerHelpTopic;
  farm_id?: number;
  report_id?: number;
}

export interface FarmerHelpResponse {
  topic: string;
  explanation: string;
  insights: AIInsight[];
  ai_mode: string;
  disclaimer: string;
}

export async function getFarmerHelp(
  payload: FarmerHelpRequest,
): Promise<FarmerHelpResponse> {
  const res = await apiClient.post<FarmerHelpResponse>('/ai/farmer/help', payload);
  return res.data;
}

export { DISCLAIMER };
