import apiClient from './client';
import type { VerificationRequest } from '../types';

/** GET /verification/pending */
export async function getPendingVerificationsApi(): Promise<VerificationRequest[]> {
  const { data } = await apiClient.get<VerificationRequest[]>('/verification/pending');
  return data;
}

/** GET /verification/{id} */
export async function getVerificationApi(id: number): Promise<VerificationRequest> {
  const { data } = await apiClient.get<VerificationRequest>(`/verification/${id}`);
  return data;
}

/** POST /verification/{id}/approve */
export async function approveVerificationApi(
  id: number,
  remarks?: string,
): Promise<VerificationRequest> {
  const { data } = await apiClient.post<VerificationRequest>(`/verification/${id}/approve`, {
    remarks,
  });
  return data;
}

/** POST /verification/{id}/reject */
export async function rejectVerificationApi(
  id: number,
  remarks?: string,
): Promise<VerificationRequest> {
  const { data } = await apiClient.post<VerificationRequest>(`/verification/${id}/reject`, {
    remarks,
  });
  return data;
}
