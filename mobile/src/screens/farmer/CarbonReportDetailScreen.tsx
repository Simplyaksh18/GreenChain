/**
 * CarbonReportDetailScreen — Phase 9C
 * Shows full detail for a carbon report including MRV data, verification, and token.
 *
 * Fetches:
 *   GET /carbon-reports/{report_id}
 *   GET /verification/pending (filter by report_id — no direct endpoint)
 *   GET /sensors/crop-cycle/{crop_cycle_id}
 *   GET /satellite/{farm_id}
 *   GET /drone/{farm_id}
 *   GET /evidence/crop-cycle/{crop_cycle_id}
 *   GET /tokens/my-wallet (filter by report match)
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
  RefreshControl,
} from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getReportApi } from '../../api/carbonApi';
import { getCombinedCarbonReport, type CombinedCarbonReport } from '../../api/socApi';
import { formatScore, formatHashShort } from '../../utils/formatters';
import { getSensorsByCycleApi } from '../../api/sensorApi';
import { getSatelliteObservationsApi, getDroneObservationsApi, getEvidenceByCycleApi, type EvidenceFile } from '../../api/observationApi';
import { getMyWalletApi } from '../../api/tokenApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { InfoRow } from '../../components/InfoRow';
import { StatusBadge } from '../../components/StatusBadge';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import type { CarbonReport, SensorReading, SatelliteObservation, DroneObservation, CarbonToken } from '../../types';
import type { FarmerReportsParamList } from '../../navigation/FarmerReportsStack';

type Props = NativeStackScreenProps<FarmerReportsParamList, 'CarbonReportDetail'>;

const ZERO_CREDIT_THRESHOLD_EXPLANATION =
  'This report is verified, but the measured CO₂e reduction is below the 1 tCO₂e threshold required for carbon credit issuance. A zero-credit certificate may still be issued for record-keeping.';

export function CarbonReportDetailScreen({ route }: Props) {
  const { reportId } = route.params;

  const [report, setReport]           = useState<CarbonReport | null>(null);
  const [sensors, setSensors]         = useState<SensorReading[]>([]);
  const [satellite, setSatellite]     = useState<SatelliteObservation[]>([]);
  const [drone, setDrone]             = useState<DroneObservation[]>([]);
  const [evidence, setEvidence]       = useState<EvidenceFile[]>([]);
  const [token, setToken]             = useState<CarbonToken | null>(null);
  const [combined, setCombined]       = useState<CombinedCarbonReport | null>(null);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState('');
  const [refreshing, setRefreshing]   = useState(false);
  const [hashExpanded, setHashExpanded] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      setError('');
      const rep = await getReportApi(reportId);
      setReport(rep);

      // Parallel optional fetches — all gracefully ignored on failure
      const [sensorsR, satR, droneR, evidenceR, walletR, combinedR] = await Promise.allSettled([
        getSensorsByCycleApi(rep.crop_cycle_id, { limit: 200 }),
        getSatelliteObservationsApi(rep.farm_id, { crop_cycle_id: rep.crop_cycle_id, limit: 100 }),
        getDroneObservationsApi(rep.farm_id, { crop_cycle_id: rep.crop_cycle_id, limit: 100 }),
        getEvidenceByCycleApi(rep.crop_cycle_id),
        getMyWalletApi({ limit: 100 }),
        getCombinedCarbonReport(rep.farm_id, rep.crop_cycle_id),
      ]);

      if (sensorsR.status === 'fulfilled') setSensors(sensorsR.value);
      if (satR.status === 'fulfilled') setSatellite(satR.value);
      if (droneR.status === 'fulfilled') setDrone(droneR.value);
      if (evidenceR.status === 'fulfilled') setEvidence(evidenceR.value);
      if (walletR.status === 'fulfilled') {
        const tok = walletR.value.find((t) => t.carbon_report_id === reportId) ?? null;
        setToken(tok);
      }
      if (combinedR.status === 'fulfilled') setCombined(combinedR.value);
    } catch {
      setError('Failed to load report details.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [reportId]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  const onRefresh = () => { setRefreshing(true); fetchAll(); };

  if (loading) return <LoadingView message="Loading report…" />;
  if (error || !report) return <ErrorView message={error || 'Report not found.'} onRetry={fetchAll} />;

  const latestSensor = sensors[0] ?? null;
  const isVerified = report.status === 'VERIFIED';
  const zeroCredits = isVerified && report.estimated_credits === 0;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#fff" colors={['#66bb6a']} />
          }
        >
          {/* Header */}
          <GlassCard style={styles.headerCard} opacity={0.95}>
            <View style={styles.headerRow}>
              <View>
                <Text variant="labelSmall" style={styles.headerSub}>CARBON REPORT #{report.id}</Text>
                <Text variant="titleLarge" style={styles.headerTitle}>
                  Farm #{report.farm_id} · Cycle #{report.crop_cycle_id}
                </Text>
                <Text variant="bodySmall" style={styles.dateText}>
                  {new Date(report.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}
                </Text>
              </View>
              <StatusBadge status={report.status} />
            </View>
          </GlassCard>

          {/* Zero-credit explanation */}
          {zeroCredits && (
            <GlassCard style={styles.warningCard} opacity={0.95}>
              <View style={styles.warningRow}>
                <MaterialCommunityIcons name="information-outline" size={20} color="#e65100" />
                <Text variant="bodySmall" style={styles.warningText}>{ZERO_CREDIT_THRESHOLD_EXPLANATION}</Text>
              </View>
            </GlassCard>
          )}

          {/* Emission Calculations */}
          <SectionHeader icon="molecule-co2" title="Emission Calculation" light />
          <GlassCard opacity={0.9}>
            <InfoRow icon="trending-down" label="Baseline Methane" value={`${report.baseline_methane_kg.toFixed(2)} kg`} />
            <InfoRow icon="gas-cylinder" label="Current Methane" value={`${report.current_methane_kg.toFixed(2)} kg`} />
            <InfoRow icon="arrow-down-circle-outline" label="Methane Reduction" value={`${report.methane_reduction_kg.toFixed(2)} kg`} />
            <InfoRow icon="molecule-co2" label="CO₂e Reduction" value={`${report.co2e_reduction_tonnes.toFixed(4)} tCO₂e`} />
            <InfoRow icon="leaf-circle-outline" label="Estimated Credits" value={report.estimated_credits === 0 ? 'Below threshold (0)' : String(report.estimated_credits)} last />
          </GlassCard>

          {/* SOC Section — Phase 12.5 */}
          <SectionHeader icon="leaf-circle-outline" title="Soil Organic Carbon (SOC)" light />
          <GlassCard opacity={0.9}>
            {combined?.soc_section ? (
              <>
                <InfoRow
                  icon="trending-down"
                  label="Baseline SOC"
                  value={`${combined.soc_section.baseline_soc_percent.toFixed(3)} %`}
                />
                <InfoRow
                  icon="trending-up"
                  label="Current SOC"
                  value={`${combined.soc_section.current_soc_percent.toFixed(3)} %`}
                />
                <InfoRow
                  icon="chart-bar"
                  label="SOC Gain"
                  value={`+${combined.soc_section.soc_gain_percent.toFixed(4)} %`}
                />
                <InfoRow
                  icon="molecule-co2"
                  label="SOC CO₂e"
                  value={`${combined.soc_section.soc_co2e_tonnes.toFixed(4)} tCO₂e`}
                />
                <InfoRow
                  icon="gauge"
                  label="Confidence"
                  value={`${(combined.soc_section.confidence_score * 100).toFixed(0)}%`}
                />
                <InfoRow
                  icon="database-outline"
                  label="Data Sources"
                  value={combined.soc_section.sources_used.length > 0
                    ? combined.soc_section.sources_used.join(', ')
                    : 'Estimated'}
                  last
                />
                <View style={styles.socInfoBox}>
                  <MaterialCommunityIcons name="information-outline" size={14} color="#1565c0" />
                  <Text variant="bodySmall" style={styles.socInfoText}>
                    SOC credits are informational only and are NOT included in token minting in Phase 12.5.
                  </Text>
                </View>
              </>
            ) : (
              <Text variant="bodySmall" style={styles.noDataText}>SOC estimate unavailable.</Text>
            )}
          </GlassCard>

          {/* Combined Credits — Phase 12.5 */}
          <SectionHeader icon="currency-usd" title="Carbon Credits Summary" light />
          <GlassCard opacity={0.9}>
            <InfoRow
              icon="fire"
              label="Methane Credits"
              value={`${report.estimated_credits} tCO₂e (Mintable)`}
            />
            <InfoRow
              icon="leaf-circle-outline"
              label="SOC Credits"
              value={combined
                ? `${combined.soc_credits} tCO₂e (Informational)`
                : '—'}
            />
            <InfoRow
              icon="sigma"
              label="Total Potential Credits"
              value={combined
                ? `${combined.total_potential_credits} tCO₂e`
                : `${report.estimated_credits} tCO₂e`}
              last
            />
            <View style={styles.mintingNoteBox}>
              <MaterialCommunityIcons name="lock-outline" size={14} color="#e65100" />
              <Text variant="bodySmall" style={styles.mintingNoteText}>
                Phase 12.5: Only methane credits ({report.estimated_credits} tCO₂e) are mintable.
                SOC credits will be enabled in a future phase after validation.
              </Text>
            </View>
          </GlassCard>

          {/* Report Hash */}
          <SectionHeader icon="shield-check-outline" title="Report Integrity" light />
          <GlassCard opacity={0.9}>
            <Text variant="labelSmall" style={styles.hashLabel}>REPORT HASH</Text>
            <TouchableOpacity
              onPress={() => setHashExpanded((v) => !v)}
              activeOpacity={0.7}
              style={styles.hashRow}
            >
              <Text variant="bodySmall" style={styles.hashValue} selectable>
                {hashExpanded ? report.report_hash : formatHashShort(report.report_hash)}
              </Text>
              <MaterialCommunityIcons
                name={hashExpanded ? 'chevron-up' : 'chevron-down'}
                size={16}
                color="#aaa"
              />
            </TouchableOpacity>
            {hashExpanded && (
              <Text variant="labelSmall" style={styles.hashHint}>
                Tap to collapse · Long-press the hash to copy
              </Text>
            )}
            {!hashExpanded && (
              <Text variant="labelSmall" style={styles.hashHint}>
                Tap to view full hash
              </Text>
            )}
          </GlassCard>

          {/* Token / Certificate */}
          <SectionHeader icon="certificate-outline" title="Blockchain Token" light />
          <GlassCard opacity={0.9}>
            {token ? (
              <>
                <InfoRow icon="check-circle-outline" label="Token ID" value={`#${token.id} · ${token.token_id}`} />
                <InfoRow icon="certificate" label="Standard" value={token.token_standard} />
                <InfoRow icon="leaf-circle-outline" label="Credits" value={String(token.credit_amount)} />
                <InfoRow icon="bank-outline" label="Status" value={token.status} />
                {token.is_certificate && (
                  <View style={styles.certBadge}>
                    <MaterialCommunityIcons name="certificate" size={16} color="#6a1b9a" />
                    <Text variant="labelSmall" style={styles.certText}>Zero-credit certificate issued</Text>
                  </View>
                )}
                <Text variant="labelSmall" style={styles.txHash} numberOfLines={2}>
                  TX: {token.minted_tx_hash}
                </Text>
              </>
            ) : isVerified ? (
              <View style={styles.pendingTokenBox}>
                <MaterialCommunityIcons name="timer-sand" size={24} color="#e65100" />
                <Text variant="bodyMedium" style={styles.pendingTokenText}>
                  Awaiting FPO/Admin tokenization. Your credits will be issued after minting.
                </Text>
              </View>
            ) : (
              <View style={styles.pendingTokenBox}>
                <MaterialCommunityIcons name="file-clock-outline" size={24} color="#9e9e9e" />
                <Text variant="bodyMedium" style={styles.pendingTokenText}>
                  Token will be issued after report verification.
                </Text>
              </View>
            )}
          </GlassCard>

          {/* MRV Data — Sensors */}
          <SectionHeader icon="access-point-network" title={`MRV Sensor Data (${sensors.length} readings)`} light />
          <GlassCard opacity={0.9}>
            {sensors.length === 0 ? (
              <Text variant="bodySmall" style={styles.noDataText}>No sensor readings available for this cycle.</Text>
            ) : latestSensor ? (
              <>
                <InfoRow label="Total Readings" value={String(sensors.length)} />
                <InfoRow label="Latest Soil Moisture" value={`${latestSensor.soil_moisture.toFixed(1)}%`} />
                <InfoRow label="Latest Temperature" value={`${latestSensor.temperature_c.toFixed(1)} °C`} />
                <InfoRow label="Latest Est. Methane" value={`${latestSensor.estimated_methane.toFixed(4)} kg`} />
                <InfoRow label="Latest Quality Score" value={formatScore(latestSensor.data_quality_score)} last />
              </>
            ) : null}
          </GlassCard>

          {/* Satellite */}
          <SectionHeader icon="satellite-variant" title={`Satellite Observations (${satellite.length})`} light />
          <GlassCard opacity={0.9}>
            {satellite.length === 0 ? (
              <Text variant="bodySmall" style={styles.noDataText}>No satellite data available.</Text>
            ) : (
              <>
                <InfoRow label="Observations" value={String(satellite.length)} />
                <InfoRow label="Latest NDVI" value={satellite[0].ndvi.toFixed(3)} />
                <InfoRow label="Latest Health" value={satellite[0].vegetation_health} last />
              </>
            )}
          </GlassCard>

          {/* Drone */}
          <SectionHeader icon="drone" title={`Drone Observations (${drone.length})`} light />
          <GlassCard opacity={0.9}>
            {drone.length === 0 ? (
              <Text variant="bodySmall" style={styles.noDataText}>No drone data available.</Text>
            ) : (
              <>
                <InfoRow label="Observations" value={String(drone.length)} />
                <InfoRow label="Latest Veg. Cover" value={`${drone[0].vegetation_cover_percent.toFixed(1)}%`} />
                <InfoRow label="Latest Anomaly Score" value={drone[0].anomaly_score.toFixed(2)} last />
              </>
            )}
          </GlassCard>

          {/* Evidence */}
          {evidence.length > 0 && (
            <>
              <SectionHeader icon="file-document-multiple-outline" title={`Evidence Files (${evidence.length})`} light />
              <GlassCard opacity={0.9}>
                {evidence.map((e, i) => (
                  <View key={e.id} style={[styles.evidenceRow, i < evidence.length - 1 && styles.evidenceBorder]}>
                    <MaterialCommunityIcons name="paperclip" size={16} color="#1565c0" />
                    <View style={styles.evidenceText}>
                      <Text variant="labelSmall" style={styles.evidenceType}>{e.file_type}</Text>
                      {e.description && <Text variant="bodySmall" style={styles.evidenceDesc}>{e.description}</Text>}
                    </View>
                  </View>
                ))}
              </GlassCard>
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
  scroll: { paddingTop: 8, paddingBottom: 32 },

  headerCard: { marginTop: 8 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  headerSub: { color: '#888', marginBottom: 2 },
  headerTitle: { fontWeight: '800', color: '#1b5e20', marginBottom: 2 },
  dateText: { color: '#888' },

  warningCard: { borderLeftWidth: 4, borderLeftColor: '#e65100' },
  warningRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  warningText: { flex: 1, color: '#e65100', lineHeight: 18 },

  hashLabel: { color: '#888', marginBottom: 4 },
  hashRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  hashValue: { color: '#555', lineHeight: 18, flex: 1 },
  hashHint: { color: '#bbb', marginTop: 4 },

  certBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 },
  certText: { color: '#6a1b9a' },
  txHash: { color: '#aaa', marginTop: 8, fontFamily: 'monospace' },

  pendingTokenBox: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  pendingTokenText: { flex: 1, color: '#666' },

  noDataText: { color: '#aaa', textAlign: 'center', paddingVertical: 4 },

  evidenceRow: { flexDirection: 'row', gap: 8, paddingVertical: 8, alignItems: 'flex-start' },
  evidenceBorder: { borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  evidenceText: { flex: 1 },
  evidenceType: { color: '#1565c0', fontWeight: '700' },
  evidenceDesc: { color: '#666', marginTop: 2 },

  socInfoBox: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 6,
    marginTop: 10, paddingTop: 10,
    borderTopWidth: 1, borderTopColor: '#e3f2fd',
  },
  socInfoText: { color: '#1565c0', flex: 1, lineHeight: 16 },
  mintingNoteBox: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 6,
    marginTop: 10, paddingTop: 10,
    borderTopWidth: 1, borderTopColor: '#fff3e0',
  },
  mintingNoteText: { color: '#e65100', flex: 1, lineHeight: 16 },

  bottomPad: { height: 16 },
});
