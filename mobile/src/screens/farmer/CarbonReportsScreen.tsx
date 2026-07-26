/**
 * CarbonReportsScreen — Phase 9B
 * Tab screen — auto-loads farms then fetches reports for selected farm.
 * GET /farms  →  GET /carbon-reports/farm/{farm_id}
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  FlatList,
  StyleSheet,
  TouchableOpacity,
  View,
  RefreshControl,
} from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { getFarmsApi } from '../../api/farmApi';
import { getReportsByFarmApi } from '../../api/carbonApi';
import { RoleBackground } from '../../components/RoleBackground';
import { StatusBadge } from '../../components/StatusBadge';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import type { Farm, CarbonReport } from '../../types';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { FarmerReportsParamList } from '../../navigation/FarmerReportsStack';

type Props = NativeStackScreenProps<FarmerReportsParamList, 'CarbonReports'>;

export function CarbonReportsScreen({ navigation }: Props) {
  const [farms, setFarms]           = useState<Farm[]>([]);
  const [selectedFarm, setSelectedFarm] = useState<Farm | null>(null);
  const [reports, setReports]       = useState<CarbonReport[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fetchAll = useCallback(async (farmOverride?: Farm) => {
    try {
      setError('');
      // value from GET /farms
      const farmList = await getFarmsApi({ limit: 20 });
      setFarms(farmList);
      const farm = farmOverride ?? farmList[0] ?? null;
      setSelectedFarm(farm);
      if (farm) {
        // value from GET /carbon-reports/farm/{farm_id}
        const reps = await getReportsByFarmApi(farm.id, { limit: 50 });
        setReports([...reps].reverse()); // newest first
      } else {
        setReports([]);
      }
    } catch {
      setError('Failed to load reports.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  const onRefresh = () => { setRefreshing(true); fetchAll(); };

  const switchFarm = async (farm: Farm) => {
    setSelectedFarm(farm);
    setLoading(true);
    await fetchAll(farm);
  };

  if (loading && reports.length === 0 && !refreshing) return <LoadingView message="Loading reports…" />;
  if (error) return <ErrorView message={error} onRetry={() => fetchAll()} />;

  const renderReport = ({ item }: { item: CarbonReport }) => {
    const hash = item.report_hash.length > 20
      ? `${item.report_hash.slice(0, 10)}…${item.report_hash.slice(-8)}`
      : item.report_hash;

    return (
      <TouchableOpacity
        onPress={() => navigation.navigate('CarbonReportDetail', { reportId: item.id })}
        activeOpacity={0.85}
      >
      <View style={styles.reportCard}>
        <View style={styles.reportHeader}>
          <Text variant="labelMedium" style={styles.reportId}>Report #{item.id}</Text>
          <StatusBadge status={item.status} />
        </View>

        <View style={styles.reportGrid}>
          <View style={styles.reportStat}>
            <MaterialCommunityIcons name="molecule-co2" size={18} color="#2e7d32" />
            <Text variant="bodySmall" style={styles.statLabel}>CO₂ Reduction</Text>
            <Text variant="labelLarge" style={styles.statValue}>
              {item.co2e_reduction_tonnes.toFixed(3)} tCO₂
            </Text>
          </View>
          <View style={styles.reportStat}>
            <MaterialCommunityIcons name="cash-multiple" size={18} color="#1565c0" />
            <Text variant="bodySmall" style={styles.statLabel}>Est. Credits</Text>
            <Text variant="labelLarge" style={[styles.statValue, styles.creditValue]}>
              {item.estimated_credits.toFixed(2)}
            </Text>
          </View>
          <View style={styles.reportStat}>
            <MaterialCommunityIcons name="gas-cylinder" size={18} color="#e65100" />
            <Text variant="bodySmall" style={styles.statLabel}>CH₄ Reduced</Text>
            <Text variant="labelLarge" style={styles.statValue}>
              {item.methane_reduction_kg.toFixed(2)} kg
            </Text>
          </View>
        </View>

        <View style={styles.reportFooter}>
          <Text variant="labelSmall" style={styles.hashText} numberOfLines={1}>
            🔗 {hash}
          </Text>
          <View style={styles.footerRight}>
            <Text variant="labelSmall" style={styles.dateText}>
              {new Date(item.created_at).toLocaleDateString('en-IN', {
                day: 'numeric', month: 'short', year: 'numeric',
              })}
            </Text>
            <MaterialCommunityIcons name="chevron-right" size={16} color="#bbb" />
          </View>
        </View>
      </View>
      </TouchableOpacity>
    );
  };

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        {/* Farm selector if multiple farms */}
        {farms.length > 1 && (
          <View style={styles.farmSelector}>
            {farms.map((f) => (
              <TouchableOpacity
                key={f.id}
                style={[styles.farmChip, selectedFarm?.id === f.id && styles.farmChipActive]}
                onPress={() => switchFarm(f)}
              >
                <Text style={[styles.farmChipText, selectedFarm?.id === f.id && styles.farmChipTextActive]}
                  numberOfLines={1}>
                  {f.farm_name}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {!selectedFarm ? (
          <View style={styles.emptyCenter}>
            <View style={styles.emptyCard}>
              <MaterialCommunityIcons name="file-alert-outline" size={48} color="#9e9e9e" />
              <Text variant="titleMedium" style={styles.emptyTitle}>No Farms Found</Text>
              <Text variant="bodyMedium" style={styles.emptyMsg}>Register a farm first to view carbon reports.</Text>
            </View>
          </View>
        ) : reports.length === 0 ? (
          <View style={styles.emptyCenter}>
            <View style={styles.emptyCard}>
              <MaterialCommunityIcons name="file-document-outline" size={48} color="#9e9e9e" />
              <Text variant="titleMedium" style={styles.emptyTitle}>No Reports Yet</Text>
              <Text variant="bodyMedium" style={styles.emptyMsg}>
                No carbon reports yet for {selectedFarm.farm_name}.{'\n\n'}Reports are generated automatically once a crop cycle ends and MRV data is collected. Start a crop cycle from your Farm Details screen.
              </Text>
            </View>
          </View>
        ) : (
          <FlatList
            data={reports}
            keyExtractor={(r) => String(r.id)}
            renderItem={renderReport}
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
              <Text variant="bodySmall" style={styles.listHeader}>
                {reports.length} report{reports.length !== 1 ? 's' : ''} for {selectedFarm.farm_name}
              </Text>
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
  listHeader: { color: 'rgba(255,255,255,0.7)', textAlign: 'center', marginBottom: 10 },

  // Farm selector chips
  farmSelector: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    padding: 12,
    paddingBottom: 0,
  },
  farmChip: {
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 20, borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.5)',
    backgroundColor: 'rgba(255,255,255,0.25)',
  },
  farmChipActive: { backgroundColor: 'rgba(255,255,255,0.92)', borderColor: '#2e7d32' },
  farmChipText: { color: 'rgba(255,255,255,0.8)', fontWeight: '600', fontSize: 12 },
  farmChipTextActive: { color: '#2e7d32' },

  // Report cards
  reportCard: {
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
  reportHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  reportId: { fontWeight: '700', color: '#333' },
  reportGrid: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 10 },
  reportStat: { alignItems: 'center', gap: 3, flex: 1 },
  statLabel: { color: '#888', textAlign: 'center' },
  statValue: { fontWeight: '700', color: '#333', textAlign: 'center' },
  creditValue: { color: '#1565c0' },
  reportFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', borderTopWidth: 1, borderTopColor: '#f0f0f0', paddingTop: 8 },
  hashText: { color: '#aaa', flex: 1, marginRight: 8 },
  footerRight: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  dateText: { color: '#888' },

  emptyCenter: { flex: 1, justifyContent: 'center', padding: 24 },
  emptyCard: {
    backgroundColor: 'rgba(255,255,255,0.88)',
    borderRadius: 20, padding: 28, alignItems: 'center', gap: 12,
  },
  emptyTitle: { fontWeight: '800', color: '#555' },
  emptyMsg: { textAlign: 'center', color: '#777', lineHeight: 22 },
});
