// ─── Domain types mirroring GreenChain backend models ─────────────────────────

export type UserRole = 'FARMER' | 'FPO' | 'VERIFIER' | 'ADMIN';

export interface User {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  is_approved: boolean;
  wallet_address: string | null;
  created_at: string;
}

// ─── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
  role: UserRole;
}

// ─── Farm ──────────────────────────────────────────────────────────────────────

export type FarmStatus = 'DRAFT' | 'PENDING_APPROVAL' | 'APPROVED' | 'SUSPENDED' | 'ARCHIVED';

export interface Farm {
  id: number;
  farmer_id: number;
  fpo_id: number | null;
  farm_name: string;
  land_area_acres: number;
  latitude: number;
  longitude: number;
  village: string;
  district: string;
  state: string;
  soil_type: string;
  water_source: string;
  is_approved: boolean;
  is_deleted: boolean;
  // Phase 11 lifecycle
  farm_status: FarmStatus;
  approved_at: string | null;
  approved_by: number | null;
  archived_at: string | null;
  archive_reason: string | null;
  // Phase 11 GIS
  farm_boundary_geojson: string | null;
  boundary_area_hectares: number | null;
  boundary_area_acres: number | null;
  created_at: string;
}

export type CropCycleStatus = 'PLANNED' | 'ACTIVE' | 'HARVESTED' | 'VERIFIED' | 'CLOSED' | 'COMPLETED' | 'CANCELLED';

export interface CropCycle {
  id: number;
  farm_id: number;
  crop_type: string;
  season: string;
  start_date: string;
  end_date: string | null;
  baseline_method: string;
  reduction_practice: string;
  status: CropCycleStatus;
  // Phase 11 lifecycle
  harvest_date: string | null;
  closed_at: string | null;
  yield_quantity: number | null;
  yield_unit: string | null;
  created_at: string;
}

// ─── Sensor ────────────────────────────────────────────────────────────────────

export interface SensorReading {
  id: number;
  farm_id: number;
  crop_cycle_id: number | null;
  reading_time: string;
  soil_moisture: number;
  water_depth_cm: number;
  temperature_c: number;
  humidity: number;
  rainfall_mm: number;
  estimated_methane: number;
  data_quality_score: number;
  source_type: string;
}

// ─── Carbon Report ─────────────────────────────────────────────────────────────

export type ReportStatus = 'DRAFT' | 'SUBMITTED' | 'VERIFIED' | 'REJECTED';

export interface CarbonReport {
  id: number;
  farm_id: number;
  crop_cycle_id: number;
  baseline_methane_kg: number;
  current_methane_kg: number;
  methane_reduction_kg: number;
  co2e_reduction_tonnes: number;
  estimated_credits: number;
  report_hash: string;
  status: ReportStatus;
  created_at: string;
}

// ─── Token ─────────────────────────────────────────────────────────────────────

export type TokenStatus = 'MINTED' | 'RETIRED' | 'SUSPENDED';

export interface CarbonToken {
  id: number;
  carbon_report_id: number;
  farmer_id: number;
  token_id: string;
  token_standard: string;
  credit_amount: number;
  status: TokenStatus;
  minted_tx_hash: string;
  minted_at: string;
  created_at: string;
  is_certificate: boolean;
}

// ─── Verification ──────────────────────────────────────────────────────────────

export type VerificationStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'MANUAL_REVIEW';
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH';

export interface VerificationRequest {
  id: number;
  carbon_report_id: number;
  verifier_id: number | null;
  status: VerificationStatus;
  remarks: string | null;
  risk_score: number;
  risk_level: RiskLevel;
  recommendation: 'APPROVE' | 'MANUAL_REVIEW' | 'REJECT';
  verified_at: string | null;
  created_at: string;
  // Enriched fields from GET /verification/{id}
  risk_factors: string[];
  sensor_count: number | null;
  satellite_count: number | null;
  drone_count: number | null;
  avg_quality_score: number | null;
  num_evidence_files: number | null;
  baseline_methane_kg: number | null;
  current_methane_kg: number | null;
  methane_reduction_kg: number | null;
  co2e_reduction_tonnes: number | null;
  estimated_credits: number | null;
  verifier_name: string | null;
}

// ─── Satellite / Drone ─────────────────────────────────────────────────────────

export interface SatelliteObservation {
  id: number;
  farm_id: number;
  crop_cycle_id: number | null;
  observation_date: string;
  ndvi: number;
  ndwi: number;
  vegetation_health: 'POOR' | 'FAIR' | 'GOOD' | 'EXCELLENT';
  flood_risk: 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH';
  cloud_cover_percent: number;
  source: string;
  created_at: string;
}

export interface DroneObservation {
  id: number;
  farm_id: number;
  crop_cycle_id: number | null;
  observation_date: string;
  vegetation_cover_percent: number;
  standing_water_percent: number;
  anomaly_score: number;
  image_reference: string | null;
  created_at: string;
}

// ─── Dashboards ────────────────────────────────────────────────────────────────

export interface FarmerDashboard {
  my_farms_count: number;
  approved_farms_count: number;
  active_crop_cycles: number;
  total_sensor_readings: number;
  avg_sensor_quality: number;
  total_carbon_reports: number;
  verified_reports: number;
  token_count: number;
  total_credits: number;
  latest_mrv_confidence: number | null;
}

export interface FpoDashboard {
  linked_farms_count: number;
  approved_linked_farms: number;
  farmers_count: number;
  pending_reports: number;
  high_risk_farms: number;
}

export interface VerifierDashboard {
  pending_verifications: number;
  high_risk_reports: number;
  approved_today: number;
  rejected_today: number;
}

export interface AdminDashboard {
  total_farms: number;
  total_users: number;
  total_reports: number;
  verified_reports: number;
  total_tokens: number;
  total_credits: number;
  high_risk_reports: number;
}

export interface MobileDashboardResponse {
  success: boolean;
  message: string;
  data: {
    role: UserRole;
    data: FarmerDashboard | FpoDashboard | VerifierDashboard | AdminDashboard;
  };
}

// ─── System Status ─────────────────────────────────────────────────────────────

export interface SystemStatus {
  api_status: string;
  database_status: string;
  blockchain_mode: string;
  blockchain_configured: boolean;
  total_routes: number;
  timestamp: string;
}

// ─── Admin ─────────────────────────────────────────────────────────────────────

export interface TokenSummary {
  total_tokens: number;
  total_minted_credits: number;
  active_tokens: number;
  retired_tokens: number;
  suspended_tokens: number;
  zero_credit_certificates: number;
}

// ─── Pagination helper ─────────────────────────────────────────────────────────

export interface PaginationParams {
  limit?: number;
  offset?: number;
}

// ─── Phase 9 Custodial Model ───────────────────────────────────────────────────

export type CreditBalanceStatus = 'EARNED' | 'TOKENIZED' | 'DISTRIBUTED' | 'HELD' | 'CANCELLED';

export interface FarmerCreditBalance {
  id: number;
  farmer_id: number;
  fpo_id: number;
  carbon_report_id: number;
  carbon_token_id: number | null;
  credits_earned: number;
  credits_distributed: number;
  credits_available: number;
  status: CreditBalanceStatus;
  created_at: string;
  updated_at: string;
}

/** Enriched balance returned by GET /fpo/credits/farmers — includes farmer/farm info. */
export interface EnrichedFarmerCreditBalance extends FarmerCreditBalance {
  farmer_name: string | null;
  farmer_email: string | null;
  farm_name: string | null;
  farmer_payout_method: 'UPI' | 'BANK_TRANSFER' | null;
  farmer_upi_id: string | null;
}

export interface FarmerCreditSummary {
  farmer_id: number;
  total_earned: number;
  total_distributed: number;
  total_available: number;
  total_tokenized: number;
  balances: FarmerCreditBalance[];
}

export type PayoutStatus = 'INITIATED' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export interface Payout {
  id: number;
  farmer_id: number;
  fpo_id: number;
  credit_balance_id: number;
  amount_credits: number;
  price_per_credit: number;
  payout_amount: number;
  currency: string;
  payout_method: string | null;
  status: PayoutStatus;
  initiated_by: number;
  initiated_at: string;
  completed_at: string | null;
  remarks: string | null;
  // Phase 10B: provider tracking
  idempotency_key: string | null;
  provider_reference_id: string | null;   // RazorpayX pout_XXXX when live
}

export interface FarmerPayoutDetails {
  id: number;
  user_id: number;
  preferred_payout_method: 'UPI' | 'BANK_TRANSFER' | null;
  /** Phase 10A: raw UPI ID never returned — use upi_id_masked */
  upi_id_masked: string | null;
  bank_account_holder_name: string | null;
  bank_account_number_masked: string | null;
  ifsc_code: string | null;
  bank_name: string | null;
  /** Phase 10A: verification status */
  payout_details_verified: boolean;
  payout_details_verified_at: string | null;
  payout_verification_method: string | null;
  created_at: string;
  updated_at: string;
}

export interface FPOWallet {
  id: number;
  organization_name: string;
  wallet_address: string | null;
  /** Phase 10A: first6...last6 masked form for display */
  wallet_address_masked: string | null;
  vault_identifier: string | null;
  /** Phase 10A: verification fields */
  wallet_verified: boolean;
  wallet_verified_at: string | null;
  wallet_network: string | null;
}

export interface FPOWalletVerifyResponse {
  verified: boolean;
  wallet_address: string | null;
  wallet_address_masked: string | null;
  wallet_network: string | null;
  verified_at: string | null;
  message: string;
}

export interface FarmerBalanceRow {
  farmer_id: number;
  farmer_name: string;
  total_earned: number;
  total_available: number;
  total_distributed: number;
  balance_count: number;
}
