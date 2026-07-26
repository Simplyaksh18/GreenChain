/**
 * SatelliteDroneScreen — Phase 9B
 * GET /satellite/{farm_id}   — latest satellite observations
 * GET /drone/{farm_id}       — latest drone observations
 */
import React, { useEffect, useState, useCallback } from 'react';
import { ScrollView, StyleSheet, View, RefreshControl } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getSatelliteObsApi, getDroneObsApi } from '../../api/dashboardApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import type { SatelliteObservation, DroneObservation } from '../../types';
import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'SatelliteDrone'>;

// ── helpers ──────────────────────────────────────────────────────────────────

function healthColor(h: SatelliteObservation['vegetation_health']): string {
  return { POOR: '#c62828', FAIR: '#e65100', GOOD: '#2e7d32', EXCELLENT: '#1b5e20' }[h] ?? '#555';
}
function healthBg(h: SatelliteObservation['vegetation_health']): string {
  return { POOR: '#ffebee', FAIR: '#fff3e0', GOOD: '#e8f5e9', EXCELLENT: '#c8e6c9' }[h] ?? '#f5f5f5';
}
function riskColor(r: SatelliteObservation['flood_risk']): string {
  return { NONE: '#2e7d32', LOW: '#558b2f', MEDIUM: '#e65100', HIGH: '#c62828' }[r] ?? '#555';
}
function riskBg(r: SatelliteObservation['flood_risk']): string {
  return { NONE: '#e8f5e9', LOW: '#f1f8e9', MEDIUM: '#fff3e0', HIGH: '#ffebee' }[r] ?? '#f5f5f5';
}

// ── Satellite card ────────────────────────────────────────────────────────────

function SatelliteCard({ obs }: { obs: SatelliteObservation }) {
  return (
    <View style={styles.obsCard}>
      <View style={styles.obsHeader}>
        <View style={styles.obsLeft}>
          <MaterialCommunityIcons name="satellite-variant" size={20} color="#6a1b9a" />
          <Text variant="labelSmall" style={styles.obsDate}>
            {new Date(obs.observation_date).toLocaleDateString('en-IN', {
              day: 'numeric', month: 'short', year: 'numeric',
            })}
          </Text>
        </View>
        <Text variant="labelSmall" style={styles.obsSource}>{obs.source}</Text>
      </View>

      <View style={styles.metricsRow}>
        {/* NDVI */}
        <View style={styles.metricBox}>
          <Text variant="headlineSmall" style={[styles.metricValue, { color: '#2e7d32' }]}>
            {obs.ndvi.toFixed(3)}
          </Text>
          <Text variant="labelSmall" style={styles.metricLabel}>NDVI</Text>
        </View>
        {/* NDWI */}
        <View style={styles.metricBox}>
          <Text variant="headlineSmall" style={[styles.metricValue, { color: '#0277bd' }]}>
            {obs.ndwi.toFixed(3)}
          </Text>
          <Text variant="labelSmall" style={styles.metricLabel}>NDWI</Text>
        </View>
        {/* Cloud Cover */}
        <View style={styles.metricBox}>
          <Text variant="headlineSmall" style={[styles.metricValue, { color: '#546e7a' }]}>
            {obs.cloud_cover_percent.toFixed(0)}%
          </Text>
          <Text variant="labelSmall" style={styles.metricLabel}>Cloud Cover</Text>
        </View>
      </View>

      <View style={styles.badgesRow}>
        <View style={[styles.badge, { backgroundColor: healthBg(obs.vegetation_health) }]}>
          <MaterialCommunityIcons name="leaf" size={12} color={healthColor(obs.vegetation_health)} />
          <Text style={[styles.badgeText, { color: healthColor(obs.vegetation_health) }]}>
            {obs.vegetation_health}
          </Text>
        </View>
        <View style={[styles.badge, { backgroundColor: riskBg(obs.flood_risk) }]}>
          <MaterialCommunityIcons name="waves" size={12} color={riskColor(obs.flood_risk)} />
          <Text style={[styles.badgeText, { color: riskColor(obs.flood_risk) }]}>
            Flood: {obs.flood_risk}
          </Text>
        </View>
      </View>
    </View>
  );
}

// ── Drone card ────────────────────────────────────────────────────────────────

function DroneCard({ obs }: { obs: DroneObservation }) {
  const anomalyColor = obs.anomaly_score >= 0.7 ? '#c62828' : obs.anomaly_score >= 0.4 ? '#e65100' : '#2e7d32';
  const anomalyBg   = obs.anomaly_score >= 0.7 ? '#ffebee' : obs.anomaly_score >= 0.4 ? '#fff3e0' : '#e8f5e9';

  return (
    <View style={styles.obsCard}>
      <View style={styles.obsHeader}>
        <View style={styles.obsLeft}>
          <MaterialCommunityIcons name="quadcopter" size={20} color="#e65100" />
          <Text variant="labelSmall" style={styles.obsDate}>
            {new Date(obs.observation_date).toLocaleDateString('en-IN', {
              day: 'numeric', month: 'short', year: 'numeric',
            })}
          </Text>
        </View>
        {obs.image_reference && (
          <Text variant="labelSmall" style={styles.obsSource} numberOfLines={1}>
            📷 Image ref
          </Text>
        )}
      </View>

      <View style={styles.metricsRow}>
        {/* Vegetation Cover */}
        <View style={styles.metricBox}>
          <Text variant="headlineSmall" style={[styles.metricValue, { color: '#2e7d32' }]}>
            {obs.vegetation_cover_percent.toFixed(1)}%
          </Text>
          <Text variant="labelSmall" style={styles.metricLabel}>Vegetation</Text>
        </View>
        {/* Standing Water */}
        <View style={styles.metricBox}>
          <Text variant="headlineSmall" style={[styles.metricValue, { color: '#0277bd' }]}>
            {obs.standing_water_percent.toFixed(1)}%
          </Text>
          <Text variant="labelSmall" style={styles.metricLabel}>Standing Water</Text>
        </View>
        {/* Anomaly Score */}
        <View style={styles.metricBox}>
          <Text variant="headlineSmall" style={[styles.metricValue, { color: anomalyColor }]}>
            {obs.anomaly_score.toFixed(2)}
          </Text>
          <Text variant="labelSmall" style={styles.metricLabel}>Anomaly</Text>
        </View>
      </View>

      <View style={styles.badgesRow}>
        <View style={[styles.badge, { backgroundColor: anomalyBg }]}>
          <MaterialCommunityIcons
            name={obs.anomaly_score >= 0.7 ? 'alert-circle-outline' : 'check-circle-outline'}
            size={12}
            color={anomalyColor}
          />
          <Text style={[styles.badgeText, { color: anomalyColor }]}>
            {obs.anomaly_score >= 0.7 ? 'High Anomaly' : obs.anomaly_score >= 0.4 ? 'Moderate Anomaly' : 'Normal'}
          </Text>
        </View>
      </View>
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────

export function SatelliteDroneScreen({ route }: Props) {
  const { farmId, farmName } = route.params;

  const [satellite, setSatellite]   = useState<SatelliteObservation[]>([]);
  const [drone, setDrone]           = useState<DroneObservation[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      setError('');
      // value from GET /satellite/{farm_id} and GET /drone/{farm_id}
      const [satResult, droneResult] = await Promise.allSettled([
        getSatelliteObsApi(farmId, { limit: 10 }),
        getDroneObsApi(farmId, { limit: 10 }),
      ]);
      // UI safety: filter out any future-dated observations
      const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
      if (satResult.status === 'fulfilled') {
        const valid = satResult.value.filter((o) => o.observation_date <= today);
        setSatellite([...valid].reverse());
      }
      if (droneResult.status === 'fulfilled') {
        const valid = droneResult.value.filter((o) => o.observation_date <= today);
        setDrone([...valid].reverse());
      }
      if (satResult.status === 'rejected' && droneResult.status === 'rejected') {
        setError('Failed to load remote sensing data.');
      }
    } catch {
      setError('Failed to load remote sensing data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [farmId]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  const onRefresh = () => { setRefreshing(true); fetchAll(); };

  if (loading) return <LoadingView message="Loading remote sensing data…" />;
  if (error)   return <ErrorView message={error} onRetry={fetchAll} />;

  const noData = satellite.length === 0 && drone.length === 0;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#fff"
              colors={['#66bb6a']}
            />
          }
        >
          {noData ? (
            <GlassCard style={styles.emptyCard} opacity={0.88}>
              <View style={styles.emptyInner}>
                <MaterialCommunityIcons name="satellite-uplink" size={48} color="#9e9e9e" />
                <Text variant="titleMedium" style={styles.emptyTitle}>No Valid Observations Yet</Text>
                <Text variant="bodyMedium" style={styles.emptyMsg}>
                  No satellite or drone observations recorded for {farmName} yet.
                </Text>
              </View>
            </GlassCard>
          ) : (
            <>
              {/* Satellite Section */}
              <SectionHeader icon="satellite-variant" title="Satellite Observations" light />
              {satellite.length === 0 ? (
                <GlassCard opacity={0.82} style={styles.miniEmpty}>
                  <Text variant="bodySmall" style={styles.miniEmptyText}>No satellite observations yet.</Text>
                </GlassCard>
              ) : (
                satellite.map((obs) => <SatelliteCard key={obs.id} obs={obs} />)
              )}

              {/* Drone Section */}
              <SectionHeader icon="quadcopter" title="Drone Observations" light />
              {drone.length === 0 ? (
                <GlassCard opacity={0.82} style={styles.miniEmpty}>
                  <Text variant="bodySmall" style={styles.miniEmptyText}>No drone observations yet.</Text>
                </GlassCard>
              ) : (
                drone.map((obs) => <DroneCard key={obs.id} obs={obs} />)
              )}
            </>
          )}

          <View style={styles.bottomPad} />
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { paddingTop: 12, paddingBottom: 32 },

  obsCard: {
    backgroundColor: 'rgba(255,255,255,0.88)',
    borderRadius: 16,
    padding: 14,
    marginHorizontal: 16,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.4)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 6,
    elevation: 2,
  },
  obsHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  obsLeft: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  obsDate: { color: '#555', fontWeight: '600' },
  obsSource: { color: '#aaa', fontSize: 11 },

  metricsRow: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 12 },
  metricBox: { alignItems: 'center', flex: 1 },
  metricValue: { fontWeight: '800' },
  metricLabel: { color: '#888', marginTop: 2 },

  badgesRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  badge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8,
  },
  badgeText: { fontSize: 11, fontWeight: '700' },

  emptyCard: { marginHorizontal: 16, marginTop: 32 },
  emptyInner: { alignItems: 'center', gap: 12, paddingVertical: 16 },
  emptyTitle: { fontWeight: '800', color: '#555' },
  emptyMsg: { textAlign: 'center', color: '#777', lineHeight: 22 },

  miniEmpty: { marginHorizontal: 16, marginBottom: 8, alignItems: 'center', paddingVertical: 12 },
  miniEmptyText: { color: '#888' },

  bottomPad: { height: 16 },
});
