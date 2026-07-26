/**
 * TokenWalletScreen — Phase 9B
 * GET /tokens/my-wallet  (no farm_id required)
 */
import React, { useEffect, useState, useCallback } from 'react';
import { FlatList, StyleSheet, View, RefreshControl } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { getMyWalletApi } from '../../api/tokenApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { StatusBadge } from '../../components/StatusBadge';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import type { CarbonToken } from '../../types';

function TokenCard({ token }: { token: CarbonToken }) {
  const tokenShort = token.token_id.length > 20
    ? `${token.token_id.slice(0, 10)}…${token.token_id.slice(-6)}`
    : token.token_id;
  const txShort = token.minted_tx_hash.length > 20
    ? `${token.minted_tx_hash.slice(0, 10)}…${token.minted_tx_hash.slice(-6)}`
    : token.minted_tx_hash;

  return (
    <View style={styles.tokenCard}>
      <View style={styles.tokenHeader}>
        <View style={styles.tokenLeft}>
          <MaterialCommunityIcons
            name={token.is_certificate ? 'certificate-outline' : 'currency-btc'}
            size={24}
            color="#2e7d32"
          />
          {token.is_certificate && (
            <View style={styles.certBadge}>
              <Text style={styles.certText}>CERTIFICATE</Text>
            </View>
          )}
        </View>
        <StatusBadge status={token.status} />
      </View>

      <Text variant="headlineMedium" style={styles.creditAmount}>
        {token.credit_amount.toFixed(2)}{' '}
        <Text variant="bodySmall" style={styles.creditUnit}>tCO₂</Text>
      </Text>

      <View style={styles.tokenDetails}>
        <View style={styles.detailRow}>
          <MaterialCommunityIcons name="identifier" size={14} color="#aaa" />
          <Text variant="labelSmall" style={styles.detailText}>{tokenShort}</Text>
        </View>
        <View style={styles.detailRow}>
          <MaterialCommunityIcons name="link-variant" size={14} color="#aaa" />
          <Text variant="labelSmall" style={styles.detailText}>{txShort}</Text>
        </View>
        <View style={styles.detailRow}>
          <MaterialCommunityIcons name="calendar-outline" size={14} color="#aaa" />
          <Text variant="labelSmall" style={styles.detailText}>
            Minted: {new Date(token.minted_at).toLocaleDateString('en-IN', {
              day: 'numeric', month: 'short', year: 'numeric',
            })}
          </Text>
        </View>
        <View style={styles.detailRow}>
          <MaterialCommunityIcons name="tag-outline" size={14} color="#aaa" />
          <Text variant="labelSmall" style={styles.detailText}>{token.token_standard}</Text>
        </View>
      </View>
    </View>
  );
}

export function TokenWalletScreen() {
  const [tokens, setTokens]         = useState<CarbonToken[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fetchTokens = useCallback(async () => {
    try {
      setError('');
      // value from GET /tokens/my-wallet
      const data = await getMyWalletApi({ limit: 50 });
      setTokens(data);
    } catch {
      setError('Failed to load token wallet.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchTokens(); }, [fetchTokens]);
  const onRefresh = () => { setRefreshing(true); fetchTokens(); };

  if (loading) return <LoadingView message="Loading your token wallet…" />;
  if (error)   return <ErrorView message={error} onRetry={fetchTokens} />;

  const totalCredits = tokens.reduce((sum, t) => sum + t.credit_amount, 0);
  const minted   = tokens.filter((t) => t.status === 'MINTED').length;
  const retired  = tokens.filter((t) => t.status === 'RETIRED').length;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        {tokens.length === 0 ? (
          <View style={styles.emptyCenter}>
            <GlassCard style={styles.emptyCard} opacity={0.88}>
              <View style={styles.emptyInner}>
                <MaterialCommunityIcons name="wallet-outline" size={48} color="#9e9e9e" />
                <Text variant="titleMedium" style={styles.emptyTitle}>Empty Wallet</Text>
                <Text variant="bodyMedium" style={styles.emptyMsg}>
                  No tokens minted yet. Verified carbon reports generate tokens.
                </Text>
              </View>
            </GlassCard>
          </View>
        ) : (
          <FlatList
            data={tokens}
            keyExtractor={(t) => String(t.id)}
            renderItem={({ item }) => <TokenCard token={item} />}
            contentContainerStyle={styles.list}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={onRefresh}
                tintColor="#fff"
                colors={['#66bb6a']}
              />
            }
            ListHeaderComponent={
              <GlassCard style={styles.summaryCard} opacity={0.88}>
                <View style={styles.summaryRow}>
                  <View style={styles.summaryItem}>
                    <Text variant="headlineMedium" style={styles.summaryValue}>
                      {totalCredits.toFixed(2)}
                    </Text>
                    <Text variant="labelSmall" style={styles.summaryLabel}>TOTAL tCO₂</Text>
                  </View>
                  <View style={styles.summaryDivider} />
                  <View style={styles.summaryItem}>
                    <Text variant="headlineMedium" style={styles.summaryValue}>{minted}</Text>
                    <Text variant="labelSmall" style={styles.summaryLabel}>MINTED</Text>
                  </View>
                  <View style={styles.summaryDivider} />
                  <View style={styles.summaryItem}>
                    <Text variant="headlineMedium" style={styles.summaryValue}>{retired}</Text>
                    <Text variant="labelSmall" style={styles.summaryLabel}>RETIRED</Text>
                  </View>
                </View>
              </GlassCard>
            }
          />
        )}
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  list: { padding: 12, paddingBottom: 32 },

  summaryCard: { marginBottom: 8 },
  summaryRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', paddingVertical: 6 },
  summaryItem: { alignItems: 'center', flex: 1 },
  summaryDivider: { width: 1, height: 44, backgroundColor: 'rgba(0,0,0,0.1)' },
  summaryValue: { fontWeight: '800', color: '#1b5e20' },
  summaryLabel: { color: '#777', marginTop: 2 },

  tokenCard: {
    backgroundColor: 'rgba(255,255,255,0.88)',
    borderRadius: 16,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.4)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 6,
    elevation: 2,
  },
  tokenHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  tokenLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  certBadge: { backgroundColor: '#fff3e0', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  certText: { fontSize: 10, color: '#e65100', fontWeight: '800' },
  creditAmount: { fontWeight: '900', color: '#2e7d32', marginBottom: 10 },
  creditUnit: { color: '#777', fontWeight: '400' },
  tokenDetails: { gap: 4, borderTopWidth: 1, borderTopColor: '#f0f0f0', paddingTop: 8 },
  detailRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  detailText: { color: '#888', flex: 1 },

  emptyCenter: { flex: 1, justifyContent: 'center', padding: 24 },
  emptyCard: {},
  emptyInner: { alignItems: 'center', gap: 12, paddingVertical: 12 },
  emptyTitle: { fontWeight: '800', color: '#555' },
  emptyMsg: { textAlign: 'center', color: '#777', lineHeight: 22 },
});
