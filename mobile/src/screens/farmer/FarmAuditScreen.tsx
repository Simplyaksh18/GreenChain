/**
 * FarmAuditScreen — Phase 13
 *
 * Full auditable JSON package for a farm.
 * Shows farm info, crop cycles, carbon reports with methane diagnostics,
 * SOC reports, evidence, payouts, and methodology.
 * Includes a "Copy Audit JSON" button.
 *
 * GET /audit/farms/{farmId}/full-report
 */
import React, { useCallback, useState } from 'react';
import {
  Alert,
  Clipboard,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { Text, Button, Divider } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getFarmAuditReport, type FarmAuditReport } from '../../api/auditApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { InfoRow } from '../../components/InfoRow';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'FarmAudit'>;

export function FarmAuditScreen({ route }: Props) {
  const { farmId, farmName } = route.params;

  const [audit, setAudit]         = useState<FarmAuditReport | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [expanded, setExpanded]   = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    try {
      setError('');
      const data = await getFarmAuditReport(farmId);
      setAudit(data);
    } catch {
      setError('Failed to load audit report.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [farmId]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const toggle = (key: string) =>
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

  const handleCopyJSON = async () => {
    if (!audit) return;
    Clipboard.setString(JSON.stringify(audit, null, 2));
    Alert.alert('Copied', 'Audit JSON copied to clipboard.');
  };

  const onRefresh = () => { setRefreshing(true); load(); };

  if (loading) return <LoadingView message="Building audit report…" />;
  if (error)   return <ErrorView message={error} onRetry={load} />;
  if (!audit)  return null;

  const { farm, crop_cycles, carbon_reports, soc_reports, evidence, payouts, methodology } = audit;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#fff" />
          }
        >
          <SectionHeader icon="shield-check-outline" title={`Audit — ${farmName}`} light />

          {/* Generated at */}
          <View style={styles.genRow}>
            <MaterialCommunityIcons name="clock-outline" size={14} color="#aaa" />
            <Text variant="bodySmall" style={styles.genText}>
              Generated: {new Date(audit.generated_at).toLocaleString('en-IN')}
            </Text>
          </View>

          {/* Farm Info */}
          <GlassCard opacity={0.92} style={styles.card}>
            <Text variant="titleSmall" style={styles.sectionTitle}>Farm</Text>
            <InfoRow label="Status" value={farm.farm_status} />
            <InfoRow label="Area" value={`${farm.land_area_acres} acres`} />
            <InfoRow label="Location" value={`${farm.village}, ${farm.district}, ${farm.state}`} />
            <InfoRow label="Soil" value={farm.soil_type} />
            <InfoRow label="Water" value={farm.water_source} />
            {farm.fpo_name && <InfoRow label="FPO" value={farm.fpo_name} />}
            {farm.boundary_area_hectares != null && (
              <InfoRow label="Boundary" value={`${farm.boundary_area_hectares.toFixed(2)} ha`} />
            )}
          </GlassCard>

          {/* Crop Cycles */}
          <GlassCard opacity={0.92} style={styles.card}>
            <Text variant="titleSmall" style={styles.sectionTitle}>
              Crop Cycles ({crop_cycles.length})
            </Text>
            {crop_cycles.map((c, i) => (
              <View key={c.id} style={i > 0 ? styles.cycleRow : undefined}>
                {i > 0 && <Divider style={styles.divider} />}
                <InfoRow label="Crop" value={`${c.crop_type} (${c.season})`} />
                <InfoRow label="Dates" value={`${c.start_date ?? '?'} → ${c.end_date ?? 'ongoing'}`} />
                <InfoRow label="Practice" value={c.reduction_practice} />
                <InfoRow label="Status" value={c.status} />
              </View>
            ))}
            {crop_cycles.length === 0 && (
              <Text style={styles.emptyText}>No crop cycles</Text>
            )}
          </GlassCard>

          {/* Carbon Reports */}
          {carbon_reports.map((pkg, idx) => (
            <GlassCard key={pkg.carbon_report.id} opacity={0.92} style={styles.card}>
              <Text
                variant="titleSmall"
                style={styles.sectionTitle}
                onPress={() => toggle(`report_${idx}`)}
              >
                Carbon Report #{pkg.carbon_report.id} — {pkg.carbon_report.status}
                {'  '}
                <MaterialCommunityIcons
                  name={expanded[`report_${idx}`] ? 'chevron-up' : 'chevron-down'}
                  size={16}
                />
              </Text>

              {expanded[`report_${idx}`] && (
                <>
                  <InfoRow label="Hash" value={pkg.carbon_report.report_hash ?? 'n/a'} />
                  <InfoRow label="Created" value={new Date(pkg.carbon_report.created_at).toLocaleDateString('en-IN')} />

                  <Text variant="labelSmall" style={styles.subTitle}>Methane Diagnostics</Text>
                  <InfoRow label="Baseline CH₄" value={`${pkg.methane_diagnostics.baseline_methane_kg} kg`} />
                  <InfoRow label="Current CH₄" value={`${pkg.methane_diagnostics.current_methane_kg} kg`} />
                  <InfoRow label="Reduction" value={`${pkg.methane_diagnostics.methane_reduction_kg} kg`} />
                  <InfoRow label="CO₂e" value={`${pkg.methane_diagnostics.co2e_reduction_tonnes} t`} />
                  <InfoRow label="GWP" value={`${pkg.methane_diagnostics.gwp_factor_used}`} />
                  <InfoRow label="Credits" value={`${pkg.methane_diagnostics.estimated_credits}`} />
                  <InfoRow label="Sensor readings" value={`${pkg.methane_diagnostics.input_sensor_count}`} />

                  {pkg.soc_report && (
                    <>
                      <Text variant="labelSmall" style={[styles.subTitle, { color: '#e65100' }]}>
                        SOC — Informational Only (not mintable)
                      </Text>
                      <InfoRow label="Baseline SOC" value={`${pkg.soc_report.baseline_soc?.toFixed(3)}%`} />
                      <InfoRow label="Current SOC" value={`${pkg.soc_report.current_soc?.toFixed(3)}%`} />
                      <InfoRow label="SOC CO₂e" value={`${pkg.soc_report.soc_co2e?.toFixed(2)} t`} />
                    </>
                  )}

                  <InfoRow
                    label="Verification"
                    value={pkg.verification_history.length > 0
                      ? pkg.verification_history.map((v) => v.status).join(' → ')
                      : 'None'}
                  />
                  <InfoRow
                    label="Blockchain txns"
                    value={`${pkg.blockchain_transactions.length}`}
                  />
                  <InfoRow label="Evidence files" value={`${pkg.evidence.length}`} />
                </>
              )}
            </GlassCard>
          ))}

          {/* SOC Reports */}
          {soc_reports.length > 0 && (
            <GlassCard opacity={0.88} style={styles.card}>
              <Text variant="titleSmall" style={styles.sectionTitle}>
                SOC Reports — Informational Only
              </Text>
              {soc_reports.map((sr) => (
                <View key={sr.id}>
                  <InfoRow label={`Cycle #${sr.crop_cycle_id}`}
                    value={`${sr.current_soc?.toFixed(3)}% SOC | ${sr.soc_credits} credits`} />
                </View>
              ))}
              <Text style={styles.infoNote}>
                ⚠ SOC credits are NOT mintable or payable in GreenChain.
              </Text>
            </GlassCard>
          )}

          {/* Evidence summary */}
          <GlassCard opacity={0.88} style={styles.card}>
            <Text variant="titleSmall" style={styles.sectionTitle}>
              Evidence ({evidence.length} files)
            </Text>
            {evidence.map((ev) => (
              <View key={ev.id} style={styles.evRow}>
                <MaterialCommunityIcons
                  name={ev.file_hash ? 'shield-check-outline' : 'shield-alert-outline'}
                  size={14}
                  color={ev.file_hash ? '#2e7d32' : '#f57f17'}
                />
                <Text variant="bodySmall" style={styles.evText}>
                  {ev.file_type}{ev.description ? ` — ${ev.description}` : ''}
                  {ev.file_hash ? '  ✓ hashed' : '  no hash'}
                </Text>
              </View>
            ))}
            {evidence.length === 0 && (
              <Text style={styles.emptyText}>No evidence uploaded</Text>
            )}
          </GlassCard>

          {/* Payouts */}
          {payouts.length > 0 && (
            <GlassCard opacity={0.88} style={styles.card}>
              <Text variant="titleSmall" style={styles.sectionTitle}>
                Payouts ({payouts.length})
              </Text>
              {payouts.map((p) => (
                <View key={p.id}>
                  <InfoRow
                    label={`₹${p.payout_amount.toLocaleString('en-IN')}`}
                    value={`${p.status} · ${p.amount_credits} tCO₂e`}
                  />
                </View>
              ))}
            </GlassCard>
          )}

          {/* Methodology */}
          <GlassCard opacity={0.85} style={styles.card}>
            <Text
              variant="titleSmall"
              style={styles.sectionTitle}
              onPress={() => toggle('methodology')}
            >
              Methodology
              <MaterialCommunityIcons
                name={expanded['methodology'] ? 'chevron-up' : 'chevron-down'}
                size={16}
              />
            </Text>
            {expanded['methodology'] && (
              <>
                <Text variant="labelSmall" style={styles.subTitle}>Methane</Text>
                <Text style={styles.methodText}>
                  {String(methodology.methane.formula ?? '')}
                </Text>
                <Text style={styles.methodText}>
                  GWP: {String(methodology.methane.gwp_factor ?? '')}
                </Text>
                <Text variant="labelSmall" style={[styles.subTitle, { marginTop: 8 }]}>SOC</Text>
                <Text style={styles.methodText}>
                  {String(methodology.soc.soc_gain_formula ?? '')}
                </Text>
                <Text style={[styles.methodText, { color: '#e65100', marginTop: 4 }]}>
                  {String(methodology.soc.credits_note ?? '')}
                </Text>
              </>
            )}
          </GlassCard>

          {/* Copy JSON */}
          <Button
            mode="outlined"
            onPress={handleCopyJSON}
            icon="content-copy"
            style={styles.copyBtn}
          >
            Copy Audit JSON
          </Button>

          <View style={{ height: 24 }} />
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe:        { flex: 1 },
  scroll:      { paddingBottom: 40 },
  card:        { marginBottom: 8 },
  sectionTitle:{ fontWeight: '700', color: '#333', marginBottom: 8 },
  subTitle:    { color: '#888', fontWeight: '600', marginTop: 10, marginBottom: 4, fontSize: 11, letterSpacing: 0.4 },
  divider:     { marginVertical: 6 },
  cycleRow:    {},
  emptyText:   { color: '#aaa', fontStyle: 'italic' },
  infoNote:    { color: '#e65100', fontSize: 11, marginTop: 6, fontStyle: 'italic' },
  genRow:      { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, marginBottom: 4 },
  genText:     { color: '#aaa' },
  evRow:       { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 },
  evText:      { flex: 1, color: '#555' },
  methodText:  { color: '#444', fontSize: 12, lineHeight: 18 },
  copyBtn:     { marginHorizontal: 16, marginTop: 8 },
});
