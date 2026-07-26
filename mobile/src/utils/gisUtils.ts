/**
 * gisUtils.ts — Shared GIS coordinate conversion utilities
 *
 * Coordinate conventions used throughout this codebase:
 *   GeoJSON  → coordinates are [longitude, latitude]   (longitude first)
 *   MapView  → coordinates are { latitude, longitude } (latitude first)
 *
 * These are opposite — NEVER pass a GeoJSON coordinate array directly to
 * react-native-maps, and NEVER build a GeoJSON ring from { latitude, longitude }
 * without swapping the order.
 *
 * All functions here are pure and coordinate-agnostic — they work for any valid
 * WGS84 polygon anywhere on Earth.
 */

// ── Point type used by react-native-maps ─────────────────────────────────────

export type MapPoint = { latitude: number; longitude: number };

// ── GeoJSON Polygon → MapView coordinate array ───────────────────────────────
/**
 * Convert a GeoJSON Polygon object (or stringified JSON) to an array of
 * react-native-maps MapPoint values.
 *
 * Handles:
 *   - `{ type: "Polygon", coordinates: [ring, ...] }`
 *   - `{ type: "Feature", geometry: { type: "Polygon", ... } }`
 *   - Already-parsed dict (backend returns a dict, never a raw string after Phase 12 fix)
 *   - Stringified fallback (legacy / defensive)
 *   - Duplicate closing point is removed (GeoJSON ring closes by repeating first vertex)
 *   - Returns [] on any parse error — never throws
 *
 * GeoJSON ring: [longitude, latitude] per position
 * Output:       { latitude, longitude } per point
 */
export function geoJsonPolygonToMapPoints(
  geojson: Record<string, any> | string | null | undefined,
): MapPoint[] {
  if (!geojson) return [];

  try {
    // Support both already-parsed dict and legacy stringified value
    const raw: Record<string, any> =
      typeof geojson === 'string' ? JSON.parse(geojson) : geojson;

    if (!raw) return [];

    // Unwrap GeoJSON Feature wrapper if present
    const geometry: Record<string, any> =
      raw.type === 'Feature' ? raw.geometry : raw;

    if (!geometry || geometry.type !== 'Polygon') return [];

    const ring: number[][] = Array.isArray(geometry.coordinates?.[0])
      ? geometry.coordinates[0]
      : [];

    if (ring.length === 0) return [];

    // GeoJSON: [longitude, latitude]  →  MapView: { latitude, longitude }
    const points: MapPoint[] = ring
      .map(([lng, lat]: number[]) => ({
        latitude: Number(lat),
        longitude: Number(lng),
      }))
      .filter(
        (p) =>
          Number.isFinite(p.latitude) &&
          Number.isFinite(p.longitude) &&
          p.latitude >= -90 &&
          p.latitude <= 90 &&
          p.longitude >= -180 &&
          p.longitude <= 180,
      );

    // Remove duplicate closing vertex (GeoJSON rings close by repeating first point)
    if (
      points.length > 1 &&
      points[0].latitude === points[points.length - 1].latitude &&
      points[0].longitude === points[points.length - 1].longitude
    ) {
      return points.slice(0, -1);
    }

    return points;
  } catch {
    // Never crash on malformed input
    return [];
  }
}

// ── Polygon centroid ──────────────────────────────────────────────────────────
/**
 * Compute the arithmetic centroid of an array of MapPoints.
 * Excludes the duplicate closing vertex if present.
 * Returns null if the array is empty or produces non-finite results.
 */
export function polygonCentroid(points: MapPoint[]): MapPoint | null {
  if (points.length === 0) return null;

  // Exclude duplicate closing vertex if the ring is closed
  const pts =
    points.length > 1 &&
    points[0].latitude === points[points.length - 1].latitude &&
    points[0].longitude === points[points.length - 1].longitude
      ? points.slice(0, -1)
      : points;

  const lat = pts.reduce((sum, p) => sum + p.latitude, 0) / pts.length;
  const lng = pts.reduce((sum, p) => sum + p.longitude, 0) / pts.length;

  return Number.isFinite(lat) && Number.isFinite(lng)
    ? { latitude: lat, longitude: lng }
    : null;
}
