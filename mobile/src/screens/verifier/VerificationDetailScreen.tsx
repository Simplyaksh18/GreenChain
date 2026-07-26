/**
 * VerificationDetailScreen — Phase 10 UX
 *
 * Displays full verification detail with:
 *  1. Risk Assessment — score, level, recommendation
 *  2. Risk Breakdown — each factor that contributed to the score (from backend)
 *  3. Evidence Summary — sensor/satellite/drone counts, quality, evidence files
 *  4. Carbon Calculation — baseline, current, reduction, CO₂e, credits
 *  5. Details / Verifier Audit — who verified, when, remarks
 *  6. Decision panel — approve / reject (PENDING only)
 *
 * Endpoint: GET /verification/{id}
 * Returns enriched fields: risk_factors[], sensor_count, satellite_count,
 *   drone_count, avg_quality_score, num_evidence_files, baseline_methane_kg,
 *   current_methane_kg, methane_reduction_kg, co2e_reduction_tonnes,
 *   estimated_credits, verifier_name
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { Text, TextInput } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getVerificationApi, approveVerificationApi, rejectVerificationApi } from '../../api/verificationApi';
import { getReportDetailApi } from '../../api/farmApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { InfoRow } from '../../components/InfoRow';
import { StatusBadge } from '../../components/StatusBadge';
import { AppButton } from '../../components/AppButton';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import type { VerificationRequest } from '../../types';

// ── Report Detail types ───────────────────────────────────────────────────────
interface ReportDetailEvidence {
  id: number;
  file_url: string;
  file_type: string;
  evidence_type: string | null;
  description: string | null;
  file_hash: string | null;
  created_at: string | null;
}

interface ReportDetail {
  report: {
    id: number;
    status: string;
    baseline_methane_kg: number;
    current_methane_kg: number;
    methane_reduction_kg: number;
    co2e_reduction_tonnes: number;
    estimated_credits: number;
    report_hash: string | null;
    created_at: string | null;
  };
  farm: {
    id: number;
    farm_name: string;
    village: string;
    district: string;
    area_hectares: number | null;
    farm_status: string;
  };
  crop_cycle: {
    id: number;
    crop_type: string;
    season: string;
    start_date: string | null;
    end_date: string | null;
    baseline_method: string;
    reduction_practice: string;
  };
  evidence_files: ReportDetailEvidence[];
}
import type { VerifierStackParamList } from '../../navigation/VerifierStack';

type Props = NativeStackScreenProps<VerifierStackParamList, 'VerificationDetail'>;

const RISK_COLOR: Record<string, string> = {
  LOW: '#2e7d32',
  MEDIUM: '#e65100',
  HIGH: '#c62828',
};

const REC_ICON: Record<string, keyof typeof MaterialCommunityIcons.glyphMap> = {
  APPROVE: 'check-circle-outline',
  MANUAL_REVIEW: 'magnify-scan',
  REJECT: 'close-circle-outline',
};

const REC_COLOR: Record<string, string> = {
  APPROVE: '#2e7d32',
  MANUAL_REVIEW: '#e65100',
  REJECT: '#c62828',
};

function fmtDate(iso: string | null | undefined, showTime = false): string {
  if (!iso) return '—';
  const d = new Date(iso);
  const dateStr = d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  if (!showTime) return dateStr;
  const timeStr = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  return `${dateStr}, ${timeStr}`;
}

// ── Risk Breakdown Component ──────────────────────────────────────────────────

function RiskBreakdown({ factors, totalScore }: { factors: string[]; totalScore: number }) {
  const riskColor = totalScore <= 30 ? '#2e7d32' : totalScore <= 65 ? '#e65100' : '#c62828';

  if (factors.length === 0) {
    return (
      <GlassCard opacity={0.9} style={styles.breakdownCard}>
        <View style={styles.breakdownZero}>
          <MaterialCommunityIcons name="check-circle-outline" size={20} color="#2e7d32" />
          <Text variant="bodySmall" style={styles.breakdownZeroText}>
            No risk factors triggered. All checks passed.
          </Text>
        </View>
      </GlassCard>
    );
  }

  return (
    <GlassCard opacity={0.9} style={styles.breakdownCard}>
      {factors.map((factor, idx) => {
        // Parse "+NN" from end of string like "No evidence files uploaded (+20)"
        const match = factor.match(/\(\+(\d+)\)$/);
        const points = match ? parseInt(match[1], 10) : 0;
        const label = factor.replace(/\s*\(\+\d+\)$/, '');
        return (
          <View
            key={idx}
            style={[styles.factorRow, idx < factors.length - 1 && styles.factorBorder]}
          >
            <MaterialCommunityIcons name="alert-outline" size={14} color="#e65100" />
            <Text variant="bodySmall" style={styles.factorLabel}>{label}</Text>
            <View style={styles.factorPoints}>
              <Text variant="labelSmall" style={styles.factorPointsText}>+{points}</Text>
            </View>
          </View>
        );
      })}
      <View style={[styles.factorRow, styles.factorTotal]}>
        <Text variant="labelMedium" style={styles.factorTotalLabel}>TOTAL RISK SCORE</Text>
        <Text variant="labelMedium" style={[styles.factorTotalValue, { color: riskColor }]}>
          {totalScore} / 100
        </Text>
      </View>
    </GlassCard>
  );
}

// ── Evidence Summary Card ─────────────────────────────────────────────────────

function EvidenceSummary({ item }: { item: VerificationRequest }) {
  const checks: { label: string; value: string; ok: boolean }[] = [
    {
      label: 'Sensor Readings',
      value: item.sensor_count != null ? String(item.sensor_count) : '—',
      ok: (item.sensor_count ?? 0) >= 14,
    },
    {
      label: 'Satellite Observations',
      value: item.satellite_count != null ? String(item.satellite_count) : '—',
      ok: (item.satellite_count ?? 0) >= 1,
    },
    {
      label: 'Drone Observations',
      value: item.drone_count != null ? String(item.drone_count) : '—',
      ok: (item.drone_count ?? 0) >= 1,
    },
    {
      label: 'Avg Sensor Quality',
      value: item.avg_quality_score != null ? `${item.avg_quality_score.toFixed(1)} / 100` : '—',
      ok: (item.avg_quality_score ?? 0) >= 70,
    },
    {
      label: 'Evidence Files',
      value: item.num_evidence_files != null ? String(item.num_evidence_files) : '—',
      ok: (item.num_evidence_files ?? 0) > 0,
    },
  ];

  return (
    <GlassCard opacity={0.9}>
      {checks.map((c, i) => (
        <View key={c.label} style={[styles.evidRow, i < checks.length - 1 && styles.evidBorder]}>
          <MaterialCommunityIcons
            name={c.ok ? 'check-circle-outline' : 'alert-circle-outline'}
            size={16}
            color={c.ok ? '#2e7d32' : '#e65100'}
          />
          <Text variant="bodySmall" style={styles.evidLabel}>{c.label}</Text>
          <Text variant="labelSmall" style={[styles.evidValue, { color: c.ok ? '#2e7d32' : '#e65100' }]}>
            {c.value}
          </Text>
        </View>
      ))}
    </GlassCard>
  );
}

// ── Calculation Breakdown Card ────────────────────────────────────────────────

function CalcBreakdown({ item }: { item: VerificationRequest }) {
  if (item.baseline_methane_kg == null) {
    return (
      <GlassCard opacity={0.9}>
        <Text variant="bodySmall" style={{ color: '#aaa', padding: 4 }}>
          Calculation data not available.
        </Text>
      </GlassCard>
    );
  }

  const GWP = 27.2;
  const steps: { label: string; formula: string; value: string }[] = [
    {
      label: 'Baseline Methane',
      formula: 'avg(first 7 sensor readings)',
      value: `${item.baseline_methane_kg.toFixed(4)} kg CH₄/day`,
    },
    {
      label: 'Current Methane',
      formula: 'avg(last 7 sensor readings)',
      value: `${item.current_methane_kg?.toFixed(4) ?? '—'} kg CH₄/day`,
    },
    {
      label: 'Methane Reduction',
      formula: 'max(0, baseline − current)',
      value: `${item.methane_reduction_kg?.toFixed(4) ?? '—'} kg CH₄/day`,
    },
    {
      label: 'CO₂e Conversion',
      formula: `reduction × GWP(${GWP}) / 1000`,
      value: `${item.co2e_reduction_tonnes?.toFixed(6) ?? '—'} tCO₂e`,
    },
    {
      label: 'Credits Issued',
      formula: 'floor(co2e_reduction_tonnes)',
      value: item.estimated_credits != null
        ? (item.estimated_credits === 0 ? '0 (certificate only)' : String(item.estimated_credits))
        : '—',
    },
  ];

  return (
    <GlassCard opacity={0.9}>
      {steps.map((s, i) => (
        <View key={s.label} style={[styles.calcRow, i < steps.length - 1 && styles.calcBorder]}>
          <View style={styles.calcLeft}>
            <Text variant="labelSmall" style={styles.calcStep}>{i + 1}</Text>
          </View>
          <View style={styles.calcMiddle}>
            <Text variant="labelMedium" style={styles.calcLabel}>{s.label}</Text>
            <Text variant="labelSmall" style={styles.calcFormula}>{s.formula}</Text>
          </View>
          <Text variant="bodySmall" style={styles.calcValue}>{s.value}</Text>
        </View>
      ))}
    </GlassCard>
  );
}

// ── Main Screen ───────────────────────────────────────────────────────────────

export function VerificationDetailScreen({ route, navigation }: Props) {
  const { verificationId } = route.params;

  const [item, setItem] = useState<VerificationRequest | null>(null);
  const [reportDetail, setReportDetail] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [remarks, setRemarks] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const data = await getVerificationApi(verificationId);
      setItem(data);
      // Fetch report detail (farm + evidence files) — non-blocking, best-effort
      if (data.carbon_report_id) {
        try {
          const detail = await getReportDetailApi(data.carbon_report_id);
          setReportDetail(detail);
        } catch {
          // report detail is supplemental — don't block on failure
        }
      }
    } catch {
      setError('Failed to load verification details.');
    } finally {
      setLoading(false);
    }
  }, [verificationId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleApprove = async () => {
    if (!item) return;
    Alert.alert(
      'Approve Verification',
      `Approve Report #${item.carbon_report_id}?\n\nThis will mark the report as VERIFIED and allow the FPO to mint a carbon token.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Approve',
          onPress: async () => {
            try {
              setSubmitting(true);
              await approveVerificationApi(item.id, remarks.trim() || undefined);
              Alert.alert('Approved ✓', 'Verification approved. The FPO can now mint a carbon token.', [
                { text: 'OK', onPress: () => navigation.goBack() },
              ]);
            } catch (e: any) {
              Alert.alert('Error', e?.response?.data?.detail ?? 'Failed to approve.');
            } finally {
              setSubmitting(false);
            }
          },
        },
      ],
    );
  };

  const handleReject = async () => {
    if (!item) return;
    if (!remarks.trim()) {
      Alert.alert('Remarks Required', 'Please provide a reason for rejection.');
      return;
    }
    Alert.alert(
      'Reject Verification',
      `Reject Report #${item.carbon_report_id}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reject',
          style: 'destructive',
          onPress: async () => {
            try {
              setSubmitting(true);
              await rejectVerificationApi(item.id, remarks.trim());
              Alert.alert('Rejected', 'Verification rejected.', [
                { text: 'OK', onPress: () => navigation.goBack() },
              ]);
            } catch (e: any) {
              Alert.alert('Error', e?.response?.data?.detail ?? 'Failed to reject.');
            } finally {
              setSubmitting(false);
            }
          },
        },
      ],
    );
  };

  if (loading) return <LoadingView message="Loading verification…" />;
  if (error || !item) return <ErrorView message={error || 'Not found'} onRetry={fetchData} />;

  const isPending = item.status === 'PENDING';
  const riskColor = RISK_COLOR[item.risk_level] ?? '#555';
  const recIcon = REC_ICON[item.recommendation] ?? 'help-circle-outline';
  const recColor = REC_COLOR[item.recommendation] ?? '#555';

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ScrollView contentContainerStyle={styles.scroll}>

            {/* ── Status Banner ──────────────────────────────────────── */}
            <GlassCard style={styles.statusCard} opacity={0.95}>
              <View style={styles.statusRow}>
                <View>
                  <Text variant="labelSmall" style={styles.statusLabel}>VERIFICATION #{item.id}</Text>
                  <Text variant="titleLarge" style={styles.reportRef}>
                    Carbon Report #{item.carbon_report_id}
                  </Text>
                  <Text variant="labelSmall" style={styles.submittedText}>
                    Submitted {fmtDate(item.created_at)}
                  </Text>
                </View>
                <StatusBadge status={item.status} />
              </View>
            </GlassCard>

            {/* ── Risk Assessment ────────────────────────────────────── */}
            <SectionHeader icon="alert-circle-outline" title="Risk Assessment" light />
            <GlassCard style={[styles.riskCard, { borderLeftColor: riskColor }]} opacity={0.92}>
              <View style={styles.riskTopRow}>
                <View style={[styles.riskBadge, { backgroundColor: riskColor + '18' }]}>
                  <MaterialCommunityIcons name="shield-alert-outline" size={22} color={riskColor} />
                  <Text style={[styles.riskLevel, { color: riskColor }]}>{item.risk_level}</Text>
                </View>
                <View style={styles.scoreWrap}>
                  <Text variant="displaySmall" style={[styles.riskScore, { color: riskColor }]}>
                    {item.risk_score}
                  </Text>
                  <Text variant="labelSmall" style={styles.riskScoreLabel}>/ 100</Text>
                </View>
              </View>
              <View style={styles.recRow}>
                <MaterialCommunityIcons name={recIcon} size={16} color={recColor} />
                <Text variant="bodySmall" style={[styles.recText, { color: recColor }]}>
                  AI Recommendation: <Text style={styles.recBold}>{item.recommendation.replace('_', ' ')}</Text>
                </Text>
              </View>
            </GlassCard>

            {/* ── Risk Breakdown ─────────────────────────────────────── */}
            <SectionHeader icon="format-list-checks" title="Risk Breakdown" light />
            <RiskBreakdown factors={item.risk_factors ?? []} totalScore={item.risk_score} />

            {/* ── Evidence Summary ───────────────────────────────────── */}
            <SectionHeader icon="database-check-outline" title="Evidence Summary" light />
            <EvidenceSummary item={item} />

            {/* ── Carbon Report Detail ───────────────────────────────── */}
            {reportDetail && (
              <>
                <SectionHeader icon="file-document-outline" title="Farm & Report Detail" light />
                <GlassCard opacity={0.92}>
                  <InfoRow label="Farm" value={reportDetail.farm.farm_name} />
                  <InfoRow label="Village" value={reportDetail.farm.village} />
                  <InfoRow label="District" value={reportDetail.farm.district} />
                  <InfoRow
                    label="Area"
                    value={reportDetail.farm.area_hectares != null
                      ? `${reportDetail.farm.area_hectares.toFixed(2)} ha`
                      : '—'}
                  />
                  <InfoRow label="Crop Type" value={reportDetail.crop_cycle.crop_type} />
                  <InfoRow label="Season" value={reportDetail.crop_cycle.season} />
                  <InfoRow label="Baseline Method" value={reportDetail.crop_cycle.baseline_method} />
                  <InfoRow label="Reduction Practice" value={reportDetail.crop_cycle.reduction_practice} last />
                </GlassCard>

                {/* Evidence Files */}
                <SectionHeader icon="paperclip" title="Evidence Files" light />
                {reportDetail.evidence_files.length === 0 ? (
                  <GlassCard opacity={0.88}>
                    <View style={styles.evidEmptyRow}>
                      <MaterialCommunityIcons name="folder-open-outline" size={20} color="#aaa" />
                      <Text variant="bodySmall" style={styles.evidEmptyText}>
                        No evidence files linked to this report.
                      </Text>
                    </View>
                  </GlassCard>
                ) : (
                  <GlassCard opacity={0.92}>
                    {reportDetail.evidence_files.map((ev, i) => (
                      <View
                        key={ev.id}
                        style={[
                          styles.evFileRow,
                          i < reportDetail.evidence_files.length - 1 && styles.evFileBorder,
                        ]}
                      >
                        <MaterialCommunityIcons
                          name={
                            ev.file_type === 'IMAGE' ? 'image-outline'
                            : ev.file_type === 'PDF' ? 'file-pdf-box'
                            : ev.file_type === 'VIDEO' ? 'video-outline'
                            : ev.file_type === 'CSV' ? 'file-delimited-outline'
                            : 'file-document-outline'
                          }
                          size={18}
                          color="#6a1b9a"
                        />
                        <View style={styles.evFileInfo}>
                          <Text variant="labelMedium" style={styles.evFileType}>
                            {ev.evidence_type ?? ev.file_type}
                          </Text>
                          {ev.description ? (
                            <Text variant="bodySmall" style={styles.evFileDesc}>{ev.description}</Text>
                          ) : null}
                          {ev.file_hash ? (
                            <Text variant="labelSmall" style={styles.evFileHash}>
                              Hash: {ev.file_hash.slice(0, 10)}…{ev.file_hash.slice(-6)}
                            </Text>
                          ) : (
                            <Text variant="labelSmall" style={styles.evFileNoHash}>No hash</Text>
                          )}
                        </View>
                        <Text variant="labelSmall" style={styles.evFileDate}>
                          {ev.created_at ? fmtDate(ev.created_at) : '—'}
                        </Text>
                      </View>
                    ))}
                  </GlassCard>
                )}
              </>
            )}

            {/* ── Carbon Calculation ─────────────────────────────────── */}
            <SectionHeader icon="calculator-variant-outline" title="Carbon Calculation" light />
            <CalcBreakdown item={item} />

            {/* ── Verifier Audit ─────────────────────────────────────── */}
            <SectionHeader icon="account-check-outline" title="Verifier Audit" light />
            <GlassCard opacity={0.92}>
              <InfoRow
                label="Verified By"
                value={item.verifier_name ?? (item.verifier_id ? `Verifier #${item.verifier_id}` : 'Not yet assigned')}
              />
              <InfoRow
                label="Verified At"
                value={item.verified_at ? fmtDate(item.verified_at, true) : 'Pending'}
              />
              <InfoRow
                label="Remarks"
                value={item.remarks ?? '—'}
                last
              />
            </GlassCard>

            {/* ── Decision Panel (PENDING only) ──────────────────────── */}
            {isPending && (
              <>
                <SectionHeader icon="pencil-outline" title="Your Decision" light />
                <GlassCard opacity={0.95}>
                  <Text variant="labelMedium" style={styles.remarksLabel}>
                    Remarks (required for rejection, optional for approval)
                  </Text>
                  <TextInput
                    mode="outlined"
                    multiline
                    numberOfLines={3}
                    placeholder="Enter remarks…"
                    value={remarks}
                    onChangeText={setRemarks}
                    style={styles.remarksInput}
                    outlineColor="#9e9e9e"
                    activeOutlineColor="#6a1b9a"
                  />
                  <View style={styles.actionRow}>
                    <AppButton
                      mode="contained"
                      onPress={handleApprove}
                      loading={submitting}
                      disabled={submitting}
                      style={styles.actionBtn}
                      buttonColor="#2e7d32"
                      icon="check-circle-outline"
                    >
                      Approve
                    </AppButton>
                    <AppButton
                      mode="outlined"
                      onPress={handleReject}
                      loading={submitting}
                      disabled={submitting}
                      style={styles.actionBtn}
                      textColor="#c62828"
                      icon="close-circle-outline"
                    >
                      Reject
                    </AppButton>
                  </View>
                </GlassCard>
              </>
            )}

            {!isPending && (
              <GlassCard style={styles.closedCard} opacity={0.85}>
                <MaterialCommunityIcons
                  name={item.status === 'APPROVED' ? 'check-circle' : 'close-circle'}
                  size={28}
                  color={item.status === 'APPROVED' ? '#2e7d32' : '#c62828'}
                />
                <Text variant="bodyMedium" style={styles.closedText}>
                  This verification has been {item.status.toLowerCase()}.
                  {item.status === 'APPROVED' && ' The FPO can now mint a carbon token.'}
                </Text>
              </GlassCard>
            )}

            <View style={styles.bottomPad} />
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  flex: { flex: 1 },
  scroll: { paddingTop: 8, paddingBottom: 32 },

  statusCard: { marginTop: 8 },
  statusRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  statusLabel: { color: '#888', marginBottom: 2 },
  reportRef: { fontWeight: '800', color: '#1b5e20' },
  submittedText: { color: '#aaa', marginTop: 2 },

  riskCard: { borderLeftWidth: 4 },
  riskTopRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  riskBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 12,
  },
  riskLevel: { fontSize: 16, fontWeight: '800' },
  scoreWrap: { alignItems: 'flex-end' },
  riskScore: { fontWeight: '900', lineHeight: 48 },
  riskScoreLabel: { color: '#888' },
  recRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  recText: { fontWeight: '500' },
  recBold: { fontWeight: '800' },

  // Risk Breakdown
  breakdownCard: {},
  breakdownZero: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  breakdownZeroText: { color: '#2e7d32', flex: 1 },
  factorRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingVertical: 8,
  },
  factorBorder: { borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  factorLabel: { flex: 1, color: '#444' },
  factorPoints: {
    backgroundColor: '#fff3e0', borderRadius: 6,
    paddingHorizontal: 6, paddingVertical: 2,
  },
  factorPointsText: { color: '#e65100', fontWeight: '700' },
  factorTotal: {
    borderTopWidth: 2, borderTopColor: '#e0e0e0',
    marginTop: 4, paddingTop: 10, justifyContent: 'space-between',
  },
  factorTotalLabel: { color: '#555', fontWeight: '700' },
  factorTotalValue: { fontWeight: '900', fontSize: 15 },

  // Evidence Summary
  evidRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingVertical: 8,
  },
  evidBorder: { borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  evidLabel: { flex: 1, color: '#444' },
  evidValue: { fontWeight: '700' },

  // Calculation
  calcRow: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
    paddingVertical: 8,
  },
  calcBorder: { borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  calcLeft: {
    width: 22, height: 22, borderRadius: 11,
    backgroundColor: '#e8f5e9', justifyContent: 'center', alignItems: 'center',
  },
  calcStep: { color: '#2e7d32', fontWeight: '800', fontSize: 11 },
  calcMiddle: { flex: 1 },
  calcLabel: { color: '#333', fontWeight: '700' },
  calcFormula: { color: '#aaa', marginTop: 2, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  calcValue: { color: '#1565c0', fontWeight: '600', textAlign: 'right', maxWidth: 140 },

  remarksLabel: { color: '#555', marginBottom: 6 },
  remarksInput: { marginBottom: 12, backgroundColor: '#fff' },
  actionRow: { flexDirection: 'row', gap: 12 },
  actionBtn: { flex: 1 },

  closedCard: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  closedText: { color: '#555', flex: 1, lineHeight: 20 },

  bottomPad: { height: 16 },

  // Evidence file list
  evidEmptyRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  evidEmptyText: { color: '#aaa', flex: 1 },
  evFileRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 8 },
  evFileBorder: { borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  evFileInfo: { flex: 1 },
  evFileType: { color: '#333', fontWeight: '700' },
  evFileDesc: { color: '#666', marginTop: 2 },
  evFileHash: { color: '#2e7d32', fontSize: 10, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', marginTop: 2 },
  evFileNoHash: { color: '#f57f17', fontSize: 10, marginTop: 2 },
  evFileDate: { color: '#aaa', fontSize: 10, marginTop: 2 },
});
