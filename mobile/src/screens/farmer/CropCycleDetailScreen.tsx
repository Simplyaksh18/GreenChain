/**
 * CropCycleDetailScreen — Phase 10A
 * Shows full crop cycle detail + MRV state + report generation workflow.
 *
 * Workflow states:
 *   A: 0 readings          → Demo picker or manual options
 *   B: 1–6 readings        → "Need 7+ readings" + more options
 *   C: ≥7, no report       → "Generate Carbon Report" button
 *   D: report DRAFT        → "Submit for Verification" button
 *   E: report SUBMITTED/VERIFIED/REJECTED → show status
 *
 * MRV Data Actions (always visible):
 *   - Standard Paddy Demo (sensor + satellite + drone simulate together)
 *   - High-Emission Demo with scenario picker (5 livestock scenarios)
 *   - Add Manual Sensor Reading
 *   - Add Manual Satellite Observation
 *   - Add Manual Drone Observation
 *
 * Backend endpoints used:
 *   GET  /sensors/summary/{cycle_id}
 *   GET  /carbon-reports/farm/{farm_id}   (client-filtered by crop_cycle_id)
 *   POST /sensors/simulate
 *   POST /satellite/simulate
 *   POST /drone/simulate
 *   POST /mrv/demo/high-emission
 *   POST /carbon-reports/generate/{crop_cycle_id}
 *   POST /carbon-reports/{report_id}/submit
 *   PATCH /farms/{farm_id}/crop-cycles/{cycle_id}  (via EditCropCycleScreen)
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getCropCyclesApi, harvestCropCycleApi, closeCropCycleApi } from '../../api/farmApi';
import { getSensorSummaryApi, simulateSensorsApi } from '../../api/sensorApi';
import { getReportsByFarmApi, generateReportApi, submitReportApi } from '../../api/carbonApi';
import { getSatelliteObservationsApi, getDroneObservationsApi, generateHighEmissionDemoApi, type HighEmissionScenario } from '../../api/observationApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { InfoRow } from '../../components/InfoRow';
import { StatusBadge } from '../../components/StatusBadge';
import { AppButton } from '../../components/AppButton';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { formatScore, formatDateIN } from '../../utils/formatters';
import type { CropCycle, CarbonReport } from '../../types';
import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';
import apiClient from '../../api/client';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'CropCycleDetail'>;

const MIN_READINGS_FOR_REPORT = 7;

type WorkflowState = 'A' | 'B' | 'C' | 'D' | 'E';

function deriveWorkflowState(readings: number, report: CarbonReport | null): WorkflowState {
  if (readings === 0) return 'A';
  if (readings < MIN_READINGS_FOR_REPORT) return 'B';
  if (!report) return 'C';
  if (report.status === 'DRAFT') return 'D';
  return 'E';
}

export function CropCycleDetailScreen({ route, navigation }: Props) {
  const { cycleId, farmId, farmName, farmStatus } = route.params;

  const [cycle, setCycle]               = useState<CropCycle | null>(null);
  const [sensorCount, setSensorCount]   = useState(0);
  const [satelliteCount, setSatCount]   = useState(0);
  const [droneCount, setDroneCount]     = useState(0);
  const [avgQuality, setAvgQuality]     = useState<number | null>(null);
  const [report, setReport]             = useState<CarbonReport | null>(null);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState('');
  const [refreshing, setRefreshing]     = useState(false);
  const [simulating, setSimulating]       = useState(false);
  const [generating, setGenerating]       = useState(false);
  const [submitting, setSubmitting]       = useState(false);
  const [showDemoPicker, setShowDemoPicker] = useState(false);
  const [highEmitLoading, setHighEmitLoading] = useState(false);
  const [harvesting, setHarvesting] = useState(false);
  const [closing, setClosing] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      setError('');
      const [cyclesR, summaryR, reportsR, satR, droneR] = await Promise.allSettled([
        getCropCyclesApi(farmId),
        getSensorSummaryApi(cycleId),
        getReportsByFarmApi(farmId, { limit: 100 }),
        getSatelliteObservationsApi(farmId, { crop_cycle_id: cycleId, limit: 100 }),
        getDroneObservationsApi(farmId, { crop_cycle_id: cycleId, limit: 100 }),
      ]);

      if (cyclesR.status === 'fulfilled') {
        setCycle(cyclesR.value.find((c) => c.id === cycleId) ?? null);
      }
      if (summaryR.status === 'fulfilled') {
        setSensorCount(summaryR.value.total_readings);
        setAvgQuality(summaryR.value.avg_data_quality_score);
      } else {
        setSensorCount(0);
        setAvgQuality(null);
      }
      if (reportsR.status === 'fulfilled') {
        const cycleReports = reportsR.value
          .filter((r) => r.crop_cycle_id === cycleId)
          .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        setReport(cycleReports[0] ?? null);
      }
      if (satR.status === 'fulfilled') setSatCount(satR.value.length);
      if (droneR.status === 'fulfilled') setDroneCount(droneR.value.length);
    } catch {
      setError('Failed to load crop cycle details.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [cycleId, farmId]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  const onRefresh = () => { setRefreshing(true); fetchAll(); };

  /** Generate Demo MRV Data: sensor + satellite + drone simulate together */
  const handleGenerateDemo = () => {
    Alert.alert(
      'Generate Demo MRV Data',
      'This will generate 30 days of sensor readings and 6 satellite & drone observations for this crop cycle.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Generate',
          onPress: async () => {
            try {
              setSimulating(true);
              const [sensorR, satR, droneR] = await Promise.allSettled([
                simulateSensorsApi({ farm_id: farmId, crop_cycle_id: cycleId, number_of_days: 30 }),
                apiClient.post('/satellite/simulate', { farm_id: farmId, crop_cycle_id: cycleId, number_of_observations: 6 }),
                apiClient.post('/drone/simulate', { farm_id: farmId, crop_cycle_id: cycleId, number_of_observations: 4 }),
              ]);

              const sensorOk  = sensorR.status === 'fulfilled';
              const satOk     = satR.status === 'fulfilled';
              const droneOk   = droneR.status === 'fulfilled';

              const sensorMsg = sensorOk
                ? `✓ ${sensorR.value.generated_readings} sensor readings`
                : `✗ Sensor data failed`;
              const satMsg    = satOk
                ? `✓ ${satR.value.data.created} satellite observations`
                : `✗ Satellite data failed`;
              const droneMsg  = droneOk
                ? `✓ ${droneR.value.data.created} drone observations`
                : `✗ Drone data failed`;

              Alert.alert(
                'Demo MRV Data Generated',
                `${sensorMsg}\n${satMsg}\n${droneMsg}`,
              );
              await fetchAll();
            } catch (e: any) {
              Alert.alert('Error', 'Failed to generate demo data.');
            } finally {
              setSimulating(false);
            }
          },
        },
      ],
    );
  };

  const HIGH_EMISSION_SCENARIOS: { key: HighEmissionScenario; label: string; hint: string }[] = [
    { key: 'DAIRY_SRI_LOW',           label: 'Dairy + SRI Low Emission',   hint: '~6 credits · 12 dairy cattle' },
    { key: 'DAIRY_BIODIGESTER',       label: 'Dairy + Biodigester',        hint: '~14 credits · 20 Holstein' },
    { key: 'MIXED_LIVESTOCK_BIOCHAR', label: 'Mixed Livestock + Biochar',  hint: '~16 credits · cattle + goats' },
    { key: 'BUFFALO_BIODIGESTER',     label: 'Buffalo + Biodigester',      hint: '~11 credits · Murrah buffalo' },
    { key: 'EDGE_CERTIFICATE_ONLY',   label: 'Edge: Certificate Only',     hint: '0 credits · below threshold' },
  ];

  const handleHighEmissionScenario = async (scenario: HighEmissionScenario) => {
    setShowDemoPicker(false);
    try {
      setHighEmitLoading(true);
      const result = await generateHighEmissionDemoApi(farmId, cycleId, scenario);
      // Refresh MRV counts before showing the alert so the screen is already up-to-date
      await fetchAll();
      const creditsLabel =
        result.expected_credits === 0
          ? '0 (certificate only — below 1 tCO₂e threshold)'
          : String(result.expected_credits);
      Alert.alert(
        '⚠️ High-Emission Demo Generated',
        `Scenario: ${result.scenario_description}\n\n` +
        `✓ ${result.sensor_readings_generated} sensor readings\n` +
        `✓ ${result.satellite_observations_generated} satellite observations\n` +
        `✓ ${result.drone_observations_generated} drone observations\n\n` +
        `Expected CO₂e reduction: ${result.expected_co2e_reduction_tonnes.toFixed(2)} tCO₂e\n` +
        `Expected credits: ${creditsLabel}\n\n` +
        `Tap "Generate Carbon Report" below to produce a tradeable report.`,
        [
          { text: 'OK', style: 'cancel' },
          ...(result.expected_credits > 0
            ? [{
                text: 'Generate Carbon Report',
                onPress: () => handleGenerateReport(),
              }]
            : []),
        ],
      );
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? 'Failed to generate high-emission demo data.';
      Alert.alert('Error', msg);
    } finally {
      setHighEmitLoading(false);
    }
  };

  const handleGenerateReport = async () => {
    Alert.alert(
      'Generate Carbon Report',
      `Generate a carbon credit report for this crop cycle using ${sensorCount} sensor readings?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Generate Report',
          onPress: async () => {
            try {
              setGenerating(true);
              const newReport = await generateReportApi(cycleId);
              setReport(newReport);
              Alert.alert(
                'Report Generated ✓',
                `Carbon Report #${newReport.id} created.\n\nCO₂e Reduction: ${newReport.co2e_reduction_tonnes.toFixed(4)} tCO₂e\nEstimated Credits: ${newReport.estimated_credits}\nStatus: DRAFT\n\nYou can now submit it for verification.`,
              );
            } catch (e: any) {
              const msg = e?.response?.data?.detail ?? 'Failed to generate report.';
              Alert.alert('Report Generation Failed', msg);
            } finally {
              setGenerating(false);
            }
          },
        },
      ],
    );
  };

  const handleHarvestCycle = () => {
    const today = new Date().toISOString().split('T')[0];
    Alert.alert(
      'Mark as Harvested',
      `Mark crop cycle #${cycleId} as harvested? Today's date (${today}) will be recorded as harvest date.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Mark Harvested',
          onPress: async () => {
            try {
              setHarvesting(true);
              const updated = await harvestCropCycleApi(farmId, cycleId, { harvest_date: today });
              setCycle(updated);
              Alert.alert('Harvested', `Cycle #${cycleId} is now marked as HARVESTED.`);
            } catch (e: any) {
              Alert.alert('Error', e?.response?.data?.detail ?? 'Failed to mark as harvested.');
            } finally {
              setHarvesting(false);
            }
          },
        },
      ],
    );
  };

  const handleCloseCycle = () => {
    Alert.alert(
      'Close Cycle',
      `Close crop cycle #${cycleId}? This is the final step after verification is complete.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Close Cycle',
          style: 'destructive',
          onPress: async () => {
            try {
              setClosing(true);
              const updated = await closeCropCycleApi(farmId, cycleId);
              setCycle(updated);
              Alert.alert('Cycle Closed', `Cycle #${cycleId} is now CLOSED.`);
            } catch (e: any) {
              Alert.alert('Error', e?.response?.data?.detail ?? 'Failed to close cycle.');
            } finally {
              setClosing(false);
            }
          },
        },
      ],
    );
  };

  const handleSubmitReport = async (reportId: number) => {
    Alert.alert(
      'Submit for Verification',
      `Submit Report #${reportId} for verification?\n\nOnce submitted it cannot be edited. A risk assessment will be created automatically.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Submit',
          onPress: async () => {
            try {
              setSubmitting(true);
              const updated = await submitReportApi(reportId);
              setReport(updated);
              Alert.alert('Submitted ✓', `Report #${reportId} is now SUBMITTED and awaiting verifier review.`);
            } catch (e: any) {
              const msg = e?.response?.data?.detail ?? 'Failed to submit report.';
              Alert.alert('Submit Failed', msg);
            } finally {
              setSubmitting(false);
            }
          },
        },
      ],
    );
  };

  if (loading) return <LoadingView message="Loading crop cycle…" />;
  if (error) return <ErrorView message={error} onRetry={fetchAll} />;
  if (!cycle) return <ErrorView message="Crop cycle not found." onRetry={fetchAll} />;

  const wfState = deriveWorkflowState(sensorCount, report);

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
              <View style={styles.headerLeft}>
                <Text variant="labelSmall" style={styles.idLabel}>CROP CYCLE #{cycle.id}</Text>
                <Text variant="titleMedium" style={styles.cropTitle}>{cycle.crop_type} · {cycle.season}</Text>
                <Text variant="bodySmall" style={styles.farmName}>{farmName}</Text>
              </View>
              <StatusBadge status={cycle.status} />
            </View>
          </GlassCard>

          {/* Cycle Details */}
          <SectionHeader icon="information-outline" title="Cycle Details" light />
          <GlassCard opacity={0.9}>
            <InfoRow label="Crop Type"          value={cycle.crop_type} />
            <InfoRow label="Season"             value={cycle.season} />
            <InfoRow label="Status"             value={cycle.status} />
            <InfoRow label="Start Date"         value={formatDateIN(cycle.start_date)} />
            <InfoRow label="End Date"           value={cycle.end_date ? formatDateIN(cycle.end_date) : 'Ongoing'} />
            <InfoRow label="Baseline Method"    value={cycle.baseline_method} />
            <InfoRow label="Reduction Practice" value={cycle.reduction_practice} last />
          </GlassCard>

          {/* Lifecycle Actions */}
          <View style={styles.editRow}>
            <View style={styles.lifecycleRow}>
              <AppButton
                mode="outlined"
                onPress={() => navigation.navigate('EditCropCycle', { cycleId, farmId, farmName })}
                icon="pencil-outline"
                style={[styles.editBtn, styles.lifecycleBtn]}
              >
                Edit
              </AppButton>
              {(cycle.status === 'ACTIVE' || cycle.status === 'PLANNED') && (
                <AppButton
                  mode="contained"
                  buttonColor="#e65100"
                  icon="grain"
                  onPress={handleHarvestCycle}
                  loading={harvesting}
                  disabled={harvesting || closing}
                  style={styles.lifecycleBtn}
                >
                  Harvest
                </AppButton>
              )}
              {(cycle.status === 'HARVESTED' || cycle.status === 'VERIFIED') && (
                <AppButton
                  mode="outlined"
                  icon="lock-outline"
                  onPress={handleCloseCycle}
                  loading={closing}
                  disabled={harvesting || closing}
                  style={[styles.lifecycleBtn, styles.closeBtn]}
                >
                  Close Cycle
                </AppButton>
              )}
            </View>
          </View>

          {/* MRV Summary */}
          <SectionHeader icon="access-point-network" title="MRV Data Summary" light />
          <GlassCard opacity={0.9}>
            <InfoRow icon="counter"           label="Sensor Readings"        value={String(sensorCount)} />
            <InfoRow icon="satellite-variant" label="Satellite Observations" value={String(satelliteCount)} />
            <InfoRow icon="drone"             label="Drone Observations"     value={String(droneCount)} />
            {avgQuality !== null && (
              <InfoRow icon="check-decagram-outline" label="Avg Sensor Quality" value={formatScore(avgQuality, 2)} last />
            )}
            {sensorCount > 0 && sensorCount < MIN_READINGS_FOR_REPORT && (
              <View style={styles.insufficientRow}>
                <MaterialCommunityIcons name="alert-outline" size={14} color="#e65100" />
                <Text variant="labelSmall" style={styles.insufficientText}>
                  {MIN_READINGS_FOR_REPORT - sensorCount} more reading{MIN_READINGS_FOR_REPORT - sensorCount !== 1 ? 's' : ''} needed to generate a carbon report.
                </Text>
              </View>
            )}
          </GlassCard>

          {/* MRV Data Actions */}
          <SectionHeader icon="database-plus-outline" title="Add MRV Data" light />
          <GlassCard opacity={0.9} style={styles.mrvActionsCard}>

            {/* ── Demo Mode row ── */}
            <Text variant="labelMedium" style={styles.demoSectionLabel}>MRV Demo Mode</Text>

            <AppButton
              mode="contained"
              buttonColor="#1565c0"
              icon="database-arrow-right-outline"
              onPress={handleGenerateDemo}
              loading={simulating}
              disabled={simulating || highEmitLoading}
              style={styles.mrvBtn}
            >
              Standard Paddy Demo
            </AppButton>
            <Text variant="labelSmall" style={styles.mrvHint}>
              30 sensor readings + 6 satellite + 4 drone · paddy emission model
            </Text>

            <AppButton
              mode="contained"
              buttonColor="#6a1b9a"
              icon="cow"
              onPress={() => setShowDemoPicker(true)}
              loading={highEmitLoading}
              disabled={simulating || highEmitLoading}
              style={styles.mrvBtn}
            >
              High-Emission Demo ⚠️
            </AppButton>
            <Text variant="labelSmall" style={styles.mrvHint}>
              Livestock/manure scenarios · engineers 5–20 tCO₂e · DEMO DATA ONLY
            </Text>

            <View style={styles.mrvDivider} />

            {/* ── Manual inputs ── */}
            <Text variant="labelMedium" style={styles.demoSectionLabel}>Manual Entry</Text>
            <AppButton
              mode="outlined"
              icon="access-point-network"
              onPress={() => navigation.navigate('ManualSensorReading', { cycleId, farmId, farmName })}
              style={styles.mrvBtn}
            >
              Add Manual Sensor Reading
            </AppButton>
            <AppButton
              mode="outlined"
              icon="satellite-variant"
              onPress={() => navigation.navigate('ManualSatelliteObservation', { cycleId, farmId, farmName })}
              style={styles.mrvBtn}
            >
              Add Satellite Observation
            </AppButton>
            <AppButton
              mode="outlined"
              icon="drone"
              onPress={() => navigation.navigate('ManualDroneObservation', { cycleId, farmId, farmName })}
              style={styles.mrvBtn}
            >
              Add Drone Observation
            </AppButton>
          </GlassCard>

          {/* ── High-Emission Scenario Picker Modal ── */}
          <Modal
            visible={showDemoPicker}
            transparent
            animationType="slide"
            onRequestClose={() => setShowDemoPicker(false)}
          >
            <Pressable style={styles.modalOverlay} onPress={() => setShowDemoPicker(false)}>
              <Pressable style={styles.modalSheet} onPress={() => {}}>
                <Text variant="titleMedium" style={styles.modalTitle}>
                  ⚠️ High-Emission Demo
                </Text>
                <Text variant="bodySmall" style={styles.modalSubtitle}>
                  Select a livestock scenario. Data is labelled DEMO_HIGH_EMISSION and is for testing only.
                </Text>
                {HIGH_EMISSION_SCENARIOS.map((s) => (
                  <Pressable
                    key={s.key}
                    style={styles.scenarioRow}
                    onPress={() => handleHighEmissionScenario(s.key)}
                  >
                    <View style={styles.scenarioTextCol}>
                      <Text variant="labelMedium" style={styles.scenarioLabel}>{s.label}</Text>
                      <Text variant="labelSmall" style={styles.scenarioHint}>{s.hint}</Text>
                    </View>
                    <MaterialCommunityIcons name="chevron-right" size={20} color="#9e9e9e" />
                  </Pressable>
                ))}
                <AppButton
                  mode="text"
                  onPress={() => setShowDemoPicker(false)}
                  style={{ marginTop: 8 }}
                >
                  Cancel
                </AppButton>
              </Pressable>
            </Pressable>
          </Modal>

          {/* Carbon Report Workflow */}
          <SectionHeader icon="file-chart-outline" title="Carbon Report Workflow" light />
          <GlassCard opacity={0.9}>
            {wfState === 'A' && (
              <View style={styles.workflowBox}>
                <MaterialCommunityIcons name="access-point-network-off" size={32} color="#9e9e9e" />
                <Text variant="labelMedium" style={styles.wfTitle}>No MRV Data Yet</Text>
                <Text variant="bodySmall" style={styles.wfMsg}>
                  No sensor readings found. Use Standard Paddy Demo, High-Emission Demo, or add readings manually above.
                </Text>
              </View>
            )}

            {wfState === 'B' && (
              <View style={styles.workflowBox}>
                <MaterialCommunityIcons name="timer-sand" size={32} color="#e65100" />
                <Text variant="labelMedium" style={styles.wfTitle}>More Data Needed</Text>
                <Text variant="bodySmall" style={styles.wfMsg}>
                  {sensorCount} reading{sensorCount !== 1 ? 's' : ''} collected. At least {MIN_READINGS_FOR_REPORT} sensor readings are required.
                </Text>
              </View>
            )}

            {wfState === 'C' && (
              <View style={styles.workflowBox}>
                <MaterialCommunityIcons name="file-chart-check-outline" size={32} color="#2e7d32" />
                <Text variant="labelMedium" style={styles.wfTitle}>Ready for Report Generation</Text>
                <Text variant="bodySmall" style={styles.wfMsg}>
                  {sensorCount} sensor readings collected. Generate your carbon credit report.
                </Text>
                <AppButton
                  mode="contained"
                  buttonColor="#2e7d32"
                  icon="file-chart-outline"
                  onPress={handleGenerateReport}
                  loading={generating}
                  disabled={generating}
                  style={styles.wfBtn}
                >
                  Generate Carbon Report
                </AppButton>
              </View>
            )}

            {wfState === 'D' && report && (
              <View style={styles.workflowBox}>
                <MaterialCommunityIcons name="file-clock-outline" size={32} color="#1565c0" />
                <Text variant="labelMedium" style={styles.wfTitle}>Report Ready for Submission</Text>
                <View style={styles.reportSummaryCard}>
                  <InfoRow label="Report #"       value={String(report.id)} />
                  <InfoRow label="CO₂e Reduction" value={`${report.co2e_reduction_tonnes.toFixed(4)} tCO₂e`} />
                  <InfoRow label="Est. Credits"   value={report.estimated_credits === 0 ? 'Below threshold (0)' : String(report.estimated_credits)} />
                  <InfoRow label="Status"         value={report.status} last />
                </View>
                {farmStatus && farmStatus !== 'APPROVED' && (
                  <View style={styles.approvalBanner}>
                    <MaterialCommunityIcons name="clock-alert-outline" size={16} color="#b45309" />
                    <Text variant="bodySmall" style={styles.approvalBannerText}>
                      Your farm is awaiting FPO approval. Verification can only start after the farm is approved.
                    </Text>
                  </View>
                )}
                <AppButton
                  mode="contained"
                  buttonColor="#1565c0"
                  icon="send-outline"
                  onPress={() => handleSubmitReport(report.id)}
                  loading={submitting}
                  disabled={submitting || (farmStatus !== undefined && farmStatus !== 'APPROVED')}
                  style={styles.wfBtn}
                >
                  Submit for Verification
                </AppButton>
              </View>
            )}

            {wfState === 'E' && report && (
              <View style={styles.workflowBox}>
                <MaterialCommunityIcons
                  name={report.status === 'VERIFIED' ? 'check-circle' : report.status === 'REJECTED' ? 'close-circle' : 'timer-sand'}
                  size={32}
                  color={report.status === 'VERIFIED' ? '#2e7d32' : report.status === 'REJECTED' ? '#c62828' : '#e65100'}
                />
                <View style={styles.reportSummaryCard}>
                  <InfoRow label="Report #"       value={String(report.id)} />
                  <InfoRow label="CO₂e Reduction" value={`${report.co2e_reduction_tonnes.toFixed(4)} tCO₂e`} />
                  <InfoRow label="Est. Credits"   value={report.estimated_credits === 0 ? 'Below threshold (0)' : String(report.estimated_credits)} />
                  <InfoRow label="Status"         value={report.status} last />
                </View>
                {report.status === 'REJECTED' && (
                  <Text variant="bodySmall" style={styles.rejectedNote}>
                    This report was rejected. You may generate a new report with corrected data.
                  </Text>
                )}
                {report.status === 'VERIFIED' && (
                  <Text variant="bodySmall" style={styles.verifiedNote}>
                    ✓ Report verified. Your FPO can now mint a carbon token.
                  </Text>
                )}
              </View>
            )}
          </GlassCard>

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
  headerLeft: { flex: 1, marginRight: 10 },
  idLabel: { color: '#888', marginBottom: 2 },
  cropTitle: { fontWeight: '800', color: '#1b5e20', marginBottom: 2 },
  farmName: { color: '#555' },

  editRow: { marginHorizontal: 16, marginBottom: 4 },
  editBtn: { borderColor: '#2e7d32' },
  lifecycleRow: { flexDirection: 'row', gap: 8 },
  lifecycleBtn: { flex: 1 },
  closeBtn: { borderColor: '#546e7a' },

  insufficientRow: { flexDirection: 'row', gap: 6, alignItems: 'center', marginTop: 8 },
  insufficientText: { flex: 1, color: '#e65100' },

  mrvActionsCard: { gap: 4 },
  mrvBtn: { marginBottom: 4 },
  mrvHint: { color: '#888', textAlign: 'center', marginTop: 2, marginBottom: 8 },
  mrvDivider: { height: 1, backgroundColor: '#e0e0e0', marginVertical: 8 },
  demoSectionLabel: { color: '#555', fontWeight: '700', marginBottom: 4, marginTop: 4 },

  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    paddingBottom: 36,
  },
  modalTitle: { fontWeight: '800', color: '#333', marginBottom: 4 },
  modalSubtitle: { color: '#888', marginBottom: 16, lineHeight: 18 },
  scenarioRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  scenarioTextCol: { flex: 1 },
  scenarioLabel: { fontWeight: '600', color: '#1a1a1a' },
  scenarioHint: { color: '#888', marginTop: 2 },

  workflowBox: { alignItems: 'center', gap: 10, paddingVertical: 8 },
  wfTitle: { fontWeight: '700', color: '#333', textAlign: 'center' },
  wfMsg: { color: '#666', textAlign: 'center', lineHeight: 20, paddingHorizontal: 8 },
  wfBtn: { marginTop: 4, alignSelf: 'stretch' },
  approvalBanner: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 8,
    backgroundColor: '#fef3c7', borderRadius: 8,
    padding: 10, alignSelf: 'stretch',
  },
  approvalBannerText: { flex: 1, color: '#92400e', lineHeight: 18 },

  reportSummaryCard: {
    alignSelf: 'stretch',
    backgroundColor: 'rgba(0,0,0,0.04)',
    borderRadius: 8, marginVertical: 4, overflow: 'hidden',
  },

  rejectedNote: { color: '#c62828', textAlign: 'center', lineHeight: 20 },
  verifiedNote: { color: '#2e7d32', textAlign: 'center', fontWeight: '600' },

  bottomPad: { height: 16 },
});
