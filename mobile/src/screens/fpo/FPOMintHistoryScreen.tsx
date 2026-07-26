/**
 * FPOMintHistoryScreen — Mint Audit Trail
 *
 * Shows all carbon tokens minted by this FPO with:
 *   Token ID | Farm | Farmer | Credits | Mint Date | TX Hash | Status
 *
 * Phase 17: Real blockchain — shows network badge + "View on PolygonScan" link
 * when blockchain_network === 'POLYGON_AMOY'.
 *
 * API: GET /fpo/mint-history
 */
import React, { useCallback, useState } from 'react';
import { FlatList, Linking, RefreshControl, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';

import { getFPOMintHistoryApi, type MintHistoryItem } from '../../api/fpoApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { StatusBadge } from '../../components/StatusBadge';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { EmptyState } from '../../components/EmptyState';
import { formatDateIN } from '../../utils/formatters';

// ── PolygonScan helper ─────────────────────────────────────────────────────────

/** Returns the Polygon Amoy testnet explorer URL for a tx hash. */
function getPolygonScanUrl(txHash: string): string {
  return `https://amoy.polygonscan.com/tx/${txHash}`;
}

function isRealChain(network: string | null | undefined): boolean {
  // Only networks that are NOT mock get a PolygonScan link
  return network === 'POLYGON_AMOY';
}

// ── Network badge ──────────────────────────────────────────────────────────────

function NetworkBadge({ network }: { network: string | null | undefined }) {
  if (!network) return null;

  if (isRealChain(network)) {
    return (
      <View style={badgeStyles.real}>
        <MaterialCommunityIcons name="ethereum" size={11} color="#7b1fa2" />
        <Text style={badgeStyles.realText}>Polygon Amoy</Text>
      </View>
    );
  }

  return (
    <View style={badgeStyles.mock}>
      <MaterialCommunityIcons name="flask-outline" size={11} color="#666" />
      <Text style={badgeStyles.mockText}>Mock</Text>
    </View>
  );
}

const badgeStyles = StyleSheet.create({
  real: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: '#f3e5f5', borderRadius: 6,
    paddingHorizontal: 6, paddingVertical: 2,
  },
  realText: { fontSize: 10, color: '#7b1fa2', fontWeight: '700' },
  mock: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: '#f5f5f5', borderRadius: 6,
    paddingHorizontal: 6, paddingVertical: 2,
  },
  mockText: { fontSize: 10, color: '#777', fontWeight: '600' },
});

// ── Main screen ────────────────────────────────────────────────────────────────

export function FPOMintHistoryScreen() {
  const [history, setHistory] = useState<MintHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const data = await getFPOMintHistoryApi();
      setHistory(data);
    } catch {
      setError('Failed to load mint history.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      fetchData();
    }, [fetchData]),
  );

  if (loading) return <LoadingView message="Loading mint history…" />;
  if (error) return <ErrorView message={error} onRetry={fetchData} />;

  const totalCredits = history.reduce((sum, h) => sum + h.credit_amount, 0);
  const realCount = history.filter(h => isRealChain(h.blockchain_network)).length;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        {/* Summary strip */}
        {history.length > 0 && (
          <GlassCard style={styles.summaryCard} opacity={0.92}>
            <View style={styles.summaryRow}>
              <View style={styles.summaryItem}>
                <Text variant="headlineMedium" style={styles.summaryNum}>{history.length}</Text>
                <Text variant="labelSmall" style={styles.summaryLabel}>TOKENS</Text>
              </View>
              <View style={styles.divider} />
              <View style={styles.summaryItem}>
                <Text variant="headlineMedium" style={[styles.summaryNum, { color: '#2e7d32' }]}>
                  {totalCredits}
                </Text>
                <Text variant="labelSmall" style={styles.summaryLabel}>CREDITS ISSUED</Text>
              </View>
              {realCount > 0 && (
                <>
                  <View style={styles.divider} />
                  <View style={styles.summaryItem}>
                    <Text variant="headlineMedium" style={[styles.summaryNum, { color: '#7b1fa2' }]}>
                      {realCount}
                    </Text>
                    <Text variant="labelSmall" style={styles.summaryLabel}>ON-CHAIN</Text>
                  </View>
                </>
              )}
            </View>
          </GlassCard>
        )}

        <SectionHeader icon="history" title="Mint Audit Trail" light />

        <FlatList
          data={history}
          keyExtractor={(item) => String(item.db_id)}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { setRefreshing(true); fetchData(); }}
              tintColor="#fff"
              colors={['#1565c0']}
            />
          }
          contentContainerStyle={history.length === 0 ? styles.emptyContainer : styles.listContent}
          ListEmptyComponent={
            <EmptyState
              icon="certificate-outline"
              title="No Tokens Minted Yet"
              message="Minted carbon tokens will appear here after the FPO completes the minting process."
            />
          }
          renderItem={({ item }) => (
            <GlassCard style={styles.card} opacity={0.92}>
              {/* Header row */}
              <View style={styles.cardHeader}>
                <View style={styles.tokenIdChip}>
                  <MaterialCommunityIcons name="certificate" size={14} color="#6a1b9a" />
                  <Text variant="labelSmall" style={styles.tokenIdText} numberOfLines={1}>
                    {item.token_id}
                  </Text>
                </View>
                <View style={styles.headerRight}>
                  <NetworkBadge network={item.blockchain_network} />
                  <StatusBadge status={item.status} />
                </View>
              </View>

              {/* Farm + Farmer */}
              <View style={styles.row}>
                <MaterialCommunityIcons name="home-outline" size={14} color="#888" />
                <Text variant="bodySmall" style={styles.rowText}>{item.farm_name}</Text>
              </View>
              <View style={styles.row}>
                <MaterialCommunityIcons name="account-outline" size={14} color="#888" />
                <Text variant="bodySmall" style={styles.rowText}>{item.farmer_name}</Text>
              </View>

              {/* Metrics */}
              <View style={styles.metricsRow}>
                <View style={styles.metric}>
                  <Text variant="headlineSmall" style={[styles.metricVal, { color: '#2e7d32' }]}>
                    {item.credit_amount}
                  </Text>
                  <Text variant="labelSmall" style={styles.metricLabel}>CREDITS</Text>
                </View>
                <View style={styles.metric}>
                  <Text variant="bodySmall" style={styles.metricVal}>
                    {item.minted_at ? formatDateIN(item.minted_at) : '—'}
                  </Text>
                  <Text variant="labelSmall" style={styles.metricLabel}>MINTED</Text>
                </View>
                <View style={styles.metric}>
                  <Text variant="bodySmall" style={styles.metricVal}>#{item.report_id}</Text>
                  <Text variant="labelSmall" style={styles.metricLabel}>REPORT</Text>
                </View>
              </View>

              {/* TX Hash + PolygonScan link */}
              {item.minted_tx_hash && (
                <View style={styles.txSection}>
                  <View style={styles.txRow}>
                    <MaterialCommunityIcons name="link-variant" size={12} color="#888" />
                    <Text variant="bodySmall" style={styles.txHash} numberOfLines={1} ellipsizeMode="middle">
                      {item.minted_tx_hash}
                    </Text>
                  </View>
                  {isRealChain(item.blockchain_network) && (
                    <TouchableOpacity
                      style={styles.scanLink}
                      onPress={() => Linking.openURL(getPolygonScanUrl(item.minted_tx_hash!))}
                      activeOpacity={0.7}
                    >
                      <MaterialCommunityIcons name="open-in-new" size={12} color="#7b1fa2" />
                      <Text style={styles.scanLinkText}>View on PolygonScan</Text>
                    </TouchableOpacity>
                  )}
                </View>
              )}

              {/* Contract address (real chain only) */}
              {isRealChain(item.blockchain_network) && item.contract_address && (
                <View style={styles.contractRow}>
                  <MaterialCommunityIcons name="file-document-outline" size={12} color="#aaa" />
                  <Text style={styles.contractText} numberOfLines={1} ellipsizeMode="middle">
                    Contract: {item.contract_address}
                  </Text>
                </View>
              )}
            </GlassCard>
          )}
        />
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  listContent: { paddingBottom: 32 },
  emptyContainer: { flex: 1, justifyContent: 'center' },

  summaryCard: { marginTop: 8 },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-around', paddingVertical: 4 },
  summaryItem: { alignItems: 'center', flex: 1 },
  divider: { width: 1, height: 40, backgroundColor: '#e0e0e0' },
  summaryNum: { fontWeight: '900', color: '#1b5e20' },
  summaryLabel: { color: '#888', marginTop: 2 },

  card: { marginBottom: 2 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  tokenIdChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: '#f3e5f5', paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: 8, flexShrink: 1, maxWidth: '55%',
  },
  tokenIdText: { color: '#6a1b9a', fontWeight: '700', flexShrink: 1 },

  row: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 3 },
  rowText: { color: '#555', flex: 1 },

  metricsRow: { flexDirection: 'row', gap: 20, marginTop: 10, marginBottom: 8 },
  metric: { alignItems: 'center' },
  metricVal: { fontWeight: '700', color: '#333' },
  metricLabel: { color: '#888', marginTop: 2, fontSize: 10 },

  txSection: { marginTop: 4, gap: 4 },
  txRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  txHash: { flex: 1, color: '#888', fontSize: 11, fontFamily: 'monospace' },

  scanLink: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    alignSelf: 'flex-start',
    backgroundColor: '#f3e5f5', borderRadius: 6,
    paddingHorizontal: 8, paddingVertical: 3,
  },
  scanLinkText: { fontSize: 11, color: '#7b1fa2', fontWeight: '700' },

  contractRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2 },
  contractText: { flex: 1, fontSize: 10, color: '#aaa', fontFamily: 'monospace' },
});
