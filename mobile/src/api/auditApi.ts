/**
 * auditApi.ts — Phase 13 / Phase 14 Evidence & Audit Trail client
 *
 * Endpoints:
 *   POST   /evidence                          — upload evidence (URL-based)
 *   POST   /evidence/upload                   — multipart binary upload (Phase 14)
 *   GET    /evidence/farm/{farmId}            — evidence for a farm
 *   GET    /evidence/crop-cycle/{cycleId}     — evidence for a crop cycle
 *   GET    /evidence/report/{reportId}        — evidence linked to a report
 *   GET    /evidence/{id}/verify              — verify evidence hash
 *   GET    /audit/farms/{farmId}/full-report  — full auditable farm package
 *   GET    /audit/reports/{reportId}/package  — report-level audit package
 *   POST   /mrv/import/sensor-csv            — Phase 14 sensor CSV import
 *   POST   /mrv/import/satellite-csv         — Phase 14 satellite CSV import
 *   POST   /mrv/import/drone-csv             — Phase 14 drone CSV import
 *   POST   /mrv/import/farm-boundary-geojson — Phase 14 GIS boundary import
 *   POST   /mrv/import/satellite-geojson     — Phase 14 satellite GeoJSON import
 *
 * SECURITY: No keys, secrets, or raw payout details are returned.
 * Idempotency keys are shortened (last 8 chars only).
 * Transaction hashes are truncated for display.
 */
import apiClient from './client';

// ── Evidence types ─────────────────────────────────────────────────────────────

export type EvidenceTypeName =
  | 'PHOTO' | 'VIDEO' | 'PDF' | 'DOCUMENT'
  | 'SENSOR_EXPORT' | 'SATELLITE_EXPORT' | 'DRONE_EXPORT'
  | 'GIS_BOUNDARY' | 'OTHER';

export interface EvidenceFile {
  id: number;
  farm_id: number;
  crop_cycle_id: number | null;
  carbon_report_id: number | null;
  uploaded_by: number;
  evidence_type: EvidenceTypeName | null;
  file_type: string;
  file_name: string | null;
  file_mime_type: string | null;
  file_size: number | null;
  file_url: string;
  storage_path: string | null;
  description: string | null;
  file_hash: string | null;
  hash_algorithm: string | null;
  created_at: string;
}

export interface EvidenceVerifyResult {
  evidence_id: number;
  stored_hash: string | null;
  recomputed_hash: string;
  hash_algorithm: string;
  hash_match: boolean;
  verified_at: string;
}

export interface EvidenceUploadPayload {
  farm_id: number;
  crop_cycle_id?: number;
  carbon_report_id?: number;
  file_url: string;
  file_type: string;
  evidence_type?: string;
  description?: string;
  file_name?: string;
  file_mime_type?: string;
  file_size?: number;
}

export interface EvidenceUploadSummary {
  id: number;
  farm_id: number;
  crop_cycle_id: number | null;
  carbon_report_id: number | null;
  evidence_type: string | null;
  file_name: string | null;
  file_mime_type: string | null;
  file_size: number | null;
  file_hash: string;
  hash_algorithm: string;
  file_url: string;
  description: string | null;
  created_at: string;
}

// ── MRV Import types ───────────────────────────────────────────────────────────

export interface MrvImportResult {
  success: boolean;
  rows_received: number;
  rows_inserted: number;
  duplicates_skipped: number;
  invalid_rows: number;
  errors: string[];
}

export interface BoundaryImportResult {
  success: boolean;
  farm_id: number;
  boundary_area_hectares: number;
  boundary_area_acres: number;
  file_hash: string;
  message: string;
}

// ── Audit types ────────────────────────────────────────────────────────────────

export interface MethaneDiagnostics {
  baseline_methane_kg: number;
  current_methane_kg: number;
  methane_reduction_kg: number;
  co2e_reduction_tonnes: number;
  gwp_factor_used: number;
  formula: string;
  estimated_credits: number;
  input_sensor_count: number;
  sensor_quality_average: number | null;
  satellite_observation_count: number;
}

export interface AuditVerification {
  id: number;
  status: string;
  risk_score: number;
  risk_level: string;
  recommendation: string;
  remarks: string | null;
  verifier_name: string | null;
  verified_at: string | null;
  created_at: string;
}

export interface AuditBlockchainTx {
  id: number;
  action_type: string;
  tx_hash: string | null;          // truncated
  blockchain_network: string;
  contract_address: string | null; // truncated
  created_at: string;
}

export interface AuditToken {
  id: number;
  token_id: string;
  token_standard: string;
  credit_amount: number;
  status: string;
  minted_tx_hash: string | null;   // truncated
  minted_at: string | null;
}

export interface AuditPayout {
  id: number;
  amount_credits: number;
  price_per_credit: number;
  payout_amount: number;
  currency: string;
  status: string;
  payout_method: string | null;
  provider_reference_id: string | null;
  idempotency_key_suffix: string | null;
  initiated_at: string;
  completed_at: string | null;
  remarks: string | null;
}

export interface AuditSocReport {
  id: number;
  crop_cycle_id: number;
  baseline_soc: number;
  current_soc: number;
  soc_gain: number;
  soc_co2e: number;
  soc_credits: number;
  confidence_score: number;
  is_informational_only: true;
  note: string;
  created_at: string;
}

export interface FarmAuditReport {
  generated_at: string;
  farm: {
    id: number;
    farm_name: string;
    village: string;
    district: string;
    state: string;
    land_area_acres: number;
    soil_type: string;
    water_source: string;
    farm_status: string;
    fpo_name: string | null;
    boundary_area_hectares: number | null;
  };
  crop_cycles: Array<{
    id: number;
    crop_type: string;
    season: string;
    start_date: string | null;
    end_date: string | null;
    baseline_method: string;
    reduction_practice: string;
    status: string;
  }>;
  carbon_reports: Array<{
    carbon_report: { id: number; status: string; report_hash: string | null; created_at: string };
    methane_diagnostics: MethaneDiagnostics;
    soc_report: AuditSocReport | null;
    crop_cycle: object | null;
    evidence: EvidenceFile[];
    verification_history: AuditVerification[];
    blockchain_transactions: AuditBlockchainTx[];
    token: AuditToken | null;
  }>;
  soc_reports: AuditSocReport[];
  evidence: EvidenceFile[];
  payouts: AuditPayout[];
  methodology: {
    methane: Record<string, unknown>;
    soc: Record<string, unknown>;
  };
}

export interface ReportAuditPackage {
  generated_at: string;
  farm_id: number;
  farm_name: string;
  carbon_report: { id: number; status: string; report_hash: string | null; created_at: string };
  methane_diagnostics: MethaneDiagnostics;
  soc_report: AuditSocReport | null;
  crop_cycle: object | null;
  evidence: EvidenceFile[];
  verification_history: AuditVerification[];
  blockchain_transactions: AuditBlockchainTx[];
  token: AuditToken | null;
  methodology: {
    methane: Record<string, unknown>;
    soc: Record<string, unknown>;
  };
}

// ── Evidence API functions ─────────────────────────────────────────────────────

/** POST /evidence (URL-based) */
export async function uploadEvidence(
  payload: EvidenceUploadPayload,
): Promise<EvidenceFile> {
  const { data } = await apiClient.post<EvidenceFile>('/evidence', payload);
  return data;
}

/**
 * POST /evidence/upload (multipart binary — Phase 14)
 * @param uri      local file URI from expo-image-picker / expo-document-picker
 * @param fileName original file name
 * @param mimeType MIME type
 */
export async function uploadEvidenceFile(opts: {
  farmId: number;
  cropCycleId?: number;
  carbonReportId?: number;
  evidenceType: string;
  description?: string;
  uri: string;
  fileName: string;
  mimeType: string;
}): Promise<EvidenceUploadSummary> {
  const form = new FormData();
  form.append('farm_id', String(opts.farmId));
  if (opts.cropCycleId != null) form.append('crop_cycle_id', String(opts.cropCycleId));
  if (opts.carbonReportId != null) form.append('carbon_report_id', String(opts.carbonReportId));
  form.append('evidence_type', opts.evidenceType);
  if (opts.description) form.append('description', opts.description);
  // React Native FormData: append file as object with uri/name/type
  form.append('file', { uri: opts.uri, name: opts.fileName, type: opts.mimeType } as any);

  const { data } = await apiClient.post<EvidenceUploadSummary>('/evidence/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

/** GET /evidence/farm/{farmId} */
export async function getEvidenceByFarm(farmId: number): Promise<EvidenceFile[]> {
  const { data } = await apiClient.get<EvidenceFile[]>(`/evidence/farm/${farmId}`);
  return data;
}

/** GET /evidence/crop-cycle/{cycleId} */
export async function getEvidenceByCycle(cycleId: number): Promise<EvidenceFile[]> {
  const { data } = await apiClient.get<EvidenceFile[]>(`/evidence/crop-cycle/${cycleId}`);
  return data;
}

/** GET /evidence/report/{reportId} */
export async function getEvidenceByReport(reportId: number): Promise<EvidenceFile[]> {
  const { data } = await apiClient.get<EvidenceFile[]>(`/evidence/report/${reportId}`);
  return data;
}

/** GET /evidence/{id}/verify */
export async function verifyEvidenceHash(
  evidenceId: number,
): Promise<EvidenceVerifyResult> {
  const { data } = await apiClient.get<EvidenceVerifyResult>(
    `/evidence/${evidenceId}/verify`,
  );
  return data;
}

// ── Audit API functions ────────────────────────────────────────────────────────

/** GET /audit/farms/{farmId}/full-report */
export async function getFarmAuditReport(
  farmId: number,
): Promise<FarmAuditReport> {
  const { data } = await apiClient.get<FarmAuditReport>(
    `/audit/farms/${farmId}/full-report`,
  );
  return data;
}

/** GET /audit/reports/{reportId}/package */
export async function getReportAuditPackage(
  reportId: number,
): Promise<ReportAuditPackage> {
  const { data } = await apiClient.get<ReportAuditPackage>(
    `/audit/reports/${reportId}/package`,
  );
  return data;
}

// ── MRV Import API functions — Phase 14 ───────────────────────────────────────

async function _mrvImport(
  path: string,
  farmId: number,
  cropCycleId: number | undefined,
  uri: string,
  fileName: string,
): Promise<MrvImportResult> {
  const form = new FormData();
  form.append('farm_id', String(farmId));
  if (cropCycleId != null) form.append('crop_cycle_id', String(cropCycleId));
  form.append('file', { uri, name: fileName, type: 'text/csv' } as any);
  const { data } = await apiClient.post<MrvImportResult>(path, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function importSensorCsv(
  farmId: number, cropCycleId: number, uri: string, fileName: string,
): Promise<MrvImportResult> {
  return _mrvImport('/mrv/import/sensor-csv', farmId, cropCycleId, uri, fileName);
}

export async function importSatelliteCsv(
  farmId: number, cropCycleId: number, uri: string, fileName: string,
): Promise<MrvImportResult> {
  return _mrvImport('/mrv/import/satellite-csv', farmId, cropCycleId, uri, fileName);
}

export async function importDroneCsv(
  farmId: number, cropCycleId: number, uri: string, fileName: string,
): Promise<MrvImportResult> {
  return _mrvImport('/mrv/import/drone-csv', farmId, cropCycleId, uri, fileName);
}

export async function importFarmBoundaryGeoJson(
  farmId: number, uri: string, fileName: string,
): Promise<BoundaryImportResult> {
  const form = new FormData();
  form.append('farm_id', String(farmId));
  form.append('file', { uri, name: fileName, type: 'application/json' } as any);
  const { data } = await apiClient.post<BoundaryImportResult>(
    '/mrv/import/farm-boundary-geojson', form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

export async function importSatelliteGeoJson(
  farmId: number, cropCycleId: number, uri: string, fileName: string,
): Promise<MrvImportResult> {
  const form = new FormData();
  form.append('farm_id', String(farmId));
  form.append('crop_cycle_id', String(cropCycleId));
  form.append('file', { uri, name: fileName, type: 'application/json' } as any);
  const { data } = await apiClient.post<MrvImportResult>(
    '/mrv/import/satellite-geojson', form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}
