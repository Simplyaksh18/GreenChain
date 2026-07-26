/**
 * CreditBalanceScreen — Phase 10 Redesign
 *
 * Portfolio Summary header + tappable timeline cards.
 * Each card navigates to CreditDetailScreen for full detail + calculation breakdown.
 *
 * GET /credits/my-balance
 */
import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { getMyCreditBalance } from '../../api/custodialApi';
import { getFarmsApi } from '../../api/farmApi';
import { getReportsByFarmApi } from '../../api/carbonApi';
import { ErrorView } from '../../components/ErrorView';
import { GlassCard } from '../../components/GlassCard';
import { LoadingView } from '../../components/LoadingView';
import { RoleBackground } from '../../components/RoleBackground';
import type { FarmerCreditBalance, FarmerCreditSummary } from '../../types';
import type { FarmerCreditsStackParamList } from '../../navigation/FarmerCreditsStack';

type Nav = NativeStackNavigationProp<FarmerCreditsStackParamList, 'CreditBalance'>;

const STATUS_COLOR: Record<string, string> = {
  EARNED:      '#1565c0',
  TOKENIZED:   '#2e7d32',
  DISTRIBUTED: '#6a1b9a',
  HELD:        '#e65100',
  CANCELLED:   '#757575',
};

const STATUS_ICON: Record<string, keyof typeof MaterialCommunityIcons.glyphMap> = {
  EARNED:      'leaf-circle-outline',
  TOKENIZED:   'link-lock',
  DISTRIBUTED: 'cash-check',
  HELD:        'pause-circle-outline',
  CANCELLED:   'close-circle-outline',
};

const STATUS_LABEL: Record<string, string> = {
  EARNED:      'Awaiting Payout',
  TOKENIZED:   'On Blockchain',
  DISTRIBUTED: 'Paid Out',
  HELD:        'On Hold',
  CANCELLED:   'Cancelled',
};

// ── Portfolio Summary ─────────────────────────────────────────────────────────

interface PortfolioSummaryProps {
  summary: FarmerCreditSummary;
  certCount: number;
  reportCount: number;
  onPayoutDetails: () => void;
}

function PortfolioSummary({ summary, certCount, reportCount, onPayoutDetails }: PortfolioSummaryProps) {
  const { total_earned, total_available, total_distributed, total_tokenized } = summary;
  const allZero = total_earned === 0 && certCount === reportCount && reportCount > 0;

  return (
    <GlassCard style={s.summaryCard} opacity={0.92}>
      {/* Title row */}
      <View style={s.summaryTitleRow}>
        <MaterialCommunityIcons name="leaf" size={18} color="#2e7d32" />
        <Text variant="titleSmall" style={s.summaryTitle}>My Carbon Portfolio</Text>
      </View>

      {allZero ? (
        <View style={s.zeroBanner}>
          <MaterialCommunityIcons name="information-outline" size={15} color="#6a1b9a" />
          <Text variant="bodySmall" style={s.zeroBannerText}>
            All verified reports are below the 1 tCO₂e threshold. Verification certificates
            were issued instead of tradable credits.
          </Text>
        </View>
      ) : (
        <>
          {/* Main trio */}
          <View style={s.trioRow}>
            <PortfolioStat label="EARNED" value={total_earned} color="#1b5e20" />
            <View style={s.trioDivider} />
            <PortfolioStat label="AVAILABLE" value={total_available} color="#2e7d32" />
            <View style={s.trioDivider} />
            <PortfolioStat label="PAID OUT" value={total_distributed} color="#6a1b9a" />
          </View>

          {/* Secondary row */}
          <View style={s.secondaryRow}>
            {total_tokenized > 0 && (
              <View style={s.secondaryChip}>
                <MaterialCommunityIcons name="link-lock" size={12} color="#0d47a1" />
                <Text variant="labelSmall" style={s.secondaryChipText}>
                  {total_tokenized} tokenized
                </Text>
              </View>
            )}
            <View style={s.secondaryChip}>
              <MaterialCommunityIcons name="file-document-outline" size={12} color="#555" />
              <Text variant="labelSmall" style={s.secondaryChipText}>
                {reportCount} report{reportCount !== 1 ? 's' : ''}
              </Text>
            </View>
            {certCount > 0 && (
              <View style={s.secondaryChip}>
                <MaterialCommunityIcons name="certificate-outline" size={12} color="#6a1b9a" />
                <Text variant="labelSmall" style={s.secondaryChipText}>
                  {certCount} cert{certCount !== 1 ? 's' : ''}
                </Text>
              </View>
            )}
          </View>
        </>
      )}

      {/* Custodial notice */}
      <View style={s.custodialNotice}>
        <MaterialCommunityIcons name="shield-lock-outline" size={13} color="#1565c0" />
        <Text variant="labelSmall" style={s.custodialText}>
          Credits held by your FPO on your behalf. Payouts go to your registered UPI/bank.
        </Text>
      </View>

      {/* Payout settings shortcut */}
      <TouchableOpacity style={s.payoutShortcut} onPress={onPayoutDetails} activeOpacity={0.75}>
        <MaterialCommunityIcons name="bank-outline" size={15} color="#1565c0" />
        <Text variant="labelSmall" style={s.payoutShortcutText}>Manage Payout Details</Text>
        <MaterialCommunityIcons name="chevron-right" size={15} color="#9e9e9e" />
      </TouchableOpacity>
    </GlassCard>
  );
}

function PortfolioStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <View style={s.portfolioStat}>
      <Text variant="headlineMedium" style={[s.portfolioStatValue, { color }]}>
        {Math.round(value)}
      </Text>
      <Text variant="labelSmall" style={s.portfolioStatLabel}>{label}</Text>
      <Text variant="labelSmall" style={s.portfolioStatUnit}>tCO₂e</Text>
    </View>
  );
}

// ── Timeline Card ─────────────────────────────────────────────────────────────

function TimelineCard({ balance, onPress }: { balance: FarmerCreditBalance; onPress: () => void }) {
  const isZeroCert = balance.credits_earned === 0;
  const color  = STATUS_COLOR[balance.status] ?? '#555';
  const icon   = STATUS_ICON[balance.status]  ?? 'circle-outline';
  const label  = STATUS_LABEL[balance.status] ?? balance.status;

  return (
    <TouchableOpacity activeOpacity={0.82} onPress={onPress}>
      <View style={s.timelineRow}>
        {/* Dot + line */}
        <View style={s.timelineSide}>
          <View style={[s.timelineDot, { backgroundColor: color }]}>
            <MaterialCommunityIcons name={icon} size={12} color="#fff" />
          </View>
          <View style={s.timelineLine} />
        </View>

        {/* Card body */}
        <View style={s.timelineBody}>
          <View style={s.timelineHeader}>
            <Text variant="labelMedium" style={[s.timelineStatus, { color }]}>{label}</Text>
            <Text variant="labelSmall" style={s.timelineDate}>
              {new Date(balance.created_at).toLocaleDateString('en-IN', {
                day: 'numeric', month: 'short', year: 'numeric',
              })}
            </Text>
          </View>

          {isZeroCert ? (
            <View style={s.certChip}>
              <MaterialCommunityIcons name="certificate-outline" size={12} color="#6a1b9a" />
              <Text variant="labelSmall" style={s.certChipText}>
                Verification Certificate — below 1 tCO₂e threshold
              </Text>
            </View>
          ) : (
            <View style={s.creditsRow}>
              <CreditPill label="EARNED"  value={balance.credits_earned}      color="#1b5e20" />
              <CreditPill label="AVAIL"   value={balance.credits_available}   color="#2e7d32" />
              <CreditPill label="PAID"    value={balance.credits_distributed} color="#6a1b9a" />
            </View>
          )}

          <View style={s.timelineFooter}>
            <Text variant="labelSmall" style={s.timelineRef}>Report #{balance.carbon_report_id}</Text>
            {balance.carbon_token_id && (
              <Text variant="labelSmall" style={s.timelineRef}>
                {isZeroCert ? `Cert` : `Token`} #{balance.carbon_token_id}
              </Text>
            )}
            <MaterialCommunityIcons name="chevron-right" size={14} color="#bbb" style={s.timelineChevron} />
          </View>
        </View>
      </View>
    </TouchableOpacity>
  );
}

function CreditPill({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <View style={s.pill}>
      <Text variant="labelLarge" style={[s.pillValue, { color }]}>{Math.round(value)}</Text>
      <Text variant="labelSmall" style={s.pillLabel}>{label}</Text>
    </View>
  );
}

// ── Payout Details Prompt Card ────────────────────────────────────────────────

function PayoutDetailsPromptCard({ onPress }: { onPress: () => void }) {
  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.85}>
      <GlassCard style={s.payoutCard} opacity={0.88}>
        <View style={s.payoutRow}>
          <View style={s.payoutIconWrap}>
            <MaterialCommunityIcons name="bank-outline" size={28} color="#1565c0" />
          </View>
          <View style={s.payoutTextWrap}>
            <Text variant="titleSmall" style={s.payoutTitle}>Manage Payout Details</Text>
            <Text variant="bodySmall" style={s.payoutSub}>
              Add UPI or bank account so your FPO can send carbon credit payouts directly to you.
            </Text>
          </View>
          <MaterialCommunityIcons name="chevron-right" size={20} color="#9e9e9e" />
        </View>
      </GlassCard>
    </TouchableOpacity>
  );
}

// ── Empty States ──────────────────────────────────────────────────────────────

type EmptyCase = 'no-reports' | 'not-verified' | 'verified-zero' | 'awaiting-mint' | null;

const EMPTY_STATES: Record<NonNullable<EmptyCase>, {
  icon: keyof typeof MaterialCommunityIcons.glyphMap;
  title: string;
  msg: string;
}> = {
  'no-reports': {
    icon: 'file-document-outline',
    title: 'No Carbon Reports Yet',
    msg: 'No carbon reports have been generated yet. Complete a crop cycle and request a report.',
  },
  'not-verified': {
    icon: 'timer-sand',
    title: 'Awaiting Verification',
    msg: 'Your reports are awaiting verification. Credits will appear here once a verifier approves them.',
  },
  'verified-zero': {
    icon: 'scale-balance',
    title: 'Below Credit Threshold',
    msg: 'Your reports are verified. Verification certificates were issued, but the measured CO₂e reduction is below the 1 tCO₂e threshold required to issue tradable carbon credits.',
  },
  'awaiting-mint': {
    icon: 'timer-sand-complete',
    title: 'Awaiting Tokenization',
    msg: 'Your reports are verified. Waiting for your FPO to mint carbon credits. Contact your FPO if this takes too long.',
  },
};

// ── Main Screen ───────────────────────────────────────────────────────────────

export function CreditBalanceScreen() {
  const navigation = useNavigation<Nav>();
  const [summary, setSummary]       = useState<FarmerCreditSummary | null>(null);
  const [emptyCase, setEmptyCase]   = useState<EmptyCase>(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const data = await getMyCreditBalance();
      setSummary(data);

      if (data.balances.length === 0) {
        try {
          const farms = await getFarmsApi({ limit: 5 });
          if (farms.length === 0) {
            setEmptyCase('no-reports');
          } else {
            const reports = await getReportsByFarmApi(farms[0].id, { limit: 20 });
            if (reports.length === 0) {
              setEmptyCase('no-reports');
            } else {
              const verified    = reports.filter((r) => r.status === 'VERIFIED');
              const zeroCredits = verified.filter((r) => r.estimated_credits === 0);
              if (verified.length === 0) {
                setEmptyCase('not-verified');
              } else if (verified.length > 0 && zeroCredits.length === verified.length) {
                setEmptyCase('verified-zero');
              } else {
                setEmptyCase('awaiting-mint');
              }
            }
          }
        } catch {
          setEmptyCase('no-reports');
        }
      } else {
        setEmptyCase(null);
      }
    } catch {
      setError('Failed to load carbon credit balance.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);
  const onRefresh = () => { setRefreshing(true); fetchData(); };

  if (loading) return <LoadingView message="Loading credit balance…" />;
  if (error)   return <ErrorView message={error} onRetry={fetchData} />;

  const balances  = summary?.balances ?? [];
  const certCount = balances.filter((b) => b.credits_earned === 0).length;

  const navigateToPayoutDetails = () => navigation.navigate('PayoutDetails');

  // ── Empty (no balances) ───────────────────────────────────────────────────

  if (balances.length === 0) {
    const state = emptyCase ? EMPTY_STATES[emptyCase] : EMPTY_STATES['no-reports'];
    return (
      <RoleBackground>
        <SafeAreaView style={s.safe} edges={['bottom']}>
          <View style={s.emptyCenter}>
            <GlassCard style={s.emptyCard} opacity={0.88}>
              <View style={s.emptyInner}>
                <MaterialCommunityIcons name={state.icon} size={48} color="#9e9e9e" />
                <Text variant="titleMedium" style={s.emptyTitle}>{state.title}</Text>
                <Text variant="bodyMedium" style={s.emptyMsg}>{state.msg}</Text>
              </View>
            </GlassCard>
            <PayoutDetailsPromptCard onPress={navigateToPayoutDetails} />
          </View>
        </SafeAreaView>
      </RoleBackground>
    );
  }

  // ── Has balances ──────────────────────────────────────────────────────────

  return (
    <RoleBackground>
      <SafeAreaView style={s.safe} edges={['bottom']}>
        <FlatList
          data={balances}
          keyExtractor={(b) => String(b.id)}
          renderItem={({ item }) => (
            <TimelineCard
              balance={item}
              onPress={() => navigation.navigate('CreditDetail', { balance: item })}
            />
          )}
          contentContainerStyle={s.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#fff"
              colors={['#66bb6a']}
            />
          }
          ListHeaderComponent={
            <PortfolioSummary
              summary={summary!}
              certCount={certCount}
              reportCount={balances.length}
              onPayoutDetails={navigateToPayoutDetails}
            />
          }
          ListFooterComponent={<View style={s.timelineEnd} />}
        />
      </SafeAreaView>
    </RoleBackground>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  safe: { flex: 1 },
  list: { padding: 12, paddingBottom: 32 },

  emptyCenter: { flex: 1, justifyContent: 'center', padding: 24, gap: 12 },
  emptyCard: {},
  emptyInner: { alignItems: 'center', gap: 12, paddingVertical: 12 },
  emptyTitle: { fontWeight: '800', color: '#555' },
  emptyMsg: { textAlign: 'center', color: '#777', lineHeight: 22 },

  // Portfolio Summary
  summaryCard: { marginBottom: 14 },
  summaryTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  summaryTitle: { fontWeight: '800', color: '#1b5e20', fontSize: 15 },

  trioRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around',
    marginBottom: 10,
  },
  trioDivider: { width: 1, height: 50, backgroundColor: 'rgba(0,0,0,0.08)' },
  portfolioStat: { alignItems: 'center', flex: 1 },
  portfolioStatValue: { fontWeight: '900' },
  portfolioStatLabel: { color: '#777', marginTop: 1 },
  portfolioStatUnit: { color: '#aaa', fontSize: 10 },

  secondaryRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap', marginBottom: 10 },
  secondaryChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(0,0,0,0.05)', borderRadius: 12,
    paddingHorizontal: 8, paddingVertical: 4,
  },
  secondaryChipText: { color: '#555' },

  zeroBanner: {
    flexDirection: 'row', gap: 8, alignItems: 'flex-start',
    backgroundColor: '#f3e5f5', borderRadius: 10, padding: 10, marginBottom: 8,
  },
  zeroBannerText: { color: '#6a1b9a', flex: 1, lineHeight: 18 },

  custodialNotice: {
    flexDirection: 'row', gap: 6, alignItems: 'flex-start',
    backgroundColor: '#e3f2fd', borderRadius: 8, padding: 8,
    marginBottom: 10,
  },
  custodialText: { color: '#1565c0', flex: 1, lineHeight: 16 },

  payoutShortcut: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: 'rgba(21,101,192,0.06)', borderRadius: 10,
    paddingHorizontal: 10, paddingVertical: 8,
  },
  payoutShortcutText: { color: '#1565c0', flex: 1, fontWeight: '600' },

  // Timeline cards
  timelineRow: { flexDirection: 'row', marginBottom: 4 },
  timelineSide: { width: 28, alignItems: 'center' },
  timelineDot: {
    width: 24, height: 24, borderRadius: 12,
    justifyContent: 'center', alignItems: 'center',
    marginTop: 2,
  },
  timelineLine: { flex: 1, width: 2, backgroundColor: 'rgba(0,0,0,0.08)', marginTop: 4 },
  timelineEnd: { height: 24 },

  timelineBody: {
    flex: 1, marginLeft: 10,
    backgroundColor: 'rgba(255,255,255,0.88)',
    borderRadius: 14, padding: 12, marginBottom: 10,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.4)',
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.07, shadowRadius: 4, elevation: 2,
  },
  timelineHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8, alignItems: 'center' },
  timelineStatus: { fontWeight: '700', fontSize: 12 },
  timelineDate: { color: '#aaa' },

  creditsRow: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  pill: {
    flex: 1, alignItems: 'center', paddingVertical: 6,
    backgroundColor: 'rgba(0,0,0,0.04)', borderRadius: 10,
  },
  pillValue: { fontWeight: '900' },
  pillLabel: { color: '#999', marginTop: 1, fontSize: 9 },

  certChip: {
    flexDirection: 'row', gap: 5, alignItems: 'center',
    backgroundColor: '#f3e5f5', borderRadius: 8, padding: 7, marginBottom: 8,
  },
  certChipText: { color: '#6a1b9a', flex: 1 },

  timelineFooter: { flexDirection: 'row', gap: 10, alignItems: 'center', borderTopWidth: 1, borderTopColor: '#f0f0f0', paddingTop: 6 },
  timelineRef: { color: '#888' },
  timelineChevron: { marginLeft: 'auto' },

  // Payout prompt card
  payoutCard: { marginBottom: 10, marginTop: 4 },
  payoutRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  payoutIconWrap: {
    width: 48, height: 48, borderRadius: 24,
    backgroundColor: '#e3f2fd', justifyContent: 'center', alignItems: 'center',
  },
  payoutTextWrap: { flex: 1 },
  payoutTitle: { fontWeight: '700', color: '#1565c0', marginBottom: 2 },
  payoutSub: { color: '#555', lineHeight: 17 },
});
