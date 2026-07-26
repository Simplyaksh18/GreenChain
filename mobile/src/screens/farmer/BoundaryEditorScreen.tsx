/**
 * BoundaryEditorScreen — Phase 12
 * (fix: preload saved boundary + fitToCoordinates + shared gisUtils + why-card)
 *
 * Fixes in this revision:
 * 1. Saved boundary now preloads on open.
 *    - geoJsonPolygonToMapPoints() from gisUtils converts the saved GeoJSON into
 *      MapView { latitude, longitude } points and sets them as the initial `points`.
 *    - When points >= 3, fitToCoordinates() is used so the whole polygon is visible
 *      regardless of its geographic size or location.
 *
 * 2. Map positioned correctly on open:
 *    - Boundary exists → fitToCoordinates(points)
 *    - No boundary → animateToRegion(farmCoord)
 *    - A one-shot ref prevents re-fitting as the user adds points during editing.
 *
 * 3. "Why draw a boundary?" info card shown when screen opens with no existing boundary.
 *
 * Preserved from previous bugfix:
 * 4. handleMapPress extracts nativeEvent.coordinate synchronously (React event pool).
 * 5. normalizeCoordinate() guards all incoming coordinates.
 * 6. pointerEvents="box-none" on instruction banner overlay.
 *
 * GeoJSON ↔ MapView convention (NEVER confuse these):
 *   GeoJSON ring: [longitude, latitude]   (longitude first)
 *   MapView:      { latitude, longitude } (latitude first)
 *   Loading: geoJsonPolygonToMapPoints() handles the swap
 *   Saving:  coordsToGeoJSON() writes [p.longitude, p.latitude] per point
 */
import React, { useCallback, useRef, useState, useEffect, useMemo } from 'react';
import {
  Alert,
  StyleSheet,
  View,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import MapView, {
  Marker,
  Polygon,
  type MapPressEvent,
  PROVIDER_DEFAULT,
  type Region,
} from 'react-native-maps';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';
import {
  getFarmBoundary,
  saveFarmBoundary,
  validateFarmBoundary,
  type BoundaryValidationResult,
} from '../../api/gisApi';
import { geoJsonPolygonToMapPoints } from '../../utils/gisUtils';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'BoundaryEditor'>;

// ── Coordinate normalization ───────────────────────────────────────────────────
// Used for map-press validation. Coerces to number and validates WGS84 ranges.
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

// ── Area preview (frontend approximation — server computes canonical value) ───
function approxAreaAcres(points: { latitude: number; longitude: number }[]): number {
  if (points.length < 3) return 0;
  const R = 6_371_000;
  let area = 0;
  const n = points.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const xi = (points[i].longitude * Math.PI) / 180 * R * Math.cos((points[i].latitude  * Math.PI) / 180);
    const yi = (points[i].latitude  * Math.PI) / 180 * R;
    const xj = (points[j].longitude * Math.PI) / 180 * R * Math.cos((points[j].latitude  * Math.PI) / 180);
    const yj = (points[j].latitude  * Math.PI) / 180 * R;
    area += xi * yj - xj * yi;
  }
  return Math.abs(area) / 2 / 4046.856;
}

// ── GeoJSON serialization ─────────────────────────────────────────────────────
// MapView { latitude, longitude } → GeoJSON [longitude, latitude] ring (closed)
function coordsToGeoJSON(pts: { latitude: number; longitude: number }[]): string {
  const ring = pts.map(p => [p.longitude, p.latitude]); // GeoJSON: lon first
  if (ring.length >= 3) ring.push(ring[0]);              // close the ring
  return JSON.stringify({ type: 'Polygon', coordinates: [ring] });
}

export function BoundaryEditorScreen({ navigation, route }: Props) {
  const { farmId, farmName } = route.params;

  const mapRef = useRef<MapView>(null);

  // farmCoord: validated centre coordinate (farm lat/lon from API)
  const [farmCoord, setFarmCoord] = useState<{ latitude: number; longitude: number } | null>(null);
  const [points, setPoints]         = useState<{ latitude: number; longitude: number }[]>([]);
  const [loading, setLoading]       = useState(true);
  const [saving, setSaving]         = useState(false);
  const [validation, setValidation] = useState<BoundaryValidationResult | null>(null);

  // One-shot ref: map is positioned once per focus, then ignored until next focus.
  // This prevents re-fitting as the user adds points during editing.
  const didPositionMap = useRef(false);

  // ── Load farm centre + existing boundary ──────────────────────────────────
  useFocusEffect(useCallback(() => {
    let cancelled = false;
    didPositionMap.current = false; // allow re-position on each focus

    setLoading(true);
    setPoints([]);
    setFarmCoord(null);
    setValidation(null);

    if (__DEV__) console.log('BoundaryEditor opened', { routeFarmId: farmId }); // eslint-disable-line no-console

    (async () => {
      try {
        const bd = await getFarmBoundary(farmId);
        if (cancelled) return;

        const coord = normalizeCoordinate(bd.latitude, bd.longitude);
        setFarmCoord(coord);

        // Preload existing boundary using shared utility.
        // Dual-field fallback: try `boundary` first then `farm_boundary_geojson`
        // so this works regardless of which field the backend populates.
        // geoJsonPolygonToMapPoints handles [lon,lat] → {latitude,longitude} and
        // removes the duplicate closing vertex automatically.
        const rawBoundary = (bd.boundary ?? bd.farm_boundary_geojson) as Record<string, any> | null;
        if (rawBoundary) {
          const existingPoints = geoJsonPolygonToMapPoints(rawBoundary);
          if (!cancelled) {
            setPoints(existingPoints);
            if (__DEV__) {
              // eslint-disable-next-line no-console
              console.log('[GIS] BoundaryEditorScreen loaded', {
                farmId,
                boundaryExists: existingPoints.length >= 3,
                pointCount: existingPoints.length,
                markerCoord: coord,
              });
            }
          }
        } else {
          if (__DEV__) {
            // eslint-disable-next-line no-console
            console.log('[GIS] BoundaryEditorScreen loaded', {
              farmId,
              boundaryExists: false,
              pointCount: 0,
              markerCoord: coord,
              rawBoundaryFields: { boundary: bd.boundary, farm_boundary_geojson: bd.farm_boundary_geojson },
            });
          }
        }
      } catch {
        if (!cancelled) {
          // API call failed — show empty map; user can still draw a new boundary
          setFarmCoord(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [farmId]));

  // ── Map positioning — one shot per focus ───────────────────────────────────
  // Fires when loading becomes false (data ready) and farmCoord is set.
  // Boundary exists → fitToCoordinates (shows full polygon)
  // No boundary     → animateToRegion (centres on farm location)
  useEffect(() => {
    if (loading || !farmCoord || didPositionMap.current) return;
    didPositionMap.current = true;

    const t = setTimeout(() => {
      if (points.length >= 3) {
        // Fit the map to encompass the whole boundary polygon.
        // Bottom padding is large to keep the polygon above the toolbar.
        mapRef.current?.fitToCoordinates(points, {
          edgePadding: { top: 80, right: 40, bottom: 180, left: 40 },
          animated: true,
        });
      } else {
        mapRef.current?.animateToRegion(
          {
            latitude:      farmCoord.latitude,
            longitude:     farmCoord.longitude,
            latitudeDelta:  0.02,
            longitudeDelta: 0.02,
          },
          400,
        );
      }
    }, 300);
    return () => clearTimeout(t);
  }, [loading, farmCoord, points]);

  // ── Map press handler ──────────────────────────────────────────────────────
  // FIX: Extract nativeEvent.coordinate synchronously on the very first line.
  // React may call setState updaters asynchronously after the event is nullified.
  const handleMapPress = useCallback((event: MapPressEvent) => {
    // ✅ Extract immediately — before any async work or state update
    const rawCoord = event?.nativeEvent?.coordinate;

    if (!rawCoord) {
      if (__DEV__) console.warn('[GIS] Map press ignored: missing coordinate');
      return;
    }

    const point = normalizeCoordinate(rawCoord.latitude, rawCoord.longitude);

    if (!point) {
      if (__DEV__) console.warn('[GIS] Map press ignored: invalid coordinate', rawCoord);
      return;
    }

    // ✅ Only plain validated values passed to setState — not the event object
    setPoints(prev => [...prev, point]);
    setValidation(null);
  }, []);

  const handleUndo = useCallback(() => {
    setPoints(prev => prev.slice(0, -1));
    setValidation(null);
  }, []);

  const handleClear = useCallback(() => {
    Alert.alert('Clear Boundary', 'Remove all points?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Clear',
        style: 'destructive',
        onPress: () => { setPoints([]); setValidation(null); },
      },
    ]);
  }, []);

  const previewArea = useMemo(() => approxAreaAcres(points), [points]);

  const handleValidate = useCallback(async () => {
    if (points.length < 3) {
      Alert.alert('Too few points', 'Add at least 3 points to draw a polygon.');
      return;
    }
    try {
      const geojson = coordsToGeoJSON(points);
      const result  = await validateFarmBoundary(farmId, geojson);
      setValidation(result);
      if (!result.valid) {
        Alert.alert('Invalid Boundary', result.error ?? 'Unknown validation error');
      }
    } catch (e: any) {
      Alert.alert('Validation failed', e?.response?.data?.detail ?? 'Network error');
    }
  }, [farmId, points]);

  const handleSave = useCallback(async () => {
    if (points.length < 3) {
      Alert.alert('Too few points', 'Add at least 3 points to form a polygon.');
      return;
    }
    const geojson = coordsToGeoJSON(points);

    if (__DEV__) console.log('Saving boundary for farm', { farmId, pointCount: points.length }); // eslint-disable-line no-console

    let vr: BoundaryValidationResult;
    try {
      vr = await validateFarmBoundary(farmId, geojson);
    } catch {
      vr = { valid: true, area_m2: null, area_hectares: null, area_acres: null, area_warning: null, error: null };
    }

    if (!vr.valid) {
      Alert.alert('Invalid Boundary', vr.error ?? 'Cannot save invalid boundary.');
      return;
    }

    const doSave = async () => {
      setSaving(true);
      try {
        // 1. Persist boundary
        const saveResp = await saveFarmBoundary(farmId, {
          farm_boundary_geojson:  geojson,
          boundary_area_hectares: vr.area_hectares ?? undefined,
          boundary_area_acres:    vr.area_acres    ?? undefined,
        });

        if (__DEV__) {
          // eslint-disable-next-line no-console
          console.log('Save boundary response', {
            responseFarmId: saveResp.farm_id,
            requestedFarmId: farmId,
            farmIdMatch: saveResp.farm_id === farmId,
            hasBoundary: saveResp.has_boundary,
            hasBoundaryGeojson: !!(saveResp.boundary ?? saveResp.farm_boundary_geojson),
          });
        }

        // 2. Verify the save response targets the correct farm
        if (saveResp.farm_id !== farmId) {
          Alert.alert('Save Error', `Farm ID mismatch: saved to ${saveResp.farm_id}, expected ${farmId}.`);
          return;
        }

        // 3. Re-fetch boundary to confirm DB persistence and update local points
        //    This makes BoundaryEditor show the saved state immediately, and
        //    provides FarmMapScreen's useFocusEffect with fresh data on return.
        const confirmed = await getFarmBoundary(farmId);
        const confirmedRaw = (confirmed.boundary ?? confirmed.farm_boundary_geojson) as Record<string, any> | null;
        const confirmedPoints = confirmedRaw ? geoJsonPolygonToMapPoints(confirmedRaw) : [];

        if (__DEV__) {
          // eslint-disable-next-line no-console
          console.log('Boundary confirmed after save', {
            farmId,
            hasBoundary: confirmed.has_boundary,
            pointCount: confirmedPoints.length,
          });
        }

        if (confirmedPoints.length >= 3) {
          // Update local state so the polygon is immediately visible
          setPoints(confirmedPoints);
        }

        Alert.alert(
          'Boundary Saved',
          confirmedPoints.length >= 3
            ? `Farm boundary saved successfully. ${confirmedPoints.length} points recorded.`
            : 'Farm boundary has been saved.',
          [{ text: 'OK', onPress: () => navigation.goBack() }],
        );
      } catch (e: any) {
        const msg = e?.response?.data?.detail ?? 'Failed to save boundary.';
        Alert.alert('Save Failed', msg);
      } finally {
        setSaving(false);
      }
    };

    if (vr.area_warning) {
      Alert.alert('Area Warning', `${vr.area_warning}\n\nSave anyway?`, [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Save', onPress: doSave },
      ]);
    } else {
      await doSave();
    }
  }, [farmId, navigation, points]);

  // ── Loading / error states ─────────────────────────────────────────────────
  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#2e7d32" />
      </View>
    );
  }

  if (!farmCoord) {
    return (
      <View style={styles.centered}>
        <MaterialCommunityIcons name="map-marker-alert" size={48} color="#f57f17" />
        <Text variant="bodyMedium" style={{ color: '#c62828', textAlign: 'center', padding: 24 }}>
          Could not load farm location. Please go back and try again.
        </Text>
      </View>
    );
  }

  const safeInitialRegion: Region = {
    latitude:      farmCoord.latitude,
    longitude:     farmCoord.longitude,
    latitudeDelta:  0.02,
    longitudeDelta: 0.02,
  };

  const closedPolygon = points.length >= 3 ? [...points, points[0]] : points;
  const hasExistingBoundary = points.length >= 3;

  // ── Google Maps API key guard ───────────────────────────────────────────────
  // Same guard as FarmMapScreen — prevents native IllegalStateException crash
  // when the key is missing from AndroidManifest.xml / not yet rebuilt.
  if (!process.env.EXPO_PUBLIC_GOOGLE_MAPS_ANDROID_API_KEY) {
    return (
      <View style={styles.centered}>
        <Text style={{ color: '#c62828', textAlign: 'center', padding: 24 }}>
          Google Maps API key not configured.{'\n'}
          Rebuild APK after adding EXPO_PUBLIC_GOOGLE_MAPS_ANDROID_API_KEY to mobile/.env.
        </Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      {/*
        MapView must receive onPress directly — not through a Pressable or ScrollView wrapper.
        Instructions banner uses pointerEvents="box-none" so map touches pass through.
      */}
      <MapView
        ref={mapRef}
        style={styles.map}
        provider={PROVIDER_DEFAULT}
        initialRegion={safeInitialRegion}
        onPress={handleMapPress}
      >
        {/* Polygon — shown when 3+ points exist */}
        {points.length >= 3 && (
          <Polygon
            coordinates={closedPolygon}
            strokeColor="#2e7d32"
            fillColor="rgba(46,125,50,0.18)"
            strokeWidth={2}
          />
        )}

        {/* Vertex markers */}
        {points.map((pt, idx) => (
          <Marker
            key={idx}
            coordinate={pt}
            anchor={{ x: 0.5, y: 0.5 }}
            pinColor={idx === 0 ? '#2e7d32' : '#1565c0'}
          />
        ))}
      </MapView>

      {/* Instruction banner — pointerEvents="box-none" so map receives touches */}
      <View style={styles.instructionBanner} pointerEvents="box-none">
        <Text style={styles.instructionText}>
          {points.length === 0
            ? 'Tap on the map to add boundary points'
            : points.length < 3
            ? `${points.length} point${points.length > 1 ? 's' : ''} · add ${3 - points.length} more`
            : `${points.length} points · polygon ready`}
        </Text>
      </View>

      {/* Bottom panel — normal layout flow, never overlays map */}
      <View style={styles.toolbar}>
        {/* "Why draw a boundary?" — shown when starting fresh with no existing points */}
        {!hasExistingBoundary && (
          <View style={styles.whyCard}>
            <Text style={styles.whyTitle}>Why draw a boundary?</Text>
            <Text style={styles.whyText}>
              Satellite pixels and MRV checks must match the actual farm area, not just one GPS
              point. A boundary calculates acreage, verifies land claims, and targets NDVI/NDWI
              to this farm only.
            </Text>
          </View>
        )}

        {/* Area preview */}
        <View style={styles.toolRow}>
          <View style={styles.areaBox}>
            <Text style={styles.areaLabel}>Preview</Text>
            <Text style={styles.areaVal}>
              {points.length >= 3 ? `~${previewArea.toFixed(2)} ac` : '—'}
            </Text>
            {validation?.area_hectares != null && (
              <Text style={styles.areaValidated}>
                {validation.area_acres?.toFixed(3)} ac
              </Text>
            )}
          </View>

          {/* Controls */}
          <View style={styles.controls}>
            <TouchableOpacity
              style={[styles.ctrlBtn, styles.undoBtn]}
              onPress={handleUndo}
              disabled={points.length === 0}
            >
              <MaterialCommunityIcons
                name="undo"
                size={20}
                color={points.length === 0 ? '#bbb' : '#333'}
              />
              <Text style={[styles.ctrlLabel, points.length === 0 && styles.disabledLabel]}>Undo</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.ctrlBtn, styles.clearBtn]}
              onPress={handleClear}
              disabled={points.length === 0}
            >
              <MaterialCommunityIcons
                name="delete-outline"
                size={20}
                color={points.length === 0 ? '#bbb' : '#c62828'}
              />
              <Text style={[styles.ctrlLabel, { color: points.length === 0 ? '#bbb' : '#c62828' }]}>Clear</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.ctrlBtn, styles.validateBtn]}
              onPress={handleValidate}
              disabled={points.length < 3}
            >
              <MaterialCommunityIcons
                name="check-circle-outline"
                size={20}
                color={points.length < 3 ? '#bbb' : '#1565c0'}
              />
              <Text style={[styles.ctrlLabel, { color: points.length < 3 ? '#bbb' : '#1565c0' }]}>Check</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.ctrlBtn, styles.saveBtn, (points.length < 3 || saving) && styles.saveBtnDisabled]}
              onPress={handleSave}
              disabled={points.length < 3 || saving}
            >
              {saving
                ? <ActivityIndicator size={16} color="#fff" />
                : <MaterialCommunityIcons name="content-save-outline" size={20} color="#fff" />
              }
              <Text style={styles.saveBtnLabel}>{saving ? 'Saving…' : 'Save'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:    { flex: 1 },
  map:     { flex: 1 },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },

  instructionBanner: {
    position: 'absolute', top: 0, left: 0, right: 0,
    backgroundColor: 'rgba(0,0,0,0.55)',
    paddingVertical: 8, paddingHorizontal: 16, alignItems: 'center',
  },
  instructionText: { color: '#fff', fontSize: 13, fontWeight: '600' },

  toolbar: {
    backgroundColor: '#fff',
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0',
    paddingHorizontal: 12,
    paddingTop: 8,
    paddingBottom: 10,
  },

  // "Why draw a boundary?" card
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

  toolRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  areaBox: {
    backgroundColor: '#f5f5f5',
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 6,
    minWidth: 80,
    alignItems: 'center',
  },
  areaLabel:     { fontSize: 10, color: '#888', fontWeight: '600' },
  areaVal:       { fontSize: 14, fontWeight: '900', color: '#1b5e20' },
  areaValidated: { fontSize: 10, color: '#2e7d32', fontWeight: '600' },

  controls: { flex: 1, flexDirection: 'row', gap: 6, justifyContent: 'flex-end' },
  ctrlBtn: {
    alignItems: 'center', justifyContent: 'center',
    gap: 2, paddingHorizontal: 10, paddingVertical: 8,
    borderRadius: 8, borderWidth: 1, borderColor: '#e0e0e0',
    backgroundColor: '#fafafa',
  },
  undoBtn:      {},
  clearBtn:     {},
  validateBtn:  {},
  ctrlLabel:    { fontSize: 10, color: '#333', fontWeight: '600' },
  disabledLabel:{ color: '#bbb' },

  saveBtn: {
    backgroundColor: '#2e7d32',
    borderColor: '#2e7d32',
    paddingHorizontal: 16,
    flexDirection: 'row',
    gap: 4,
  },
  saveBtnDisabled: { backgroundColor: '#aaa', borderColor: '#aaa' },
  saveBtnLabel:    { fontSize: 12, color: '#fff', fontWeight: '800' },
});
