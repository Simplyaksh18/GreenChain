/**
 * CreditDetailScreen — Phase 10 (Item 4 + 5)
 *
 * Full detail view for a single farmer credit balance record.
 * Tapped from CreditBalanceScreen timeline cards.
 *
 * Fetches:
 *   GET /credits/my-balance  (balance already in route.params)
 *   GET /reports/{id}        — carbon report detail (methane / co2e / credits)
 *   GET /tokens/{id}         — token detail (tx hash, standard, minted_at)
 *
 * Sections:
 *   1. Credit Overview      — status, earned/available/paid, report/token IDs
 *   2. Carbon Calculation   — 5-step calculation with actual values
 *   3. Blockchain Token     — standard, tx hash, minted at
 *   4. Distribution History — distributions from payout API (if any)
 */
import React, { useCallback, useEffect, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getReportApi } from '../../api/carbonApi';
import { getTokenApi } from '../../api/tokenApi';
import { getMyPayouts } from '../../api/custodialApi';
import { ErrorView } from '../../components/ErrorView';
import { GlassCard } from '../../components/GlassCard';
import { LoadingView } from '../../components/LoadingView';
import { RoleBackground } from '../../components/RoleBackground';
import type { CarbonReport, CarbonToken, Payout } from '../../types';
import type { FarmerCreditsStackParamList } from '../../navigation/FarmerCreditsStack';

type Props = NativeStackScreenProps<FarmerCreditsStackParamList, 'CreditDetail'>;

const STATUS_COLOR: Record<string, string> = {
  EARNED:      '#1565c0',
  TOKENIZED:   '#2e7d32',
  DISTRIBUTED: '#6a1b9a',
  HELD:        '#e65100',
  CANCELLED:   '#757575',
};

const STATUS_LABEL: Record<string, string> = {
  EARNED:      'Awaiting Payout',
  TOKENIZED:   'On Blockchain',
  DISTRIBUTED: 'Paid Out',
  HELD:        'On Hold',
  CANCELLED:   'Cancelled',
};

function InfoRow({ label, value, mono }: { label: string; value: string | null | undefined; mono?: boolean }) {
  if (!value) return null;
  return (
    <View style={s.infoRow}>
      <Text variant="labelSmall" style={s.infoLabel}>{label}</Text>
      <Text variant="bodySmall" style={[s.infoValue, mono && s.infoMono]} numberOfLines={2}>
        {value}
      </Text>
    </View>
  );
}

function SectionHeader({ icon, title, color = '#333' }: {
  icon: keyof typeof MaterialCommunityIcons.glyphMap;
  title: string;
  color?: string;
}) {
  return (
    <View style={s.sectionHeader}>
      <MaterialCommunityIcons name={icon} size={18} color={color} />
      <Text variant="titleSmall" style={[s.sectionTitle, { color }]}>{title}</Text>
    </View>
  );
}

// ── Carbon Calculation Explanation ────────────────────────────────────────────

function CalcStep({
  step, label, value, unit, note, isResult,
}: {
  step: number;
  label: string;
  value: string;
  unit: string;
  note?: string;
  isResult?: boolean;
}) {
  return (
    <View style={[s.calcStep, isResult && s.calcStepResult]}>
      <View style={[s.calcStepNum, isResult && s.calcStepNumResult]}>
        <Text variant="labelSmall" style={[s.calcStepNumText, isResult && { color: '#fff' }]}>
          {step}
        </Text>
      </View>
      <View style={s.calcStepBody}>
        <Text variant="labelSmall" style={[s.calcStepLabel, isResult && { color: '#1b5e20', fontWeight: '700' }]}>
          {label}
        </Text>
        <View style={s.calcStepValueRow}>
          <Text variant="labelLarge" style={[s.calcStepValue, isResult && { color: '#2e7d32', fontSize: 18 }]}>
            {value}
          </Text>
          <Text variant="labelSmall" style={s.calcStepUnit}> {unit}</Text>
        </View>
        {note && (
          <Text variant="labelSmall" style={s.calcStepNote}>{note}</Text>
        )}
      </View>
    </View>
  );
}

function CarbonCalcSection({ report }: { report: CarbonReport }) {
  const baseline  = report.baseline_methane_kg;
  const current   = report.current_methane_kg;
  const reduction = report.methane_reduction_kg;
  const co2e      = report.co2e_reduction_tonnes;
  const credits   = report.estimated_credits;

  return (
    <GlassCard style={s.card} opacity={0.9}>
      <SectionHeader icon="calculator-variant-outline" title="Carbon Calculation" color="#1565c0" />

      <View style={s.calcFormula}>
        <Text variant="labelSmall" style={s.calcFormulaText}>
          (Baseline − Current Methane) × 27.2 ÷ 1000 = CO₂e  →  floor(CO₂e) = Credits
        </Text>
      </View>

      <CalcStep
        step={1}
        label="Baseline Methane Emission"
        value={baseline.toFixed(3)}
        unit="kg CH₄/day"
        note="Average of first 7 sensor readings of the crop cycle"
      />
      <View style={s.calcArrow}>
        <MaterialCommunityIcons name="minus" size={14} color="#bbb" />
      </View>
      <CalcStep
        step={2}
        label="Current Methane Emission"
        value={current.toFixed(3)}
        unit="kg CH₄/day"
        note="Average of last 7 sensor readings of the crop cycle"
      />
      <View style={s.calcArrow}>
        <MaterialCommunityIcons name="equal" size={14} color="#bbb" />
      </View>
      <CalcStep
        step={3}
        label="Methane Reduction"
        value={reduction.toFixed(3)}
        unit="kg CH₄/day"
        note="Baseline minus current — the verified daily reduction"
      />
      <View style={s.calcArrow}>
        <MaterialCommunityIcons name="close" size={12} color="#bbb" />
        <Text variant="labelSmall" style={s.calcMultiplierText}>× 27.2 ÷ 1000</Text>
      </View>
      <CalcStep
        step={4}
        label="CO₂e Reduction"
        value={co2e.toFixed(4)}
        unit="tCO₂e"
        note="Methane × GWP factor (27.2) ÷ 1000 to convert to tonnes CO₂-equivalent"
      />
      <View style={s.calcArrow}>
        <MaterialCommunityIcons name="arrow-down" size={14} color="#bbb" />
        <Text variant="labelSmall" style={s.calcMultiplierText}>floor(CO₂e)</Text>
      </View>
      <CalcStep
        step={5}
        label="Carbon Credits Issued"
        value={String(credits)}
        unit="credits"
        note="Whole credits only — fractional tCO₂e is not tradable"
        isResult
      />

      {credits === 0 && (
        <View style={s.zeroCertNote}>
          <MaterialCommunityIcons name="certificate-outline" size={14} color="#6a1b9a" />
          <Text variant="labelSmall" style={s.zeroCertText}>
            CO₂e reduction ({co2e.toFixed(4)} tCO₂e) is below the 1 tCO₂e threshold.
            A verification certificate was issued as proof of reduction, but no tradable
            carbon credits were generated.
          </Text>
        </View>
      )}
    </GlassCard>
  );
}

// ── Main Screen ───────────────────────────────────────────────────────────────

export function CreditDetailScreen({ route }: Props) {
  const { balance } = route.params;

  const [report, setReport]   = useState<CarbonReport | null>(null);
  const [token, setToken]     = useState<CarbonToken | null>(null);
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  const isZeroCert    = balance.credits_earned === 0;
  const statusColor   = STATUS_COLOR[balance.status] ?? '#555';
  const statusLabel   = STATUS_LABEL[balance.status] ?? balance.status;

  const fetchAll = useCallback(async () => {
    try {
      setError('');
      const [r, p] = await Promise.all([
        getReportApi(balance.carbon_report_id),
        getMyPayouts({ limit: 50 }),
      ]);
      setReport(r);
      setPayouts(p.filter((pay) => {
        // Filter payouts related to this balance — we don't have balance_id on Payout
        // so just show all FPO payouts to the farmer for now (they can't see others' payouts
        // since this endpoint returns only the current farmer's payouts)
        return true;
      }));

      if (balance.carbon_token_id) {
        try {
          const t = await getTokenApi(balance.carbon_token_id);
          setToken(t);
        } catch {
          // Token fetch failing is non-fatal (admin may not have minted yet)
        }
      }
    } catch {
      setError('Failed to load credit details.');
    } finally {
      setLoading(false);
    }
  }, [balance.carbon_report_id, balance.carbon_token_id]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  if (loading) return <LoadingView message="Loading credit details…" />;
  if (error)   return <ErrorView message={error} onRetry={fetchAll} />;

  const relevantPayouts = payouts.filter((p) => p.credit_balance_id === balance.id);

  return (
    <RoleBackground>
      <SafeAreaView style={s.safe} edges={['bottom']}>
        <ScrollView contentContainerStyle={s.scroll}>

          {/* ── Credit Overview ──────────────────────────────────────── */}
          <GlassCard style={s.card} opacity={0.9}>
            <SectionHeader icon="leaf-circle-outline" title="Credit Overview" color={statusColor} />

            {/* Status badge */}
            <View style={[s.statusBadge, { backgroundColor: statusColor + '18' }]}>
              <Text variant="labelMedium" style={[s.statusBadgeText, { color: statusColor }]}>
                {statusLabel}
              </Text>
            </View>

            {isZeroCert ? (
              <View style={s.certBanner}>
                <MaterialCommunityIcons name="certificate-outline" size={16} color="#6a1b9a" />
                <Text variant="bodySmall" style={s.certBannerText}>
                  Verification Certificate only — CO₂e reduction is below the 1 tCO₂e threshold
                  required to generate tradable carbon credits.
                </Text>
              </View>
            ) : (
              <View style={s.creditsTrio}>
                <CreditTrioItem label="EARNED"    value={balance.credits_earned}      color="#1b5e20" />
                <CreditTrioItem label="AVAILABLE" value={balance.credits_available}   color="#2e7d32" />
                <CreditTrioItem label="PAID OUT"  value={balance.credits_distributed} color="#6a1b9a" />
              </View>
            )}

            <InfoRow label="Report ID"   value={`#${balance.carbon_report_id}`} />
            {balance.carbon_token_id && (
              <InfoRow
                label={isZeroCert ? 'Certificate ID' : 'Token ID'}
                value={`#${balance.carbon_token_id}`}
              />
            )}
            <InfoRow label="Record Created" value={
              new Date(balance.created_at).toLocaleDateString('en-IN', {
                day: 'numeric', month: 'long', year: 'numeric',
              })
            } />
            {balance.updated_at && balance.updated_at !== balance.created_at && (
              <InfoRow label="Last Updated" value={
                new Date(balance.updated_at).toLocaleDateString('en-IN', {
                  day: 'numeric', month: 'long', year: 'numeric',
                })
              } />
            )}
          </GlassCard>

          {/* ── Carbon Calculation ───────────────────────────────────── */}
          {report && <CarbonCalcSection report={report} />}

          {/* ── Blockchain Token ─────────────────────────────────────── */}
          {token && (
            <GlassCard style={s.card} opacity={0.9}>
              <SectionHeader icon="link-lock" title="Blockchain Token" color="#0d47a1" />
              <InfoRow label="Token Standard" value={token.token_standard} />
              <InfoRow label="Credit Amount"  value={`${token.credit_amount} tCO₂e`} />
              <InfoRow label="Token Status"   value={token.status} />
              <InfoRow label="Minted At"      value={
                new Date(token.minted_at).toLocaleString('en-IN', {
                  day: 'numeric', month: 'short', year: 'numeric',
                  hour: '2-digit', minute: '2-digit',
                })
              } />
              {token.minted_tx_hash && (
                <InfoRow label="Tx Hash" value={token.minted_tx_hash} mono />
              )}
              <View style={s.chainNote}>
                <MaterialCommunityIcons name="information-outline" size={13} color="#1565c0" />
                <Text variant="labelSmall" style={s.chainNoteText}>
                  This token is held by your FPO's custodial wallet on your behalf. Your FPO
                  manages on-chain transfers and retirements when credits are sold.
                </Text>
              </View>
            </GlassCard>
          )}

          {/* ── Distribution History ──────────────────────────────────── */}
          {relevantPayouts.length > 0 && (
            <GlassCard style={s.card} opacity={0.9}>
              <SectionHeader icon="cash-check" title="Distribution History" color="#6a1b9a" />
              {relevantPayouts.map((p) => (
                <PayoutHistoryRow key={p.id} payout={p} />
              ))}
            </GlassCard>
          )}

        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

function CreditTrioItem({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <View style={s.trioItem}>
      <Text variant="headlineSmall" style={[s.trioValue, { color }]}>{Math.round(value)}</Text>
      <Text variant="labelSmall" style={s.trioLabel}>{label}</Text>
    </View>
  );
}

function PayoutHistoryRow({ payout }: { payout: Payout }) {
  const STATUS_C: Record<string, string> = {
    COMPLETED: '#2e7d32',
    INITIATED: '#e65100',
    PROCESSING: '#1565c0',
    FAILED: '#c62828',
    CANCELLED: '#757575',
  };
  const color = STATUS_C[payout.status] ?? '#555';
  return (
    <View style={s.payoutHistoryRow}>
      <View style={s.payoutHistoryLeft}>
        <Text variant="labelMedium" style={[s.payoutHistoryStatus, { color }]}>{payout.status}</Text>
        <Text variant="labelSmall" style={s.payoutHistoryDate}>
          {new Date(payout.initiated_at).toLocaleDateString('en-IN', {
            day: 'numeric', month: 'short', year: 'numeric',
          })}
        </Text>
      </View>
      <View style={s.payoutHistoryRight}>
        <Text variant="labelLarge" style={[s.payoutHistoryAmount, { color }]}>
          ₹{payout.payout_amount.toLocaleString('en-IN')}
        </Text>
        <Text variant="labelSmall" style={s.payoutHistoryCredits}>
          {payout.amount_credits} tCO₂e @ ₹{payout.price_per_credit}
        </Text>
      </View>
    </View>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { padding: 14, paddingBottom: 40 },
  card: { marginBottom: 10 },

  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  sectionTitle: { fontWeight: '800', flex: 1 },

  infoRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 6, alignItems: 'flex-start' },
  infoLabel: { color: '#888', flex: 1.2, marginRight: 8 },
  infoValue: { color: '#333', flex: 2, textAlign: 'right' },
  infoMono: { fontFamily: 'monospace', fontSize: 11, color: '#1565c0' },

  statusBadge: { alignSelf: 'flex-start', borderRadius: 20, paddingHorizontal: 12, paddingVertical: 5, marginBottom: 12 },
  statusBadgeText: { fontWeight: '700' },

  certBanner: {
    flexDirection: 'row', gap: 8, alignItems: 'flex-start',
    backgroundColor: '#f3e5f5', borderRadius: 10, padding: 10, marginBottom: 10,
  },
  certBannerText: { color: '#6a1b9a', flex: 1, lineHeight: 18 },

  creditsTrio: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 12, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  trioItem: { alignItems: 'center' },
  trioValue: { fontWeight: '900' },
  trioLabel: { color: '#999', marginTop: 2 },

  // Carbon calc
  calcFormula: { backgroundColor: 'rgba(21,101,192,0.07)', borderRadius: 8, padding: 8, marginBottom: 12 },
  calcFormulaText: { color: '#1565c0', lineHeight: 17, fontFamily: 'monospace', fontSize: 11 },

  calcStep: {
    flexDirection: 'row', gap: 10, marginBottom: 4,
    backgroundColor: 'rgba(0,0,0,0.03)', borderRadius: 10, padding: 10,
  },
  calcStepResult: {
    backgroundColor: '#e8f5e9', borderWidth: 1, borderColor: '#a5d6a7',
  },
  calcStepNum: {
    width: 22, height: 22, borderRadius: 11,
    backgroundColor: 'rgba(0,0,0,0.12)',
    justifyContent: 'center', alignItems: 'center',
  },
  calcStepNumResult: { backgroundColor: '#2e7d32' },
  calcStepNumText: { color: '#555', fontWeight: '700', fontSize: 11 },
  calcStepBody: { flex: 1 },
  calcStepLabel: { color: '#666', marginBottom: 2 },
  calcStepValueRow: { flexDirection: 'row', alignItems: 'baseline' },
  calcStepValue: { fontWeight: '800', color: '#333', fontSize: 15 },
  calcStepUnit: { color: '#888' },
  calcStepNote: { color: '#aaa', lineHeight: 14, marginTop: 3, fontSize: 10 },

  calcArrow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, marginVertical: 2 },
  calcMultiplierText: { color: '#bbb', fontSize: 11 },

  zeroCertNote: {
    flexDirection: 'row', gap: 7, alignItems: 'flex-start',
    backgroundColor: '#f3e5f5', borderRadius: 8, padding: 10, marginTop: 8,
  },
  zeroCertText: { color: '#6a1b9a', flex: 1, lineHeight: 17 },

  // Token
  chainNote: {
    flexDirection: 'row', gap: 6, alignItems: 'flex-start',
    backgroundColor: '#e3f2fd', borderRadius: 8, padding: 8, marginTop: 10,
  },
  chainNoteText: { color: '#1565c0', flex: 1, lineHeight: 16 },

  // Payout history
  payoutHistoryRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#f5f5f5',
  },
  payoutHistoryLeft: { gap: 2 },
  payoutHistoryRight: { alignItems: 'flex-end', gap: 2 },
  payoutHistoryStatus: { fontWeight: '700' },
  payoutHistoryDate: { color: '#aaa' },
  payoutHistoryAmount: { fontWeight: '800' },
  payoutHistoryCredits: { color: '#888' },
});
