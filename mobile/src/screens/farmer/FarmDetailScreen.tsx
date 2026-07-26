/**
 * FarmDetailScreen — Phase 9B
 * GET /farms/{farm_id}
 * Shows farm details + quick links to Sensor Readings, Carbon Reports,
 * Satellite/Drone data, and the shared Token Wallet tab.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { ScrollView, StyleSheet, View, RefreshControl, Modal, TextInput as RNTextInput } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getFarmApi, getCropCyclesApi, deleteFarmApi, archiveFarmApi } from '../../api/farmApi';
import { getFarmSOCOverview, generateSOCReport, addSOCMeasurement, type FarmSOCOverview } from '../../api/socApi';
import { getMRVSummary, type MRVSummaryResponse } from '../../api/aiApi';
import { AIInsightsCard } from '../../components/AIInsightsCard';
import { Alert, TouchableOpacity } from 'react-native';
import { AppButton } from '../../components/AppButton';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { InfoRow } from '../../components/InfoRow';
import { StatusBadge } from '../../components/StatusBadge';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import type { Farm, CropCycle } from '../../types';
import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'FarmDetail'>;

interface QuickLink {
  icon: keyof typeof MaterialCommunityIcons.glyphMap;
  label: string;
  sub: string;
  color: string;
  onPress: () => void;
}

export function FarmDetailScreen({ navigation, route }: Props) {
  const { farmId, farmName } = route.params;

  const [farm, setFarm]           = useState<Farm | null>(null);
  const [cycles, setCycles]       = useState<CropCycle[]>([]);
  const [socOverview, setSOCOverview] = useState<FarmSOCOverview | null>(null);
  const [generatingSOC, setGeneratingSOC] = useState(false);
  const [showAddSOC, setShowAddSOC]       = useState(false);
  const [socPercent, setSOCPercent]       = useState('');
  const [socSourceType, setSOCSourceType] = useState<'LAB' | 'MANUAL'>('LAB');
  const [socNotes, setSOCNotes]           = useState('');
  const [submittingSOC, setSubmittingSOC] = useState(false);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [refreshing, setRefreshing] = useState(false);

  // Phase 18 — AI MRV Insights (per-farm)
  const [aiSummary, setAiSummary] = useState<MRVSummaryResponse | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      setError('');
      // value from GET /farms/{farm_id}
      const [farmData, cycleData, socData] = await Promise.allSettled([
        getFarmApi(farmId),
        getCropCyclesApi(farmId),
        getFarmSOCOverview(farmId),
      ]);
      if (farmData.status === 'fulfilled') setFarm(farmData.value);
      if (cycleData.status === 'fulfilled') setCycles(cycleData.value);
      if (socData.status === 'fulfilled') setSOCOverview(socData.value);
      if (farmData.status === 'rejected') setError('Failed to load farm details.');
    } catch {
      setError('Failed to load farm details.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [farmId]);

  const fetchAIInsights = useCallback(async () => {
    setAiLoading(true);
    setAiError(null);
    try {
      const result = await getMRVSummary(farmId);
      setAiSummary(result);
    } catch {
      setAiError('Could not load AI insights. Tap refresh to retry.');
    } finally {
      setAiLoading(false);
    }
  }, [farmId]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => { fetchAIInsights(); }, [fetchAIInsights]);
  const onRefresh = () => { setRefreshing(true); fetchAll(); fetchAIInsights(); };

  const handleArchiveFarm = () => {
    Alert.alert(
      'Archive Farm',
      `Archive "${farm?.farm_name}"? The farm will be archived and no new crop cycles can be created. Existing data is preserved.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Archive',
          style: 'destructive',
          onPress: async () => {
            try {
              const updated = await archiveFarmApi(farmId, 'Archived by farmer');
              setFarm(updated);
              Alert.alert('Farm Archived', `"${updated.farm_name}" has been archived.`);
            } catch (e: any) {
              const msg = e?.response?.data?.detail ?? 'Failed to archive farm.';
              Alert.alert('Error', msg);
            }
          },
        },
      ],
    );
  };

  const handleDeleteFarm = () => {
    Alert.alert(
      'Permanently Delete Farm',
      `Delete "${farm?.farm_name}" forever?\n\nThis will permanently remove the farm and all its crop cycles, sensor readings, and reports. This cannot be undone.\n\nDeletion is blocked if credits have been minted or a payout has been issued.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete Forever',
          style: 'destructive',
          onPress: async () => {
            try {
              await deleteFarmApi(farmId);
              Alert.alert('Farm Deleted', 'The farm has been permanently removed.', [
                { text: 'OK', onPress: () => navigation.navigate('MyFarms') },
              ]);
            } catch (e: any) {
              const msg = e?.response?.data?.detail ?? 'Failed to delete farm.';
              Alert.alert('Cannot Delete Farm', msg);
            }
          },
        },
      ],
    );
  };

  const handleGenerateSOCReport = async () => {
    if (!socOverview?.crop_cycle_id) return;
    setGeneratingSOC(true);
    try {
      await generateSOCReport(farmId, socOverview.crop_cycle_id);
      // Refresh SOC overview to switch from LIVE_ESTIMATE → REPORT_AVAILABLE
      const updated = await getFarmSOCOverview(farmId);
      setSOCOverview(updated);
    } catch (e: any) {
      Alert.alert('SOC Error', e?.response?.data?.detail ?? 'Failed to generate SOC report.');
    } finally {
      setGeneratingSOC(false);
    }
  };

  const handleAddSoilTest = async () => {
    const pct = parseFloat(socPercent);
    if (isNaN(pct) || pct < 0 || pct > 100) {
      Alert.alert('Invalid Input', 'SOC % must be a number between 0 and 100.');
      return;
    }
    setSubmittingSOC(true);
    try {
      await addSOCMeasurement(farmId, {
        soc_percent: pct,
        soc_source: socSourceType,
        notes: socNotes || undefined,
        crop_cycle_id: socOverview?.crop_cycle_id ?? undefined,
      });
      setShowAddSOC(false);
      setSOCPercent('');
      setSOCNotes('');
      // Refresh SOC overview — confidence should improve with LAB/MANUAL data
      const updated = await getFarmSOCOverview(farmId);
      setSOCOverview(updated);
      Alert.alert('Soil Test Added', `${socSourceType} measurement of ${pct}% SOC recorded. Confidence has been updated.`);
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Failed to add SOC measurement.');
    } finally {
      setSubmittingSOC(false);
    }
  };

  if (loading) return <LoadingView message="Loading farm details…" />;
  if (error || !farm) return <ErrorView message={error || 'Farm not found.'} onRetry={fetchAll} />;

  const activeCycles = cycles.filter((c) => c.status === 'ACTIVE').length;

  const quickLinks: QuickLink[] = [
    {
      icon: 'access-point-network',
      label: 'Sensor Readings',
      sub: 'Soil, water, methane',
      color: '#1565c0',
      onPress: () => navigation.navigate('SensorReadings', { farmId, farmName }),
    },
    {
      icon: 'satellite-variant',
      label: 'Satellite & Drone',
      sub: 'NDVI, vegetation, water',
      color: '#6a1b9a',
      onPress: () => navigation.navigate('SatelliteDrone', { farmId, farmName }),
    },
    // Phase 12 — GIS
    {
      icon: 'map-outline',
      label: 'View Map',
      sub: 'Location & boundary',
      color: '#00695c',
      onPress: () => {
        if (__DEV__) console.log('Navigate View Map', { farmId: farm.id, farmName: farm.farm_name }); // eslint-disable-line no-console
        navigation.navigate('FarmMap', { farmId: farm.id, farmName: farm.farm_name });
      },
    },
    {
      icon: 'vector-polygon',
      label: 'Edit Boundary',
      sub: 'Draw farm boundary',
      color: '#2e7d32',
      onPress: () => {
        if (__DEV__) console.log('Navigate Edit Boundary', { farmId: farm.id, farmName: farm.farm_name }); // eslint-disable-line no-console
        navigation.navigate('BoundaryEditor', { farmId: farm.id, farmName: farm.farm_name });
      },
    },
    {
      icon: 'chart-line',
      label: 'Satellite Insights',
      sub: 'NDVI, NDWI, scenes',
      color: '#1565c0',
      onPress: () => navigation.navigate('SatelliteInsights', { farmId: farm.id, farmName: farm.farm_name }),
    },
    // Phase 13 — Audit & Evidence
    {
      icon: 'folder-open-outline',
      label: 'Evidence',
      sub: 'Photos, PDFs, documents',
      color: '#37474f',
      onPress: () => navigation.navigate('EvidenceList', { farmId: farm.id, farmName: farm.farm_name }),
    },
    {
      icon: 'shield-check-outline',
      label: 'Audit Package',
      sub: 'Full auditable report',
      color: '#4a148c',
      onPress: () => navigation.navigate('FarmAudit', { farmId: farm.id, farmName: farm.farm_name }),
    },
    // Phase 14 — Add Evidence and MRV Import are FPO-only actions.
    // Farmers are view-only on evidence (backend enforces 403 on upload).
    // These links are intentionally absent from the farmer FarmDetail screen.
  ];

  /** Map raw backend source keys to readable labels. */
  const humanizeSOCSources = (sources: string[]): string => {
    const SOURCE_MAP: Record<string, string> = {
      LAB:                  'lab soil test',
      MANUAL:               'manual soil-test entry',
      COPERNICUS:           'Copernicus satellite observations',
      SENTINEL_2:           'Copernicus (Sentinel-2) observations',
      LANDSAT_8:            'Copernicus (Landsat-8) observations',
      BHUVAN:               'Bhuvan/NRSC soil layers',
      SATELLITE_MANUAL:     'manually uploaded satellite data',
      SATELLITE_IMPORTED:   'imported satellite observations',
      SATELLITE_SIMULATED:  'simulated satellite observations',
      ESTIMATED:            'soil-type estimate',
    };
    const readable = sources.map((s) => {
      // Handle ESTIMATED(soil_type=Other,0.650%) → soil-type estimate
      const key = s.split('(')[0].trim().toUpperCase();
      return SOURCE_MAP[key] ?? s;
    });
    if (readable.length === 0) return '—';
    if (readable.length === 1) return `Source: ${readable[0]}`;
    const last = readable[readable.length - 1];
    const rest = readable.slice(0, -1).join(', ');
    return `Source: ${rest} + ${last}`;
  };

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
          {/* Farm Status Header */}
          <GlassCard style={styles.headerCard} opacity={0.90}>
            <View style={styles.headerRow}>
              <View style={styles.farmIconBig}>
                <MaterialCommunityIcons name="sprout" size={32} color="#2e7d32" />
              </View>
              <View style={styles.headerText}>
                <Text variant="titleMedium" style={styles.farmTitle} numberOfLines={2}>
                  {farm.farm_name}
                </Text>
                <Text variant="bodySmall" style={styles.farmLoc}>
                  {farm.village}, {farm.district}, {farm.state}
                </Text>
              </View>
              <StatusBadge status={farm.farm_status ?? (farm.is_approved ? 'APPROVED' : 'PENDING')} />
            </View>
          </GlassCard>

          {/* Farm Details */}
          <SectionHeader icon="information-outline" title="Farm Details" light />
          <GlassCard opacity={0.82}>
            <InfoRow icon="ruler-square"    label="Land Area"     value={`${farm.land_area_acres.toFixed(2)} acres`} />
            <InfoRow icon="terrain"         label="Soil Type"     value={farm.soil_type} />
            <InfoRow icon="water-well-outline" label="Water Source" value={farm.water_source} />
            <InfoRow icon="map-marker"      label="Coordinates"   value={`${farm.latitude.toFixed(4)}, ${farm.longitude.toFixed(4)}`} />
            <InfoRow icon="calendar-plus"   label="Registered"    value={new Date(farm.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })} last />
          </GlassCard>

          {/* Crop Cycles */}
          <SectionHeader icon="rotate-right" title="Crop Cycles" light />
          <GlassCard opacity={0.82}>
            {cycles.length === 0 ? (
              <View style={styles.emptyBox}>
                <Text variant="bodyMedium" style={styles.emptyText}>No crop cycles registered yet.</Text>
                <AppButton
                  mode="outlined"
                  onPress={() => navigation.navigate('CreateCropCycle', { farmId, farmName })}
                  icon="plus-circle-outline"
                  style={styles.createCycleBtn}
                >
                  Create First Crop Cycle
                </AppButton>
              </View>
            ) : (
              <>
                <InfoRow icon="rotate-left"  label="Total Cycles"  value={String(cycles.length)} />
                <InfoRow icon="play-circle-outline" label="Active Cycles" value={String(activeCycles)} last />
                {cycles.slice(0, 3).map((c, i) => (
                  <TouchableOpacity
                    key={c.id}
                    style={[styles.cycleRow, i < Math.min(cycles.length, 3) - 1 && styles.cycleBorder]}
                    onPress={() => navigation.navigate('CropCycleDetail', { cycleId: c.id, farmId, farmName, farmStatus: farm.farm_status })}
                    activeOpacity={0.7}
                  >
                    <View style={styles.cycleLeft}>
                      <Text variant="labelSmall" style={styles.cycleName}>{c.crop_type} · {c.season}</Text>
                      <Text variant="bodySmall" style={styles.cycleId}>Cycle #{c.id}</Text>
                    </View>
                    <StatusBadge status={c.status} />
                    <MaterialCommunityIcons name="chevron-right" size={16} color="#bbb" />
                  </TouchableOpacity>
                ))}
              </>
            )}
          </GlassCard>

          {/* Create Crop Cycle CTA */}
          {cycles.length > 0 && (
            <View style={styles.ctaRow}>
              <AppButton
                mode="outlined"
                onPress={() => navigation.navigate('CreateCropCycle', { farmId, farmName })}
                icon="plus-circle-outline"
                style={styles.createCycleBtn}
              >
                New Crop Cycle
              </AppButton>
            </View>
          )}

          {/* Quick Links */}
          <SectionHeader icon="link-variant" title="Explore Data" light />
          <View style={styles.quickGrid}>
            {quickLinks.map((link) => (
              <TouchableOpacity
                key={link.label}
                style={styles.quickTile}
                onPress={link.onPress}
                activeOpacity={0.8}
              >
                <MaterialCommunityIcons name={link.icon} size={28} color={link.color} />
                <Text variant="labelMedium" style={styles.quickLabel}>{link.label}</Text>
                <Text variant="bodySmall" style={styles.quickSub}>{link.sub}</Text>
                <MaterialCommunityIcons name="chevron-right" size={16} color="#bbb" style={styles.quickChevron} />
              </TouchableOpacity>
            ))}
          </View>

          {/* SOC Overview — Phase 12.5 / 13 */}
          <SectionHeader icon="leaf-circle-outline" title="Soil Organic Carbon" light />
          <GlassCard opacity={0.82}>
            {!socOverview ? (
              <View style={styles.emptyBox}>
                <MaterialCommunityIcons name="leaf-circle-outline" size={36} color="#a5d6a7" />
                <Text variant="bodySmall" style={styles.emptyText}>Loading SOC data…</Text>
              </View>

            ) : socOverview.data_status === 'REPORT_AVAILABLE' ? (
              /* ── Saved SOC report ─────────────────────────────────────────── */
              <>
                <View style={styles.socStatusBadge}>
                  <MaterialCommunityIcons name="check-circle-outline" size={14} color="#2e7d32" />
                  <Text variant="labelSmall" style={styles.socStatusGreen}>SOC Report Saved</Text>
                </View>
                <InfoRow icon="molecule-co2"        label="Baseline SOC"   value={`${socOverview.baseline_soc_percent?.toFixed(3)} %`} />
                <InfoRow icon="trending-up"         label="Current SOC"    value={`${socOverview.current_soc_percent?.toFixed(3)} %`} />
                <InfoRow icon="chart-bar"           label="SOC Gain"       value={`+${socOverview.soc_gain_percent?.toFixed(4)} %`} />
                <InfoRow icon="molecule-co2"        label="SOC CO₂e"       value={`${socOverview.soc_co2e?.toFixed(4)} tCO₂e`} />
                <InfoRow icon="leaf-circle-outline" label="SOC Credits"    value={`${socOverview.soc_credits} (informational)`} />
                <InfoRow icon="gauge"               label="Confidence"     value={`${((socOverview.confidence_score ?? 0) * 100).toFixed(0)}%`} last />
                {/* Compact source + confidence box */}
                <View style={styles.socSourceBox}>
                  <Text variant="bodySmall" style={styles.socSourceText}>
                    {humanizeSOCSources(socOverview.sources_used)}
                  </Text>
                  {socOverview.confidence_breakdown && (
                    <Text variant="bodySmall" style={styles.socConfidenceNote}>
                      {socOverview.confidence_breakdown.reason}
                    </Text>
                  )}
                </View>
                <View style={styles.socInfoBox}>
                  <MaterialCommunityIcons name="information-outline" size={13} color="#1565c0" />
                  <Text variant="bodySmall" style={styles.socInfoText}>
                    SOC credits are informational only — not included in token minting.
                  </Text>
                </View>
                <AppButton mode="outlined" icon="flask-outline" style={styles.socGenerateBtn}
                  onPress={() => setShowAddSOC(true)}>
                  Add Soil Test SOC
                </AppButton>
              </>

            ) : socOverview.data_status === 'LIVE_ESTIMATE' ? (
              /* ── Live estimate — satellite data available, no saved report ── */
              <>
                <View style={styles.socStatusBadge}>
                  <MaterialCommunityIcons name="chart-line-variant" size={14} color="#1565c0" />
                  <Text variant="labelSmall" style={styles.socStatusBlue}>Estimated SOC Potential</Text>
                </View>
                <InfoRow icon="molecule-co2"        label="Baseline SOC"      value={`${socOverview.baseline_soc_percent?.toFixed(3)} %`} />
                <InfoRow icon="trending-up"         label="Est. Current SOC"  value={`${socOverview.current_soc_percent?.toFixed(3)} %`} />
                <InfoRow icon="chart-bar"           label="SOC Gain"          value={`+${socOverview.soc_gain_percent?.toFixed(4)} %`} />
                <InfoRow icon="molecule-co2"        label="Est. CO₂e"         value={`${socOverview.soc_co2e?.toFixed(4)} tCO₂e`} />
                <InfoRow icon="leaf-circle-outline" label="Potential Credits"  value={`${socOverview.soc_credits} (informational)`} />
                <InfoRow icon="satellite-variant"   label="Satellite Obs."     value={`${socOverview.satellite_observation_count}`} />
                <InfoRow icon="gauge"               label="Confidence"         value={`${((socOverview.confidence_score ?? 0) * 100).toFixed(0)}%`} last />
                {/* Compact source + confidence note */}
                <View style={styles.socSourceBox}>
                  <Text variant="bodySmall" style={styles.socSourceText}>
                    {humanizeSOCSources(socOverview.sources_used)}
                  </Text>
                  {socOverview.confidence_breakdown && (
                    <Text variant="bodySmall" style={styles.socConfidenceNote}>
                      {socOverview.confidence_breakdown.reason}
                    </Text>
                  )}
                </View>
                {/* Recommendations */}
                {socOverview.recommendations && socOverview.recommendations.length > 0 && (
                  <View style={styles.socRecsBox}>
                    <Text variant="labelSmall" style={styles.socRecsTitle}>How to improve confidence:</Text>
                    {socOverview.recommendations.slice(0, 3).map((rec, i) => (
                      <Text key={i} variant="bodySmall" style={styles.socRecItem}>• {rec}</Text>
                    ))}
                  </View>
                )}
                <View style={styles.socInfoBox}>
                  <MaterialCommunityIcons name="information-outline" size={13} color="#1565c0" />
                  <Text variant="bodySmall" style={styles.socInfoText}>
                    Live estimate — not yet saved. SOC credits are informational only.
                  </Text>
                </View>
                <AppButton mode="outlined" icon="flask-outline" style={styles.socSatBtn}
                  onPress={() => setShowAddSOC(true)}>
                  Add Soil Test SOC
                </AppButton>
                <AppButton
                  mode="contained"
                  onPress={handleGenerateSOCReport}
                  icon="content-save-outline"
                  loading={generatingSOC}
                  disabled={generatingSOC}
                  style={styles.socGenerateBtn}
                >
                  Generate SOC Report
                </AppButton>
              </>

            ) : socOverview.data_status === 'INSUFFICIENT_SATELLITE_DATA' ? (
              /* ── No satellite observations ───────────────────────────────── */
              <View style={styles.emptyBox}>
                <MaterialCommunityIcons name="satellite-variant" size={36} color="#90a4ae" />
                <Text variant="bodyMedium" style={styles.emptyText}>Satellite data required</Text>
                <Text variant="bodySmall" style={styles.emptyHint}>
                  Satellite observations are needed to estimate SOC. Add observations via Satellite Insights.
                </Text>
                <AppButton mode="outlined" icon="flask-outline" style={styles.socSatBtn}
                  onPress={() => setShowAddSOC(true)}>
                  Add Soil Test SOC
                </AppButton>
                <AppButton
                  mode="outlined"
                  icon="chart-line"
                  style={styles.socSatBtn}
                  onPress={() => navigation.navigate('SatelliteInsights', { farmId: farm.id, farmName: farm.farm_name })}
                >
                  Open Satellite Insights
                </AppButton>
              </View>

            ) : (
              /* ── NO_CROP_CYCLE ─────────────────────────────────────────── */
              <View style={styles.emptyBox}>
                <MaterialCommunityIcons name="leaf-circle-outline" size={36} color="#a5d6a7" />
                <Text variant="bodyMedium" style={styles.emptyText}>No crop cycle yet</Text>
                <Text variant="bodySmall" style={styles.emptyHint}>
                  Create a crop cycle before SOC can be estimated.
                </Text>
              </View>
            )}
          </GlassCard>

          {/* Add Soil Test Modal */}
          <Modal visible={showAddSOC} transparent animationType="slide" onRequestClose={() => setShowAddSOC(false)}>
            <View style={styles.modalOverlay}>
              <View style={styles.modalCard}>
                <Text variant="titleMedium" style={styles.modalTitle}>Add Soil Test SOC</Text>
                <Text variant="bodySmall" style={styles.modalHint}>
                  Enter a lab-certified or manual soil SOC% measurement. This will update the baseline and improve confidence.
                </Text>
                <Text variant="labelMedium" style={styles.modalLabel}>SOC % (0–100)</Text>
                <RNTextInput
                  style={styles.modalInput}
                  keyboardType="decimal-pad"
                  placeholder="e.g. 0.85"
                  value={socPercent}
                  onChangeText={setSOCPercent}
                />
                <Text variant="labelMedium" style={styles.modalLabel}>Source</Text>
                <View style={styles.sourceRow}>
                  {(['LAB', 'MANUAL'] as const).map((src) => (
                    <TouchableOpacity key={src} style={[styles.sourceChip, socSourceType === src && styles.sourceChipActive]}
                      onPress={() => setSOCSourceType(src)}>
                      <Text variant="labelSmall" style={socSourceType === src ? styles.sourceChipTextActive : styles.sourceChipText}>
                        {src === 'LAB' ? '🔬 LAB' : '📝 MANUAL'}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
                <Text variant="labelMedium" style={styles.modalLabel}>Notes (optional)</Text>
                <RNTextInput
                  style={[styles.modalInput, { height: 60 }]}
                  placeholder="Lab report reference, notes…"
                  value={socNotes}
                  onChangeText={setSOCNotes}
                  multiline
                />
                <AppButton mode="contained" onPress={handleAddSoilTest} loading={submittingSOC} disabled={submittingSOC}
                  style={{ marginTop: 12 }}>
                  Submit SOC Measurement
                </AppButton>
                <AppButton mode="outlined" onPress={() => setShowAddSOC(false)} style={{ marginTop: 8 }}>
                  Cancel
                </AppButton>
              </View>
            </View>
          </Modal>

          {/* AI MRV Insights — Phase 18 (per-farm, only shown once a carbon report exists) */}
          {(aiLoading || aiSummary?.has_carbon_report) ? (
            <>
              <SectionHeader icon="brain" title="AI MRV Insights" light />
              <View style={styles.aiCardWrap}>
                <AIInsightsCard
                  loading={aiLoading}
                  error={aiError}
                  summary={aiSummary?.summary ?? undefined}
                  insights={aiSummary?.insights}
                  dataCompletenessPct={aiSummary?.data_completeness}
                  confidenceLevel={aiSummary?.confidence_level}
                  disclaimer={aiSummary?.disclaimer}
                  onRefresh={fetchAIInsights}
                />
                {!aiLoading && !aiError && aiSummary?.next_best_action ? (
                  <View style={styles.aiBestAction}>
                    <MaterialCommunityIcons name="arrow-right-circle-outline" size={15} color="#2e7d32" />
                    <Text variant="bodySmall" style={styles.aiBestActionText}>
                      {aiSummary.next_best_action}
                    </Text>
                  </View>
                ) : null}
              </View>
            </>
          ) : (
            /* Show a teaser when farm has no carbon report yet */
            !aiLoading && aiSummary && !aiSummary.has_carbon_report ? (
              <>
                <SectionHeader icon="brain" title="AI MRV Insights" light />
                <GlassCard opacity={0.82} style={styles.aiLockedCard}>
                  <MaterialCommunityIcons name="lock-outline" size={28} color="#ce93d8" />
                  <Text variant="bodyMedium" style={styles.aiLockedText}>
                    Generate a carbon report to unlock AI MRV insights.
                  </Text>
                </GlassCard>
              </>
            ) : null
          )}

          {/* Danger zone */}
          <SectionHeader icon="alert-circle-outline" title="Danger Zone" light />
          <GlassCard opacity={0.82} style={styles.dangerCard}>
            {farm.farm_status !== 'ARCHIVED' && (
              <>
                <AppButton
                  mode="outlined"
                  onPress={handleArchiveFarm}
                  icon="archive-outline"
                  style={styles.archiveBtn}
                  textColor="#546e7a"
                >
                  Archive This Farm
                </AppButton>
                <Text variant="bodySmall" style={styles.deleteHint}>
                  Archives the farm — no new crop cycles can be created. All existing data is preserved.
                </Text>
                <View style={styles.dangerDivider} />
              </>
            )}
            <AppButton
              mode="outlined"
              onPress={handleDeleteFarm}
              icon="delete-outline"
              style={styles.deleteBtn}
              textColor="#c62828"
            >
              Delete This Farm
            </AppButton>
            <Text variant="bodySmall" style={styles.deleteHint}>
              Permanently removes all farm data. Blocked if carbon credits have been issued or a payout is in progress.
            </Text>
          </GlassCard>

          <View style={styles.bottomPad} />
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { paddingTop: 12, paddingBottom: 32 },

  headerCard: { marginTop: 8 },
  headerRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  farmIconBig: {
    width: 52, height: 52, borderRadius: 26,
    backgroundColor: '#e8f5e9', alignItems: 'center', justifyContent: 'center',
  },
  headerText: { flex: 1 },
  farmTitle: { fontWeight: '800', color: '#1b5e20', marginBottom: 2 },
  farmLoc: { color: '#555' },

  cycleRow: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', paddingVertical: 8,
  },
  cycleBorder: { borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  cycleLeft: { flex: 1 },
  cycleName: { color: '#444', fontWeight: '600' },
  cycleId: { color: '#999', marginTop: 1 },

  quickGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginHorizontal: 16, marginVertical: 6 },
  quickTile: {
    flex: 1,
    minWidth: '44%',
    backgroundColor: 'rgba(255,255,255,0.88)',
    borderRadius: 16,
    padding: 14,
    gap: 4,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.4)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 6,
    elevation: 2,
    position: 'relative',
  },
  quickLabel: { fontWeight: '700', color: '#333', marginTop: 4 },
  quickSub: { color: '#888' },
  quickChevron: { position: 'absolute', top: 12, right: 12 },

  emptyBox: { paddingVertical: 8, alignItems: 'center', gap: 10 },
  emptyText: { color: '#888' },
  ctaRow: { marginHorizontal: 16, marginVertical: 6 },
  createCycleBtn: { borderColor: '#2e7d32' },
  dangerCard: { borderLeftWidth: 3, borderLeftColor: '#c62828' },
  archiveBtn: { borderColor: '#546e7a' },
  deleteBtn: { borderColor: '#c62828' },
  deleteHint: { color: '#888', marginTop: 8, lineHeight: 18 },
  dangerDivider: { height: 1, backgroundColor: '#f0f0f0', marginVertical: 12 },
  bottomPad: { height: 16 },
  socInfoBox: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 6,
    marginTop: 10, paddingTop: 10,
    borderTopWidth: 1, borderTopColor: '#e3f2fd',
  },
  socInfoText: { color: '#1565c0', flex: 1, lineHeight: 16 },
  emptyHint: { color: '#aaa', textAlign: 'center', marginTop: 4 },

  // SOC card — status badges
  socStatusBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    alignSelf: 'flex-start', marginBottom: 8,
    paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: 12,
  },
  socStatusGreen: { color: '#2e7d32', fontWeight: '700' },
  socStatusBlue:  { color: '#1565c0', fontWeight: '700' },

  // SOC card — live-estimate note box
  socLiveBox: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 6,
    marginTop: 10, paddingTop: 10,
    borderTopWidth: 1, borderTopColor: '#e8f5e9',
  },
  socLiveText: { color: '#388e3c', flex: 1, lineHeight: 16 },

  // SOC card — action buttons
  socGenerateBtn: { marginTop: 10, borderColor: '#2e7d32' },
  socSatBtn:      { marginTop: 6,  borderColor: '#546e7a' },

  // SOC card — recommendations box
  socRecsBox: {
    marginTop: 10, padding: 10, borderRadius: 8,
    backgroundColor: '#fffde7',
    borderWidth: 1, borderColor: '#f9a825',
  },
  socRecsTitle: { color: '#f57f17', fontWeight: '700', marginBottom: 4 },
  socRecItem:   { color: '#5d4037', marginTop: 2, lineHeight: 17 },

  // SOC card — source + confidence compact box
  socSourceBox: {
    marginTop: 8, paddingTop: 8,
    borderTopWidth: 1, borderTopColor: '#f0f0f0',
    gap: 3,
  },
  socSourceText: { color: '#555', lineHeight: 16 },
  socConfidenceNote: { color: '#888', lineHeight: 16, fontStyle: 'italic' },

  // AI Insights card wrapper
  aiCardWrap: { paddingHorizontal: 16, marginBottom: 4 },
  aiBestAction: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 6,
    marginTop: 4, paddingTop: 8,
    borderTopWidth: 1, borderTopColor: '#e8f5e9',
    paddingHorizontal: 2,
  },
  aiBestActionText: { color: '#2e7d32', flex: 1, lineHeight: 17, fontWeight: '600' },
  aiLockedCard: { alignItems: 'center', gap: 8, paddingVertical: 20 },
  aiLockedText: { color: '#888', textAlign: 'center', lineHeight: 20 },

  // Add Soil Test modal
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'flex-end',
  },
  modalCard: {
    backgroundColor: '#fff', borderTopLeftRadius: 20, borderTopRightRadius: 20,
    padding: 24, paddingBottom: 36,
  },
  modalTitle: { fontWeight: '800', color: '#1b5e20', marginBottom: 4 },
  modalHint:  { color: '#666', marginBottom: 16, lineHeight: 18 },
  modalLabel: { color: '#444', fontWeight: '700', marginBottom: 4, marginTop: 10 },
  modalInput: {
    borderWidth: 1, borderColor: '#ccc', borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 8,
    fontSize: 15, color: '#222',
    backgroundColor: '#fafafa',
  },
  sourceRow:          { flexDirection: 'row', gap: 10, marginTop: 4 },
  sourceChip:         { flex: 1, padding: 10, borderRadius: 8, borderWidth: 1.5, borderColor: '#bbb', alignItems: 'center' },
  sourceChipActive:   { borderColor: '#2e7d32', backgroundColor: '#e8f5e9' },
  sourceChipText:     { color: '#555' },
  sourceChipTextActive: { color: '#2e7d32', fontWeight: '700' },
});
