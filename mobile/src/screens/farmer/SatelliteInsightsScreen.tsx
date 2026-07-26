/**
 * SatelliteInsightsScreen — Phase 12
 * (fix: show AOI source — Farm Boundary vs Center Point Estimate)
 *
 * New in this revision:
 * - AOI source banner: "Using saved farm boundary" or "Center point estimate — draw a boundary"
 * - aoi_source and aoi_warning fields from backend satellite search/indices endpoints
 *
 * Architecture:
 * - Calls GreenChain backend only (/gis/*)
 * - No direct Copernicus/Bhuvan calls from mobile
 * - Provider tokens NEVER appear in UI
 */
import React, { useCallback, useState } from 'react';
import {
  FlatList,
  RefreshControl,
  StyleSheet,
  View,
  TouchableOpacity,
} from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';
import {
  getGISProviderStatus,
  getSatelliteIndices,
  type GISProviderStatus,
  type NormalizedScene,
  type SatelliteSearchResult,
} from '../../api/gisApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { EmptyState } from '../../components/EmptyState';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'SatelliteInsights'>;

function ndviColor(v: number | null): string {
  if (v === null) return '#888';
  if (v >= 0.6) return '#2e7d32';
  if (v >= 0.4) return '#f57f17';
  return '#c62828';
}

function ndviLabel(v: number | null): string {
  if (v === null) return 'N/A';
  if (v >= 0.6) return 'Healthy';
  if (v >= 0.4) return 'Moderate';
  return 'Low';
}

export function SatelliteInsightsScreen({ route, navigation }: Props) {
  const { farmId, farmName } = route.params;

  const [providerStatus, setProviderStatus] = useState<GISProviderStatus | null>(null);
  const [result, setResult]                 = useState<SatelliteSearchResult | null>(null);
  const [loading, setLoading]               = useState(true);
  const [refreshing, setRefreshing]         = useState(false);
  const [error, setError]                   = useState('');

  // Default: past 30 days
  const today = new Date();
  const start = new Date(today);
  start.setDate(today.getDate() - 30);
  const startDate = start.toISOString().slice(0, 10);
  const endDate   = today.toISOString().slice(0, 10);

  const fetchAll = useCallback(async () => {
    try {
      setError('');
      const [status, indices] = await Promise.allSettled([
        getGISProviderStatus(),
        getSatelliteIndices({
          farm_id: farmId,
          provider: 'AUTO',
          indices: ['NDVI', 'NDWI'],
          start_date: startDate,
          end_date: endDate,
        }),
      ]);
      if (status.status === 'fulfilled') setProviderStatus(status.value);
      if (indices.status === 'fulfilled') {
        setResult(indices.value);
        if (__DEV__) {
          // eslint-disable-next-line no-console
          console.log('[GIS] SatelliteInsightsScreen loaded', {
            farmId,
            aoiSource: indices.value.aoi_source,
            provider: indices.value.provider,
            sceneCount: indices.value.count,
          });
        }
      }
      if (indices.status === 'rejected') setError('Failed to load satellite data.');
    } catch {
      setError('Failed to load satellite data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [farmId, startDate, endDate]);

  useFocusEffect(useCallback(() => { fetchAll(); }, [fetchAll]));

  if (loading) return <LoadingView message="Loading satellite insights…" />;
  if (error && !result) return <ErrorView message={error} onRetry={fetchAll} />;

  const scenes    = result?.scenes ?? [];
  const isMock    = result?.is_mock ?? false;
  const provider  = result?.provider ?? 'UNKNOWN';
  const aoiSource = result?.aoi_source;
  const aoiWarning = result?.aoi_warning;

  const usingBoundary = aoiSource === 'BOUNDARY';

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <FlatList
          data={scenes}
          keyExtractor={(_, i) => String(i)}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { setRefreshing(true); fetchAll(); }}
              tintColor="#fff"
              colors={['#2e7d32']}
            />
          }
          contentContainerStyle={scenes.length === 0 ? styles.emptyContainer : styles.list}
          ListHeaderComponent={
            <>
              {/* ── AOI Source Banner ─────────────────────────────────────── */}
              {aoiSource && (
                <GlassCard
                  opacity={0.92}
                  style={[
                    styles.aoiBanner,
                    usingBoundary ? styles.aoiBannerBoundary : styles.aoiBannerCenter,
                  ]}
                >
                  <View style={styles.aoiRow}>
                    <MaterialCommunityIcons
                      name={usingBoundary ? 'vector-polygon' : 'map-marker-radius-outline'}
                      size={18}
                      color={usingBoundary ? '#2e7d32' : '#f57f17'}
                    />
                    <View style={styles.aoiText}>
                      <Text style={[
                        styles.aoiTitle,
                        { color: usingBoundary ? '#1b5e20' : '#e65100' },
                      ]}>
                        {usingBoundary
                          ? 'Using saved farm boundary for satellite analysis.'
                          : 'AOI source: Center Point Estimate'}
                      </Text>
                      {!usingBoundary && aoiWarning && (
                        <Text style={styles.aoiWarningText}>{aoiWarning}</Text>
                      )}
                      {!usingBoundary && (
                        <TouchableOpacity
                          onPress={() =>
                            navigation.navigate('BoundaryEditor', { farmId, farmName })
                          }
                        >
                          <Text style={styles.aoiDrawLink}>Draw a boundary to improve accuracy</Text>
                        </TouchableOpacity>
                      )}
                    </View>
                  </View>
                </GlassCard>
              )}

              {/* ── Provider Status Card ───────────────────────────────────── */}
              <SectionHeader icon="satellite-variant" title="Satellite Provider" light />
              <GlassCard opacity={0.92} style={styles.providerCard}>
                {providerStatus ? (
                  <>
                    <ProviderRow
                      label="Copernicus (Sentinel-2)"
                      configured={providerStatus.copernicus.configured}
                    />
                    <ProviderRow
                      label="Bhuvan (ISRO RESOURCESAT)"
                      configured={providerStatus.bhuvan.configured}
                    />
                    <ProviderRow
                      label="Bhoonidhi (NRSC)"
                      configured={providerStatus.bhoonidhi.configured}
                    />
                    <View style={styles.activeRow}>
                      <Text variant="labelSmall" style={styles.activeLabel}>Active:</Text>
                      <View style={[
                        styles.activeBadge,
                        isMock ? styles.mockBadge : styles.realBadge,
                      ]}>
                        <Text style={isMock ? styles.mockBadgeText : styles.realBadgeText}>
                          {isMock ? `${provider} (demo data)` : provider}
                        </Text>
                      </View>
                    </View>
                    {isMock && (
                      <View style={styles.mockNote}>
                        <MaterialCommunityIcons name="information-outline" size={13} color="#f57f17" />
                        <Text variant="bodySmall" style={styles.mockNoteText}>
                          Demo data — real provider integration coming in Phase 13.
                          Connect Copernicus or Bhuvan credentials to see live imagery.
                        </Text>
                      </View>
                    )}
                  </>
                ) : (
                  <Text variant="bodySmall" style={{ color: '#888' }}>Loading provider status…</Text>
                )}
              </GlassCard>

              {/* ── Scenes header ──────────────────────────────────────────── */}
              <SectionHeader
                icon="image-multiple-outline"
                title={`Scenes · ${scenes.length} found · ${startDate} → ${endDate}`}
                light
              />
              {scenes.length === 0 && (
                <EmptyState
                  icon="satellite-variant"
                  title="No scenes found"
                  message="No satellite imagery available for this farm in the selected period."
                />
              )}
            </>
          }
          renderItem={({ item }) => <SceneCard scene={item} />}
        />
      </SafeAreaView>
    </RoleBackground>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ProviderRow({ label, configured }: { label: string; configured: boolean }) {
  return (
    <View style={styles.providerRow}>
      <MaterialCommunityIcons
        name={configured ? 'check-circle-outline' : 'circle-off-outline'}
        size={14}
        color={configured ? '#2e7d32' : '#bbb'}
      />
      <Text variant="bodySmall" style={[styles.providerLabel, !configured && styles.notConfigured]}>
        {label}
      </Text>
      <Text variant="labelSmall" style={configured ? styles.configuredTag : styles.notConfiguredTag}>
        {configured ? 'configured' : 'not configured'}
      </Text>
    </View>
  );
}

function SceneCard({ scene }: { scene: NormalizedScene }) {
  const ndvi = scene.indices.ndvi;
  const ndwi = scene.indices.ndwi;

  return (
    <GlassCard style={styles.sceneCard} opacity={0.9}>
      <View style={styles.sceneHeader}>
        <View>
          <Text variant="labelSmall" style={styles.sceneDate}>
            {scene.observation_date ?? 'Date unknown'}
          </Text>
          <Text variant="bodySmall" style={styles.sceneSat}>
            {scene.metadata.satellite ?? scene.provider}
            {scene.is_mock ? ' · Demo data' : ''}
          </Text>
        </View>
        <View style={styles.cloudBox}>
          {scene.metadata.cloud_cover != null && (
            <>
              <MaterialCommunityIcons name="weather-cloudy" size={13} color="#888" />
              <Text style={styles.cloudText}>{scene.metadata.cloud_cover.toFixed(0)}%</Text>
            </>
          )}
          {scene.metadata.resolution_m != null && (
            <Text style={styles.resText}>{scene.metadata.resolution_m}m</Text>
          )}
        </View>
      </View>

      <View style={styles.indicesRow}>
        {/* NDVI */}
        <View style={styles.indexBox}>
          <Text style={[styles.indexVal, { color: ndviColor(ndvi) }]}>
            {ndvi != null ? ndvi.toFixed(3) : 'N/A'}
          </Text>
          <Text style={styles.indexLabel}>NDVI</Text>
          {ndvi != null && (
            <Text style={[styles.indexStatus, { color: ndviColor(ndvi) }]}>
              {ndviLabel(ndvi)}
            </Text>
          )}
        </View>

        <View style={styles.indexDivider} />

        {/* NDWI */}
        <View style={styles.indexBox}>
          <Text style={[styles.indexVal, { color: ndwi != null && ndwi > 0 ? '#1565c0' : '#888' }]}>
            {ndwi != null ? ndwi.toFixed(3) : 'N/A'}
          </Text>
          <Text style={styles.indexLabel}>NDWI</Text>
          {ndwi != null && (
            <Text style={[styles.indexStatus, { color: ndwi > 0 ? '#1565c0' : '#888' }]}>
              {ndwi > 0 ? 'Water present' : 'Dry'}
            </Text>
          )}
        </View>

        {/* Source scene ID */}
        {scene.metadata.source_scene_id && (
          <>
            <View style={styles.indexDivider} />
            <View style={styles.indexBox}>
              <Text style={styles.sceneIdText} numberOfLines={2}>
                {String(scene.metadata.source_scene_id).slice(0, 18)}…
              </Text>
              <Text style={styles.indexLabel}>Scene ID</Text>
            </View>
          </>
        )}
      </View>

      {/* Phase 13 pending notice for real providers */}
      {!scene.is_mock && (ndvi === null && ndwi === null) && (
        <View style={styles.pendingNote}>
          <MaterialCommunityIcons name="timer-sand" size={12} color="#1565c0" />
          <Text variant="bodySmall" style={styles.pendingText}>
            Index computation (Phase 13) — scene metadata available
          </Text>
        </View>
      )}
    </GlassCard>
  );
}

const styles = StyleSheet.create({
  safe:           { flex: 1 },
  list:           { paddingBottom: 32 },
  emptyContainer: { flexGrow: 1 },

  // AOI source banner
  aoiBanner: { marginBottom: 4 },
  aoiBannerBoundary: { borderLeftWidth: 3, borderLeftColor: '#2e7d32' },
  aoiBannerCenter:   { borderLeftWidth: 3, borderLeftColor: '#f57f17' },
  aoiRow:     { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  aoiText:    { flex: 1 },
  aoiTitle:   { fontSize: 13, fontWeight: '700', lineHeight: 18 },
  aoiWarningText: { fontSize: 11, color: '#5d4037', marginTop: 3, lineHeight: 16 },
  aoiDrawLink:    { fontSize: 11, color: '#1565c0', fontWeight: '700', marginTop: 4 },

  providerCard: { marginBottom: 4 },
  providerRow:  { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  providerLabel: { flex: 1, color: '#333' },
  notConfigured: { color: '#aaa' },
  configuredTag:    { fontSize: 10, color: '#2e7d32', fontWeight: '700' },
  notConfiguredTag: { fontSize: 10, color: '#bbb' },

  activeRow:  { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  activeLabel: { color: '#555' },
  activeBadge: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: 10 },
  realBadge:   { backgroundColor: '#e8f5e9' },
  mockBadge:   { backgroundColor: '#fff8e1' },
  realBadgeText: { fontSize: 12, color: '#2e7d32', fontWeight: '700' },
  mockBadgeText: { fontSize: 12, color: '#f57f17', fontWeight: '700' },

  mockNote:     { flexDirection: 'row', gap: 6, alignItems: 'flex-start', marginTop: 8, backgroundColor: '#fff8e1', padding: 8, borderRadius: 8 },
  mockNoteText: { flex: 1, color: '#e65100', lineHeight: 16 },

  sceneCard:   { marginBottom: 2 },
  sceneHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 },
  sceneDate:   { fontWeight: '700', color: '#333', fontSize: 14 },
  sceneSat:    { color: '#888', marginTop: 2 },
  cloudBox:    { flexDirection: 'row', alignItems: 'center', gap: 4 },
  cloudText:   { fontSize: 12, color: '#888' },
  resText:     { fontSize: 11, color: '#aaa', marginLeft: 6 },

  indicesRow:   { flexDirection: 'row', gap: 0 },
  indexBox:     { flex: 1, alignItems: 'center', paddingVertical: 4 },
  indexDivider: { width: 1, backgroundColor: '#f0f0f0', marginVertical: 4 },
  indexVal:     { fontSize: 20, fontWeight: '900', color: '#1b5e20' },
  indexLabel:   { fontSize: 10, color: '#aaa', marginTop: 2, fontWeight: '700' },
  indexStatus:  { fontSize: 10, marginTop: 1, fontWeight: '600' },
  sceneIdText:  { fontSize: 9, color: '#888', textAlign: 'center' },

  pendingNote: { flexDirection: 'row', gap: 5, alignItems: 'center', marginTop: 8, backgroundColor: '#e3f2fd', padding: 6, borderRadius: 6 },
  pendingText: { flex: 1, color: '#1565c0', lineHeight: 15 },
});
