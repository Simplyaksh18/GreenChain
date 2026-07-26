/**
 * FarmerCreditBalancesScreen — Phase 9C
 *
 * FPO sees all farmer credit balances under their organisation.
 * Shows farmer name, farm name, credits earned/available/distributed, and
 * allows initiating payouts for balances with credits_available > 0.
 *
 * GET /fpo/credits/farmers  (enriched — includes farmer_name, farm_name, payout method)
 */
import React, { useCallback, useState } from 'react';
import { Alert, FlatList, RefreshControl, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { FPOCreditsStackParamList } from '../../navigation/FPOCreditsStack';

import { getFPOFarmerBalances } from '../../api/custodialApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { AppButton } from '../../components/AppButton';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { EmptyState } from '../../components/EmptyState';
import type { EnrichedFarmerCreditBalance } from '../../types';

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

function PayoutMethodBadge({ method, upi }: { method: string | null; upi: string | null }) {
  if (!method) {
    return (
      <View style={styles.payoutMethodBadge}>
        <MaterialCommunityIcons name="help-circle-outline" size={12} color="#9e9e9e" />
        <Text variant="labelSmall" style={styles.payoutMethodNone}>No payout details</Text>
      </View>
    );
  }
  return (
    <View style={styles.payoutMethodBadge}>
      <MaterialCommunityIcons
        name={method === 'UPI' ? 'cellphone' : 'bank-outline'}
        size={12}
        color="#1565c0"
      />
      <Text variant="labelSmall" style={styles.payoutMethodText}>
        {method === 'UPI' ? `UPI${upi ? `: ${upi}` : ''}` : 'Bank Transfer'}
      </Text>
    </View>
  );
}

function BalanceCard({ balance, onPayout, onTap }: {
  balance: EnrichedFarmerCreditBalance;
  onPayout: (balance: EnrichedFarmerCreditBalance) => void;
  onTap: (balance: EnrichedFarmerCreditBalance) => void;
}) {
  const color = STATUS_COLOR[balance.status] ?? '#555';
  const icon  = STATUS_ICON[balance.status] ?? 'circle-outline';
  const farmerLabel = balance.farmer_name ?? `Farmer #${balance.farmer_id}`;
  const canPayout = balance.credits_available > 0;
  const isZeroCert = balance.credits_earned === 0;

  return (
    <TouchableOpacity onPress={() => onTap(balance)} activeOpacity={0.85}>
    <GlassCard style={styles.card} opacity={0.92}>
      {/* Header */}
      <View style={styles.cardHeader}>
        <View style={styles.headerLeft}>
          <MaterialCommunityIcons name={icon} size={18} color={color} />
          <Text variant="labelMedium" style={[styles.statusLabel, { color }]}>{balance.status}</Text>
        </View>
        <Text variant="labelSmall" style={styles.dateText}>
          {new Date(balance.created_at).toLocaleDateString('en-IN', {
            day: 'numeric', month: 'short', year: 'numeric',
          })}
        </Text>
      </View>

      {/* Farmer / Farm */}
      <Text variant="labelLarge" style={styles.farmerName}>{farmerLabel}</Text>
      {balance.farmer_email && (
        <Text variant="labelSmall" style={styles.farmerEmail}>{balance.farmer_email}</Text>
      )}
      {balance.farm_name && (
        <Text variant="bodySmall" style={styles.farmName}>
          <MaterialCommunityIcons name="sprout-outline" size={12} color="#4caf50" /> {balance.farm_name}
        </Text>
      )}

      {/* References */}
      <View style={styles.refs}>
        <Text variant="labelSmall" style={styles.ref}>Report #{balance.carbon_report_id}</Text>
        {balance.carbon_token_id && (
          <Text variant="labelSmall" style={styles.ref}>Token #{balance.carbon_token_id}</Text>
        )}
      </View>

      {/* Zero-credit certificate note */}
      {isZeroCert && (
        <View style={styles.certNote}>
          <MaterialCommunityIcons name="certificate-outline" size={14} color="#6a1b9a" />
          <Text variant="labelSmall" style={styles.certNoteText}>
            Verification certificate only — CO₂e below 1 tCO₂e threshold. No tradable credits.
          </Text>
        </View>
      )}

      {/* Credits row */}
      {!isZeroCert && (
        <View style={styles.creditsRow}>
          <View style={styles.creditStat}>
            <Text variant="titleMedium" style={styles.creditVal}>{balance.credits_earned}</Text>
            <Text variant="labelSmall" style={styles.creditStatLabel}>EARNED</Text>
          </View>
          <MaterialCommunityIcons name="arrow-right" size={14} color="#bbb" />
          <View style={styles.creditStat}>
            <Text variant="titleMedium" style={[styles.creditVal, { color: '#2e7d32' }]}>
              {balance.credits_available}
            </Text>
            <Text variant="labelSmall" style={styles.creditStatLabel}>AVAILABLE</Text>
          </View>
          <MaterialCommunityIcons name="arrow-right" size={14} color="#bbb" />
          <View style={styles.creditStat}>
            <Text variant="titleMedium" style={[styles.creditVal, { color: '#6a1b9a' }]}>
              {balance.credits_distributed}
            </Text>
            <Text variant="labelSmall" style={styles.creditStatLabel}>PAID OUT</Text>
          </View>
        </View>
      )}

      {/* Payout method */}
      <PayoutMethodBadge method={balance.farmer_payout_method} upi={balance.farmer_upi_id} />

      {/* Payout CTA */}
      {canPayout && !isZeroCert && (
        <AppButton
          mode="contained"
          onPress={() => onPayout(balance)}
          buttonColor="#1565c0"
          icon="cash-fast"
          style={styles.payoutBtn}
        >
          Initiate Payout ({balance.credits_available} credits)
        </AppButton>
      )}
      {!canPayout && !isZeroCert && (
        <View style={styles.distributedNote}>
          <MaterialCommunityIcons name="check-circle-outline" size={14} color="#6a1b9a" />
          <Text variant="labelSmall" style={styles.distributedText}>All credits distributed</Text>
        </View>
      )}
      <View style={styles.tapHint}>
        <Text variant="labelSmall" style={styles.tapHintText}>Tap for details →</Text>
      </View>
    </GlassCard>
    </TouchableOpacity>
  );
}

export function FarmerCreditBalancesScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<FPOCreditsStackParamList, 'FarmerCreditBalances'>>();
  const [balances, setBalances]     = useState<EnrichedFarmerCreditBalance[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const data = await getFPOFarmerBalances();
      setBalances(data);
    } catch {
      setError('Failed to load farmer credit balances.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { fetchData(); }, [fetchData]));
  const onRefresh = () => { setRefreshing(true); fetchData(); };

  const handleTapCard = (balance: EnrichedFarmerCreditBalance) => {
    navigation.navigate('CreditBalanceDetail', { balance });
  };

  const handlePayout = (balance: EnrichedFarmerCreditBalance) => {
    const farmerLabel = balance.farmer_name ?? `Farmer #${balance.farmer_id}`;
    const payoutMethod = balance.farmer_payout_method;

    if (!payoutMethod) {
      Alert.alert(
        'No Payout Details',
        `${farmerLabel} has not set up a payout method (UPI or Bank). Ask the farmer to add their payout details first.`,
      );
      return;
    }

    Alert.alert(
      'Initiate Payout',
      `Go to the Payouts screen to initiate a payout for ${farmerLabel}.\n\n` +
      `Available credits: ${balance.credits_available}\n` +
      `Payout method: ${payoutMethod === 'UPI' && balance.farmer_upi_id
        ? `UPI (${balance.farmer_upi_id})`
        : payoutMethod}`,
      [{ text: 'OK' }],
    );
  };

  if (loading) return <LoadingView message="Loading farmer balances…" />;
  if (error)   return <ErrorView message={error} onRetry={fetchData} />;

  const totalAvailable   = balances.reduce((s, b) => s + b.credits_available, 0);
  const totalDistributed = balances.reduce((s, b) => s + b.credits_distributed, 0);
  const totalEarned      = balances.reduce((s, b) => s + b.credits_earned, 0);
  const readyCount       = balances.filter((b) => b.credits_available > 0 && b.credits_earned > 0).length;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <SectionHeader
          icon="account-cash-outline"
          title={`Farmer Credits · ${readyCount} Ready`}
          light
        />
        <FlatList
          data={balances}
          keyExtractor={(b) => String(b.id)}
          renderItem={({ item }) => <BalanceCard balance={item} onPayout={handlePayout} onTap={handleTapCard} />}
          contentContainerStyle={balances.length === 0 ? styles.emptyContainer : styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#fff"
              colors={['#1976d2']}
            />
          }
          ListEmptyComponent={
            <EmptyState
              icon="account-cash-outline"
              title="No Credit Balances"
              message="Mint tokens for verified reports to create farmer credit balances."
            />
          }
          ListHeaderComponent={balances.length > 0 ? (
            <GlassCard style={styles.summaryCard} opacity={0.9}>
              <Text variant="titleSmall" style={styles.summaryTitle}>FPO Credit Summary</Text>
              <View style={styles.summaryRow}>
                <View style={styles.summaryItem}>
                  <Text variant="headlineSmall" style={styles.summaryValue}>{totalEarned}</Text>
                  <Text variant="labelSmall" style={styles.summaryLabel}>EARNED</Text>
                </View>
                <View style={styles.summaryDivider} />
                <View style={styles.summaryItem}>
                  <Text variant="headlineSmall" style={[styles.summaryValue, { color: '#2e7d32' }]}>
                    {totalAvailable}
                  </Text>
                  <Text variant="labelSmall" style={styles.summaryLabel}>AVAILABLE</Text>
                </View>
                <View style={styles.summaryDivider} />
                <View style={styles.summaryItem}>
                  <Text variant="headlineSmall" style={[styles.summaryValue, { color: '#6a1b9a' }]}>
                    {totalDistributed}
                  </Text>
                  <Text variant="labelSmall" style={styles.summaryLabel}>PAID OUT</Text>
                </View>
              </View>
              <Text variant="labelSmall" style={styles.balanceCount}>
                {balances.length} balance record{balances.length !== 1 ? 's' : ''}
              </Text>
            </GlassCard>
          ) : null}
        />
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  list: { padding: 12, paddingBottom: 32 },
  emptyContainer: { flex: 1, justifyContent: 'center' },

  summaryCard: { marginBottom: 10 },
  summaryTitle: { fontWeight: '700', color: '#333', textAlign: 'center', marginBottom: 8 },
  summaryRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around' },
  summaryItem: { alignItems: 'center', flex: 1 },
  summaryDivider: { width: 1, height: 44, backgroundColor: 'rgba(0,0,0,0.1)' },
  summaryValue: { fontWeight: '800', color: '#1b5e20' },
  summaryLabel: { color: '#777', marginTop: 2 },
  balanceCount: { color: '#aaa', textAlign: 'center', marginTop: 8 },

  card: { marginBottom: 8 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusLabel: { fontWeight: '700', fontSize: 11 },
  dateText: { color: '#aaa' },

  farmerName: { fontWeight: '800', color: '#1b5e20', marginBottom: 2 },
  farmerEmail: { color: '#777', marginBottom: 2 },
  farmName: { color: '#555', marginBottom: 6 },

  refs: { flexDirection: 'row', gap: 12, marginBottom: 6 },
  ref: { color: '#888' },

  certNote: {
    flexDirection: 'row', gap: 6, alignItems: 'flex-start',
    backgroundColor: '#f3e5f5', borderRadius: 8, padding: 8, marginBottom: 8,
  },
  certNoteText: { flex: 1, color: '#6a1b9a', lineHeight: 16 },

  creditsRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around',
    marginBottom: 8, paddingVertical: 6,
    borderTopWidth: 1, borderTopColor: '#f0f0f0',
  },
  creditStat: { alignItems: 'center' },
  creditVal: { fontWeight: '800', color: '#333' },
  creditStatLabel: { color: '#999', marginTop: 1, fontSize: 10 },

  payoutMethodBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 8 },
  payoutMethodText: { color: '#1565c0' },
  payoutMethodNone: { color: '#9e9e9e' },

  payoutBtn: { marginTop: 2 },

  distributedNote: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2 },
  distributedText: { color: '#6a1b9a' },

  tapHint: { alignItems: 'flex-end', marginTop: 6 },
  tapHintText: { color: '#aaa', fontSize: 11 },
});
