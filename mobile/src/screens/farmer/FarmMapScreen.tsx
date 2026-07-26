/**
 * FarmMapScreen — Phase 12 (fix: boundary rendering + fitToCoordinates + AOI info)
 *
 * Fixes in this revision:
 * 1. Saved boundary now renders on map open.
 *    Root cause: animateToRegion(farmCoord) centers on the farm pin but does not
 *    fit the polygon. When a boundary exists, fitToCoordinates() is used instead,
 *    which auto-zooms to encompass the full polygon regardless of its size/location.
 *
 * 2. Shared geoJsonPolygonToMapPoints() utility (gisUtils.ts) replaces inline
 *    conversion code. All GeoJSON [lon,lat] → { latitude, longitude } conversion
 *    happens in one place.
 *
 * 3. "Why draw a boundary?" info card shown when no boundary exists.
 *
 * 4. All existing crash fixes are preserved:
 *    - normalizeCoordinate() guards farm marker against null/string/swapped values.
 *    - mapRef.animateToRegion() used (not initialRegion) for reliable centering.
 *    - pointerEvents="box-none" on infoBar overlay.
 *
 * GeoJSON ↔ MapView convention (NEVER confuse these):
 *   GeoJSON ring: [longitude, latitude]   (longitude first)
 *   MapView:      { latitude, longitude } (latitude first)
 */
import React, { useCallback, useRef, useState, useEffect } from 'react';
import {
  StyleSheet,
  View,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import MapView, {
  Marker,
  Polygon,
  Circle,
  PROVIDER_DEFAULT,
  type Region,
} from 'react-native-maps';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';
import { getFarmMapData, type FarmMapData } from '../../api/gisApi';
import { GlassCard } from '../../components/GlassCard';
import { geoJsonPolygonToMapPoints } from '../../utils/gisUtils';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'FarmMap'>;

// ── Coordinate normalization ───────────────────────────────────────────────────
// Used for the farm marker only. Coerces unknown types to number, validates WGS84.
function normalizeCoordinate(
  lat: unknown,
  lng: unknown,
): { latitude: number; longitude: number } | null {
  const latitude  = Number(lat);
  const longitude = Number(lng);

  if (!Number.isFinite(latitude)  || !Number.isFinite(longitude))  return null;
  if (latitude  < -90  || latitude  > 90)  return null;
  if (longitude < -180 || longitude > 180) return null;

  return { latitude, longitude };
}

export function FarmMapScreen({ navigation, route }: Props) {
  const { farmId, farmName } = route.params;

  const mapRef = useRef<MapView>(null);

  const [mapData,    setMapData]    = useState<FarmMapData | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState('');
  // `farmCoord` is the validated, number-typed farm marker location.
  const [farmCoord, setFarmCoord]   = useState<{ latitude: number; longitude: number } | null>(null);

  const fetchData = useCallback(async () => {
    // Reset loading so stale mapData is not rendered while refetching.
    // This also re-triggers the positioning useEffect after fresh data arrives.
    setLoading(true);
    setError('');

    if (__DEV__) console.log('FarmMap opened', { routeFarmId: farmId }); // eslint-disable-line no-console

    try {
      const data = await getFarmMapData(farmId);

      // Normalize marker coordinate — guards against strings, NaN, swapped lat/lon
      const coord = normalizeCoordinate(data.marker?.latitude, data.marker?.longitude);

      if (__DEV__) {
        // ── Diagnostic logs — confirm exact response from backend ──────────────
        // eslint-disable-next-line no-console
        console.log('FarmMap mapData raw:', JSON.stringify(data, null, 2));
        // eslint-disable-next-line no-console
        console.log('FarmMap boundary fields:', {
          hasBoundary: !!data?.boundary,
          hasFarmBoundaryGeojson: !!data?.farm_boundary_geojson,
          boundaryType: (data?.boundary as any)?.type,
          farmBoundaryType: (data?.farm_boundary_geojson as any)?.type,
        });
        const rawForLog = (data?.boundary ?? data?.farm_boundary_geojson) as Record<string, any> | null;
        // eslint-disable-next-line no-console
        console.log('FarmMap converted polygon points:',
          rawForLog ? geoJsonPolygonToMapPoints(rawForLog) : []);
        // eslint-disable-next-line no-console
        console.log('FarmMap loaded mapData', {
          requestedFarmId: farmId,
          returnedFarmId: data?.farm_id,
          farmName: data?.farm_name,
          hasBoundary: !!(data?.boundary ?? data?.farm_boundary_geojson),
        });
      }

      // Commit all state in one batch — prevents stale renders between setMapData
      // and setFarmCoord, and ensures boundaryCoords memo recomputes before the
      // positioning useEffect fires.
      setMapData(data);
      setFarmCoord(coord);
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? 'Failed to load map data.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [farmId]);

  useFocusEffect(useCallback(() => { fetchData(); }, [fetchData]));

  // Parse saved boundary GeoJSON into MapView coordinates.
  //
  // Dual-field fallback: backend returns both `boundary` and `farm_boundary_geojson`
  // (both are the same parsed dict). We try `boundary` first, then fall back to
  // `farm_boundary_geojson`, so the render is correct regardless of which field the
  // backend populates — preventing the badge/polygon mismatch where `has_boundary`
  // is true but one specific field happens to be null.
  //
  // Always returns a plain array — never null — so `hasRenderableBoundary` is a
  // clean boolean derived from `.length >= 3`.
  //
  // geoJsonPolygonToMapPoints converts GeoJSON [lon, lat] → { latitude, longitude },
  // unwraps Feature objects, removes the duplicate closing vertex, and never throws.
  const boundaryCoords = React.useMemo((): { latitude: number; longitude: number }[] => {
    const raw = (mapData?.boundary ?? mapData?.farm_boundary_geojson) as Record<string, any> | null;
    if (!raw) return [];
    return geoJsonPolygonToMapPoints(raw);
  }, [mapData?.boundary, mapData?.farm_boundary_geojson]);

  // Single source of truth for "do we have a renderable polygon?"
  // Used to switch between Polygon and fallback Circle, and to decide
  // whether to use fitToCoordinates vs animateToRegion.
  const hasRenderableBoundary = boundaryCoords.length >= 3;

  // Position the map after data loads:
  //   - boundary exists → fitToCoordinates (shows the full polygon regardless of size)
  //   - no boundary     → animateToRegion (centers on farm marker with fixed zoom)
  //
  // This effect fires when farmCoord or boundaryCoords changes — i.e. after each
  // successful fetch. On re-focus after BoundaryEditor saves a new polygon,
  // boundaryCoords will have changed and the map will re-fit automatically.
  useEffect(() => {
    // Only position the map once we have a valid farm coordinate and loading is done.
    if (!farmCoord || loading) return;

    const t = setTimeout(() => {
      if (hasRenderableBoundary) {
        // Fit the camera to the boundary polygon so the full polygon is visible.
        // Bottom padding (260 pt) accounts for the info card overlay.
        // Only runs when mapRef is mounted and boundary points exist.
        mapRef.current?.fitToCoordinates(boundaryCoords, {
          edgePadding: { top: 80, right: 40, bottom: 260, left: 40 },
          animated: true,
        });
      } else {
        // No boundary — centre on farm marker
        const region: Region = {
          latitude:      farmCoord.latitude,
          longitude:     farmCoord.longitude,
          latitudeDelta:  0.04,
          longitudeDelta: 0.04,
        };
        mapRef.current?.animateToRegion(region, 400);
      }
    }, 300);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [farmCoord, loading, hasRenderableBoundary]);

  // ── Render states ─────────────────────────────────────────────────────────

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#2e7d32" />
        <Text variant="bodyMedium" style={styles.loadingText}>Loading map…</Text>
      </View>
    );
  }

  if (error && !farmCoord) {
    return (
      <View style={styles.centered}>
        <MaterialCommunityIcons name="map-marker-off" size={48} color="#c62828" />
        <Text variant="bodyMedium" style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={fetchData}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!farmCoord) {
    return (
      <View style={styles.centered}>
        <MaterialCommunityIcons name="map-marker-alert" size={48} color="#f57f17" />
        <Text variant="bodyMedium" style={styles.errorText}>
          Farm coordinates are invalid. Please update the farm location.
        </Text>
      </View>
    );
  }

  // ── Google Maps API key guard ──────────────────────────────────────────────
  // EXPO_PUBLIC_GOOGLE_MAPS_ANDROID_API_KEY must be set in mobile/.env AND the APK
  // must be rebuilt so EAS embeds it in AndroidManifest.xml via
  // expo.android.config.googleMaps.apiKey (app.config.js).
  //
  // Without a key, com.google.android.gms.maps throws a fatal exception on first render.
  // We catch the missing state here and show a message instead of crashing.
  //
  // To fix:
  //   1. Enable Maps SDK for Android in Google Cloud Console.
  //   2. Create an API key restricted to package com.greenchain.app + your SHA-1.
  //   3. Add to mobile/.env: EXPO_PUBLIC_GOOGLE_MAPS_ANDROID_API_KEY=<key>
  //   4. Rebuild: eas build -p android --profile development
  const mapsApiKey = process.env.EXPO_PUBLIC_GOOGLE_MAPS_ANDROID_API_KEY;
  if (!mapsApiKey) {
    return (
      <View style={styles.centered}>
        <MaterialCommunityIcons name="map-marker-off" size={48} color="#f57f17" />
        <Text variant="titleMedium" style={[styles.errorText, { marginBottom: 8 }]}>
          Google Maps API key not configured.
        </Text>
        <Text variant="bodySmall" style={styles.mapsKeyHint}>
          Add EXPO_PUBLIC_GOOGLE_MAPS_ANDROID_API_KEY to mobile/.env{'\n'}
          (Maps SDK for Android, restricted to com.greenchain.app),{'\n'}
          then rebuild the APK with eas build -p android --profile development.
        </Text>
      </View>
    );
  }

  // Safe initialRegion — used only on first mount before fitToCoordinates/animateToRegion fires.
  // Always derived from validated farm coordinates — never a hardcoded regional fallback.
  const safeInitialRegion: Region = {
    latitude:      farmCoord.latitude,
    longitude:     farmCoord.longitude,
    latitudeDelta:  hasRenderableBoundary ? 0.015 : 0.04,
    longitudeDelta: hasRenderableBoundary ? 0.015 : 0.04,
  };

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <MapView
        ref={mapRef}
        style={styles.map}
        provider={PROVIDER_DEFAULT}
        initialRegion={safeInitialRegion}
        showsUserLocation={false}
        showsMyLocationButton={false}
      >
        {/* Farm marker — always at validated farmCoord */}
        <Marker
          coordinate={farmCoord}
          title={farmName}
          description={
            mapData?.boundary_area_acres
              ? `${mapData.boundary_area_acres.toFixed(2)} acres`
              : `${mapData?.land_area_acres?.toFixed(2) ?? '?'} acres (registered)`
          }
          pinColor="#2e7d32"
        />

        {/*
          Boundary polygon — shown when a saved boundary exists and was parsed
          into 3+ valid coordinate points.
          hasRenderableBoundary is the single source of truth; the Circle is
          ONLY rendered when hasRenderableBoundary is false.
        */}
        {hasRenderableBoundary ? (
          <>
            <Polygon
              coordinates={boundaryCoords}
              strokeColor="#2e7d32"
              fillColor="rgba(46,125,50,0.18)"
              strokeWidth={3}
            />
            {/* Vertex dot markers — confirm polygon points are correct */}
            {boundaryCoords.map((pt, idx) => (
              <Marker
                key={`bv-${idx}`}
                coordinate={pt}
                anchor={{ x: 0.5, y: 0.5 }}
                pinColor="#2e7d32"
              />
            ))}
          </>
        ) : (
          /* 500 m reference circle — only when NO renderable boundary exists */
          <Circle
            center={farmCoord}
            radius={500}
            strokeColor="#1565c0"
            fillColor="rgba(21,101,192,0.08)"
            strokeWidth={1.5}
          />
        )}
      </MapView>

      {/* Info overlay — pointerEvents="box-none" so map still receives touches */}
      <View style={styles.infoBar} pointerEvents="box-none">
        <GlassCard style={styles.infoCard} opacity={0.93}>
          {/* Farm name + boundary status badge */}
          <View style={styles.infoRow}>
            <MaterialCommunityIcons name="map-marker" size={16} color="#2e7d32" />
            <Text variant="labelMedium" style={styles.infoText} numberOfLines={1}>
              {farmName}
            </Text>
            {hasRenderableBoundary ? (
              <View style={styles.boundaryBadge}>
                <Text style={styles.boundaryBadgeText}>
                  Boundary saved · {boundaryCoords.length} pts
                </Text>
              </View>
            ) : (
              <View style={[styles.boundaryBadge, styles.noBoundaryBadge]}>
                <Text style={styles.noBoundaryText}>No boundary</Text>
              </View>
            )}
          </View>

          {/* Area when boundary exists */}
          {mapData?.boundary_area_acres != null && (
            <Text variant="bodySmall" style={styles.areaText}>
              {mapData.boundary_area_acres.toFixed(3)} acres
              {mapData.boundary_area_hectares != null
                ? ` · ${mapData.boundary_area_hectares.toFixed(3)} ha`
                : ''}
            </Text>
          )}

          {/* Satellite summary */}
          {mapData?.satellite_summary && (
            <View style={styles.satRow}>
              <MaterialCommunityIcons name="satellite-variant" size={13} color="#6a1b9a" />
              <Text variant="bodySmall" style={styles.satText}>
                {mapData.satellite_summary.scene_count > 0
                  ? `${mapData.satellite_summary.scene_count} scene(s) · ${mapData.satellite_summary.provider}${mapData.satellite_summary.is_mock ? ' (demo)' : ''}`
                  : 'No recent satellite data'}
              </Text>
            </View>
          )}

          {/* "Why draw a boundary?" — shown only when no renderable boundary exists */}
          {!hasRenderableBoundary && (
            <View style={styles.whyCard}>
              <Text style={styles.whyTitle}>Why draw a boundary?</Text>
              <Text style={styles.whyText}>
                Satellite pixels and MRV checks must match the actual farm area, not just one GPS
                point. Drawing a boundary helps calculate acreage, verify land claims, and fetch
                NDVI/NDWI only for this farm.
              </Text>
            </View>
          )}

          {/* Action buttons */}
          <View style={styles.actionRow}>
            <TouchableOpacity
              style={styles.actionBtn}
              onPress={() => navigation.navigate('BoundaryEditor', { farmId, farmName })}
            >
              <MaterialCommunityIcons name="vector-polygon" size={14} color="#1565c0" />
              <Text style={styles.actionBtnText}>
                {hasRenderableBoundary ? 'Edit Boundary' : 'Draw Boundary'}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.actionBtn, styles.actionBtnSecondary]}
              onPress={() => navigation.navigate('SatelliteInsights', { farmId, farmName })}
            >
              <MaterialCommunityIcons name="satellite-variant" size={14} color="#6a1b9a" />
              <Text style={[styles.actionBtnText, { color: '#6a1b9a' }]}>Insights</Text>
            </TouchableOpacity>
          </View>
        </GlassCard>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:    { flex: 1 },
  map:     { flex: 1 },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 32 },
  loadingText:  { color: '#555', marginTop: 8 },
  errorText:    { color: '#c62828', textAlign: 'center' },
  mapsKeyHint:  { color: '#7b5800', textAlign: 'center', lineHeight: 20, marginTop: 4 },
  retryBtn:    { paddingHorizontal: 20, paddingVertical: 8, backgroundColor: '#2e7d32', borderRadius: 8 },
  retryText:   { color: '#fff', fontWeight: '700' },

  infoBar:  { position: 'absolute', bottom: 16, left: 16, right: 16 },
  infoCard: { margin: 0 },
  infoRow:  { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  infoText: { flex: 1, fontWeight: '700', color: '#1b5e20' },

  boundaryBadge: {
    backgroundColor: '#e8f5e9', paddingHorizontal: 8, paddingVertical: 2,
    borderRadius: 10,
  },
  boundaryBadgeText: { fontSize: 11, color: '#2e7d32', fontWeight: '700' },
  noBoundaryBadge:   { backgroundColor: '#fff3e0' },
  noBoundaryText:    { fontSize: 11, color: '#e65100', fontWeight: '600' },

  areaText: { color: '#444', marginBottom: 4 },
  satRow:   { flexDirection: 'row', alignItems: 'center', gap: 5, marginBottom: 6 },
  satText:  { color: '#6a1b9a', flex: 1 },

  // "Why draw a boundary?" informational card
  whyCard: {
    backgroundColor: '#fffde7',
    borderRadius: 8,
    padding: 10,
    marginBottom: 8,
    borderLeftWidth: 3,
    borderLeftColor: '#f9a825',
  },
  whyTitle: { fontSize: 12, fontWeight: '700', color: '#f57f17', marginBottom: 3 },
  whyText:  { fontSize: 11, color: '#5d4037', lineHeight: 16 },

  actionRow: { flexDirection: 'row', gap: 8 },
  actionBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 5, backgroundColor: '#e3f2fd', borderRadius: 8,
    paddingVertical: 8,
  },
  actionBtnSecondary: { backgroundColor: '#f3e5f5' },
  actionBtnText: { fontSize: 12, fontWeight: '700', color: '#1565c0' },
});
