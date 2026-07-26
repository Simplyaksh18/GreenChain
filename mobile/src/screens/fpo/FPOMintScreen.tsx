/**
 * FPOMintScreen — Phase 9C (9C-bugfix-v2)
 * FPO mints custodial carbon tokens for verified reports from their farms.
 *
 * Root cause of "already minted" bug:
 *   The previous version called GET /tokens/my-wallet to detect minted reports.
 *   That endpoint is FARMER-ONLY — FPO gets 403, alreadyMintedReportIds stays empty,
 *   and every VERIFIED report appeared mintable even if already minted.
 *
 * Fix:
 *   Use GET /fpo/tokens/minted-report-ids (new FPO-accessible endpoint) instead.
 *
 * Backend: POST /fpo/tokens/mint/{report_id}
 * Lists:   GET /fpo/farms → GET /carbon-reports/farm/{farm_id}
 *          GET /fpo/tokens/minted-report-ids (new)
 */
import React, { useCallback, useState } from 'react';
import {
  Alert,
  FlatList,
  RefreshControl,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { FPOMintStackParamList } from '../../navigation/FPOMintStack';
import { getFPOMintableReportsApi, type MintableReport as MintableReportItem } from '../../api/fpoApi';
import { mintFPOTokenApi } from '../../api/tokenApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { StatusBadge } from '../../components/StatusBadge';
import { AppButton } from '../../components/AppButton';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { EmptyState } from '../../components/EmptyState';
type Props = NativeStackScreenProps<FPOMintStackParamList, 'MintQueue'>;

// The mintable-reports endpoint already filters out minted items and enriches with farmer name.
// sessionMinted tracks IDs minted in this session before next refresh.
export function FPOMintScreen({ navigation }: Props) {
  const [mintable, setMintable]           = useState<MintableReportItem[]>([]);
  const [sessionMinted, setSessionMinted] = useState<Set<number>>(new Set());
  const [loading, setLoading]             = useState(true);
  const [error, setError]                 = useState('');
  const [refreshing, setRefreshing]       = useState(false);
  const [mintingByReportId, setMintingByReportId] = useState<Record<number, boolean>>({});

  const fetchData = useCallback(async () => {
    try {
      setError('');
      // GET /fpo/mintable-reports returns only VERIFIED+unminted reports — simple and correct.
      const data = await getFPOMintableReportsApi();
      setMintable(data);
      // Clear session-minted after fresh fetch so UI stays consistent
      setSessionMinted(new Set());
    } catch {
      setError('Failed to load verified reports.');
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

  const handleMint = (item: MintableReportItem) => {
    Alert.alert(
      'Mint Carbon Token',
      `Mint custodial carbon token for Report #${item.report_id}?\n\nFarm: ${item.farm_name}\nFarmer: ${item.farmer_name}\nEstimated Credits: ${item.estimated_credits}\n\nThis action cannot be undone.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Mint Token',
          onPress: async () => {
            const rid = item.report_id;
            try {
              setMintingByReportId((prev) => ({ ...prev, [rid]: true }));
              await mintFPOTokenApi(rid);
              setSessionMinted((prev) => new Set([...prev, rid]));
              const isZeroCredit = item.estimated_credits === 0;
              Alert.alert(
                isZeroCredit ? 'Certificate Issued ✓' : 'Token Minted ✓',
                isZeroCredit
                  ? `Verification certificate issued for Report #${rid}. No tradable credits (CO₂e below 1 tCO₂e threshold).`
                  : `Carbon token minted for Report #${rid}. Farmer credit balance has been updated.`,
                [{ text: 'OK', onPress: () => fetchData() }],
              );
            } catch (e: any) {
              const detail = e?.response?.data?.detail;
              let msg: string;
              if (typeof detail === 'string') {
                msg = detail;
              } else if (Array.isArray(detail)) {
                msg = detail.map((d: any) => d?.msg ?? String(d)).join('\n');
              } else {
                msg = 'Failed to mint token. Check that the FPO wallet is configured and the farm is linked correctly.';
              }
              Alert.alert('Mint Failed', msg);
            } finally {
              setMintingByReportId((prev) => { const n = { ...prev }; delete n[rid]; return n; });
            }
          },
        },
      ],
    );
  };

  if (loading) return <LoadingView message="Loading verified reports…" />;
  if (error) return <ErrorView message={error} onRetry={fetchData} />;

  // Items still visible but just minted this session are hidden (will disappear on next refresh)
  const visibleItems = mintable.filter((m) => !sessionMinted.has(m.report_id));
  const readyCount = visibleItems.length;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        {/* Info Banner */}
        <GlassCard style={styles.infoBanner} opacity={0.92}>
          <View style={styles.bannerRow}>
            <MaterialCommunityIcons name="information-outline" size={18} color="#1565c0" />
            <Text variant="bodySmall" style={styles.bannerText}>
              Mint custodial carbon tokens for verified reports from your FPO's farms.
              The token is held in your FPO vault; the farmer receives a credit balance entry.
            </Text>
          </View>
          {/* Phase 17 — Blockchain mode indicator */}
          <View style={[styles.bannerRow, styles.chainBanner]}>
            <MaterialCommunityIcons name="ethereum" size={14} color="#7b1fa2" />
            <Text variant="labelSmall" style={styles.chainText}>
              On-chain — Polygon Amoy Testnet · Contract {'•'} ERC-1155
            </Text>
          </View>
        </GlassCard>

        <View style={styles.sectionRow}>
          <SectionHeader
            icon="certificate-outline"
            title={`Mint Queue · ${readyCount} Ready`}
            light
            style={styles.sectionFlex}
          />
          <TouchableOpacity
            style={styles.historyBtn}
            onPress={() => navigation.navigate('MintHistory')}
          >
            <MaterialCommunityIcons name="history" size={14} color="#fff" />
            <Text style={styles.historyBtnText}>History</Text>
          </TouchableOpacity>
        </View>

        <FlatList
          data={visibleItems}
          keyExtractor={(item) => String(item.report_id)}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { setRefreshing(true); fetchData(); }}
              tintColor="#fff"
              colors={['#1565c0']}
            />
          }
          contentContainerStyle={visibleItems.length === 0 ? styles.emptyContainer : styles.listContent}
          ListEmptyComponent={
            <EmptyState
              icon="check-all"
              title="Mint Queue Empty"
              message="All verified reports have been minted. Check Mint History for completed tokens."
            />
          }
          renderItem={({ item }) => (
            <GlassCard style={styles.card} opacity={0.92}>
              <View style={styles.cardHeader}>
                <View style={{ flex: 1 }}>
                  <Text variant="labelSmall" style={styles.reportLabel}>REPORT #{item.report_id}</Text>
                  <Text variant="labelLarge" style={styles.farmName}>{item.farm_name}</Text>
                  <View style={styles.farmerRow}>
                    <MaterialCommunityIcons name="account-outline" size={12} color="#888" />
                    <Text variant="bodySmall" style={styles.farmerName}>{item.farmer_name}</Text>
                  </View>
                </View>
                <StatusBadge status={item.report_status} />
              </View>

              <View style={styles.metricsRow}>
                <View style={styles.metric}>
                  <Text variant="headlineSmall" style={styles.metricVal}>
                    {item.co2e_reduction_tonnes.toFixed(3)}
                  </Text>
                  <Text variant="labelSmall" style={styles.metricLabel}>tCO₂e</Text>
                </View>
                <View style={styles.metric}>
                  <Text variant="headlineSmall" style={[styles.metricVal, { color: '#2e7d32' }]}>
                    {item.estimated_credits}
                  </Text>
                  <Text variant="labelSmall" style={styles.metricLabel}>CREDITS</Text>
                </View>
                {item.verified_at && (
                  <View style={styles.metric}>
                    <Text variant="bodySmall" style={styles.metricVal}>
                      {new Date(item.verified_at).toLocaleDateString('en-IN')}
                    </Text>
                    <Text variant="labelSmall" style={styles.metricLabel}>VERIFIED</Text>
                  </View>
                )}
              </View>

              {item.estimated_credits === 0 && (
                <View style={styles.zeroCreditNote}>
                  <MaterialCommunityIcons name="alert-circle-outline" size={14} color="#e65100" />
                  <Text variant="labelSmall" style={styles.zeroCreditText}>
                    Below 1 tCO₂e threshold. A zero-credit certificate will be issued.
                  </Text>
                </View>
              )}

              <AppButton
                mode="contained"
                onPress={() => handleMint(item)}
                loading={mintingByReportId[item.report_id] === true}
                disabled={mintingByReportId[item.report_id] === true}
                buttonColor="#1565c0"
                icon="certificate-outline"
                style={styles.mintBtn}
              >
                {item.estimated_credits === 0 ? 'Issue Certificate' : 'Mint Carbon Token'}
              </AppButton>
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

  infoBanner: { marginTop: 8 },
  bannerRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  bannerText: { flex: 1, color: '#1565c0', lineHeight: 18 },
  chainBanner: { marginTop: 8, paddingTop: 8, borderTopWidth: 1, borderTopColor: '#e8d5f0' },
  chainText: { flex: 1, color: '#7b1fa2', fontWeight: '700' },

  card: { marginBottom: 2 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 },
  reportLabel: { color: '#888', marginBottom: 2 },
  farmName: { fontWeight: '700', color: '#333' },
  farmerRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2 },
  farmerName: { color: '#888' },

  metricsRow: { flexDirection: 'row', gap: 24, marginBottom: 10 },
  metric: { alignItems: 'center' },
  metricVal: { fontWeight: '900', color: '#1b5e20' },
  metricLabel: { color: '#888', marginTop: 2 },

  zeroCreditNote: { flexDirection: 'row', gap: 6, alignItems: 'center', marginBottom: 8 },
  zeroCreditText: { flex: 1, color: '#e65100' },

  location: { color: '#888', marginBottom: 10 },

  mintedBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  mintedText: { color: '#2e7d32', fontWeight: '700' },

  mintBtn: { marginTop: 4 },

  sectionRow: { flexDirection: 'row', alignItems: 'center', paddingRight: 16 },
  sectionFlex: { flex: 1 },
  historyBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(255,255,255,0.2)',
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14,
  },
  historyBtnText: { color: '#fff', fontSize: 12, fontWeight: '700' },
});
