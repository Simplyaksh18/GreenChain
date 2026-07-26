/**
 * gisApi.ts — Phase 12 GIS client
 *
 * All calls go to GreenChain backend /gis/* endpoints.
 * No direct calls to Copernicus, Bhuvan, or Bhoonidhi from mobile.
 */
import apiClient from './client';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface GISProviderStatus {
  copernicus: { configured: boolean };
  bhuvan:     { configured: boolean };
  bhoonidhi:  { configured: boolean };
  mock_fallback_enabled: boolean;
  active_provider: string | null;
  mock_mode: boolean;
}

export interface NormalizedIndices {
  ndvi: number | null;
  ndwi: number | null;
  [key: string]: number | null;
}

export interface NormalizedMetadata {
  cloud_cover: number | null;
  source_scene_id: string | null;
  resolution_m: number | null;
  satellite: string | null;
  [key: string]: unknown;
}

export interface NormalizedScene {
  provider: string;
  is_mock: boolean;
  farm_id: number | null;
  crop_cycle_id: number | null;
  geometry: object | null;
  bbox: number[] | null;
  observation_date: string | null;
  indices: NormalizedIndices;
  metadata: NormalizedMetadata;
}

export interface SatelliteSearchResult {
  provider: string | null;
  is_mock: boolean;
  scenes: NormalizedScene[];
  count: number;
  error?: string;
  requested_indices?: string[];
  /**
   * "BOUNDARY"            — satellite search AOI is the saved farm polygon
   * "CENTER_POINT_BUFFER" — no boundary saved; AOI is a buffer around farm centre
   */
  aoi_source?: 'BOUNDARY' | 'CENTER_POINT_BUFFER';
  /** Human-readable warning shown when aoi_source === "CENTER_POINT_BUFFER" */
  aoi_warning?: string | null;
  /** Bounding box [west, south, east, north] of the AOI used */
  bbox?: number[];
}

export interface FarmMapData {
  farm_id: number;
  farm_name: string;
  marker: { latitude: number; longitude: number };
  bbox: number[];
  has_boundary: boolean;
  /** GeoJSON object (dict) returned by backend — never a raw JSON string. */
  farm_boundary_geojson: Record<string, unknown> | null;
  /** Convenience alias for farm_boundary_geojson — both fields are present from backend. */
  boundary?: Record<string, unknown> | null;
  boundary_area_hectares: number | null;
  boundary_area_acres: number | null;
  land_area_acres: number;
  satellite_summary: {
    provider: string | null;
    is_mock: boolean;
    scene_count: number;
    latest_scene: NormalizedScene | null;
  };
}

export interface FarmBoundaryData {
  farm_id: number;
  farm_name: string;
  latitude: number;
  longitude: number;
  has_boundary: boolean;
  /** GeoJSON object (dict) returned by backend — never a raw JSON string. */
  farm_boundary_geojson: Record<string, unknown> | null;
  /** Convenience alias — same value as farm_boundary_geojson. */
  boundary?: Record<string, unknown> | null;
  boundary_area_hectares: number | null;
  boundary_area_acres: number | null;
  computed_area: {
    area_m2: number;
    area_hectares: number;
    area_acres: number;
  } | null;
}

export interface BoundaryValidationResult {
  valid: boolean;
  area_m2: number | null;
  area_hectares: number | null;
  area_acres: number | null;
  area_warning: string | null;
  error: string | null;
}

export interface SaveBoundaryPayload {
  farm_boundary_geojson: string;
  boundary_area_hectares?: number;
  boundary_area_acres?: number;
}

// ── API functions ─────────────────────────────────────────────────────────────

/** GET /gis/providers/status — configuration state, no secrets exposed */
export async function getGISProviderStatus(): Promise<GISProviderStatus> {
  const { data } = await apiClient.get<GISProviderStatus>('/gis/providers/status');
  return data;
}

/** GET /gis/providers/health — FPO/Admin only — live connectivity check */
export async function getGISProviderHealth(): Promise<Record<string, unknown>> {
  const { data } = await apiClient.get('/gis/providers/health');
  return data;
}

/** GET /gis/farms/{farmId}/map-data — one-shot map payload */
export async function getFarmMapData(farmId: number): Promise<FarmMapData> {
  const { data } = await apiClient.get<FarmMapData>(`/gis/farms/${farmId}/map-data`);
  return data;
}

/** GET /gis/farms/{farmId}/boundary — boundary + computed area */
export async function getFarmBoundary(farmId: number): Promise<FarmBoundaryData> {
  const { data } = await apiClient.get<FarmBoundaryData>(`/gis/farms/${farmId}/boundary`);
  return data;
}

/**
 * Save boundary — PATCH /farms/{farmId}/boundary
 * Returns FarmBoundaryData so mobile can immediately confirm the saved polygon
 * without a separate GET call. Both `farm_boundary_geojson` and `boundary`
 * fields carry the saved GeoJSON dict; `has_boundary` confirms persistence.
 */
export async function saveFarmBoundary(
  farmId: number,
  payload: SaveBoundaryPayload,
): Promise<FarmBoundaryData> {
  const { data } = await apiClient.patch<FarmBoundaryData>(`/farms/${farmId}/boundary`, payload);
  return data;
}

/** POST /gis/farms/{farmId}/boundary/validate — validate without saving */
export async function validateFarmBoundary(
  farmId: number,
  geojson: string,
): Promise<BoundaryValidationResult> {
  const { data } = await apiClient.post<BoundaryValidationResult>(
    `/gis/farms/${farmId}/boundary/validate`,
    { farm_boundary_geojson: geojson },
  );
  return data;
}

/** POST /gis/satellite/search */
export async function searchSatelliteScenes(payload: {
  farm_id: number;
  provider?: string;
  start_date: string;
  end_date: string;
  cloud_cover_max?: number;
}): Promise<SatelliteSearchResult> {
  const { data } = await apiClient.post<SatelliteSearchResult>(
    '/gis/satellite/search',
    { provider: 'AUTO', cloud_cover_max: 30, ...payload },
  );
  return data;
}

/** POST /gis/satellite/indices */
export async function getSatelliteIndices(payload: {
  farm_id: number;
  crop_cycle_id?: number;
  provider?: string;
  indices?: string[];
  start_date: string;
  end_date: string;
}): Promise<SatelliteSearchResult> {
  const { data } = await apiClient.post<SatelliteSearchResult>(
    '/gis/satellite/indices',
    { provider: 'AUTO', indices: ['NDVI', 'NDWI'], ...payload },
  );
  return data;
}
