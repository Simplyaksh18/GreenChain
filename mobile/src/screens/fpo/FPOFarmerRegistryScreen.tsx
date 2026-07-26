/**
 * FPOFarmerRegistryScreen — Phase 11
 * GET /fpo/registry/farmers
 * Lists all farmers under the FPO with farm/credit summary.
 * Tapping a row opens FPOFarmerDetailScreen.
 */
import React, { useCallback, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import {
  FlatList, RefreshControl, StyleSheet, TouchableOpacity, View,
} from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getFPOFarmerRegistryApi, type FPOFarmerSummary } from '../../api/farmApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { EmptyState } from '../../components/EmptyState';
import type { FPOFarmsStackParamList } from '../../navigation/FPOFarmsStack';

type Props = NativeStackScreenProps<FPOFarmsStackParamList, 'FPOFarmerRegistry'>;

export function FPOFarmerRegistryScreen({ navigation }: Props) {
  const [farmers, setFarmers] = useState<FPOFarmerSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const data = await getFPOFarmerRegistryApi();
      setFarmers(data);
    } catch {
      setError('Failed to load farmer registry.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { fetchData(); }, [fetchData]));

  if (loading) return <LoadingView message="Loading farmer registry…" />;
  if (error) return <ErrorView message={error} onRetry={fetchData} />;

  const totalFarms = farmers.reduce((s, f) => s + f.total_farms, 0);
  const totalCredits = farmers.reduce((s, f) => s + f.total_available_credits, 0);

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        {/* Summary */}
        <GlassCard style={styles.summaryCard} opacity={0.92}>
          <View style={styles.summaryRow}>
            <View style={styles.summaryItem}>
              <Text variant="headlineSmall" style={styles.summaryNum}>{farmers.length}</Text>
              <Text variant="labelSmall" style={styles.summaryLabel}>FARMERS</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.summaryItem}>
              <Text variant="headlineSmall" style={styles.summaryNum}>{totalFarms}</Text>
              <Text variant="labelSmall" style={styles.summaryLabel}>FARMS</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.summaryItem}>
              <Text variant="headlineSmall" style={[styles.summaryNum, { color: '#1565c0' }]}>
                {totalCredits.toFixed(0)}
              </Text>
              <Text variant="labelSmall" style={styles.summaryLabel}>AVAIL CREDITS</Text>
            </View>
          </View>
        </GlassCard>

        <SectionHeader icon="account-group-outline" title="Farmer Registry" light />

        <FlatList
          data={farmers}
          keyExtractor={(f) => String(f.farmer_id)}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { setRefreshing(true); fetchData(); }}
              tintColor="#fff"
              colors={['#1565c0']}
            />
          }
          contentContainerStyle={farmers.length === 0 ? styles.emptyContainer : styles.listContent}
          ListEmptyComponent={
            <EmptyState icon="account-off-outline" message="No farmers in the registry." />
          }
          renderItem={({ item }) => (
            <TouchableOpacity
              onPress={() => navigation.navigate('FPOFarmerDetail', { farmer: item })}
              activeOpacity={0.85}
            >
              <GlassCard style={styles.card} opacity={0.9}>
                <View style={styles.cardHeader}>
                  <View style={styles.avatar}>
                    <MaterialCommunityIcons name="account" size={22} color="#1565c0" />
                  </View>
                  <View style={styles.headerText}>
                    <Text variant="labelLarge" style={styles.farmerName}>{item.name}</Text>
                    <Text variant="bodySmall" style={styles.farmerEmail}>{item.email}</Text>
                  </View>
                  <MaterialCommunityIcons name="chevron-right" size={20} color="#9e9e9e" />
                </View>

                <View style={styles.statsRow}>
                  <StatChip icon="home-outline" value={item.total_farms} label="Farms" />
                  <StatChip icon="check-circle-outline" value={item.approved_farms} label="Approved" color="#2e7d32" />
                  <StatChip icon="sprout-outline" value={item.active_crop_cycles} label="Active Cycles" color="#e65100" />
                  <StatChip icon="leaf" value={item.total_available_credits} label="Credits" color="#1565c0" />
                </View>
              </GlassCard>
            </TouchableOpacity>
          )}
        />
      </SafeAreaView>
    </RoleBackground>
  );
}

function StatChip({
  icon, value, label, color = '#555',
}: {
  icon: keyof typeof MaterialCommunityIcons.glyphMap;
  value: number;
  label: string;
  color?: string;
}) {
  return (
    <View style={styles.chip}>
      <MaterialCommunityIcons name={icon} size={13} color={color} />
      <Text style={[styles.chipValue, { color }]}>{value}</Text>
      <Text style={styles.chipLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  listContent: { paddingBottom: 24 },
  emptyContainer: { flex: 1, justifyContent: 'center' },

  summaryCard: { marginTop: 8 },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-around', paddingVertical: 4 },
  summaryItem: { alignItems: 'center', flex: 1 },
  divider: { width: 1, height: 40, backgroundColor: '#e0e0e0' },
  summaryNum: { fontWeight: '900', color: '#1b5e20' },
  summaryLabel: { color: '#888', marginTop: 2, fontSize: 9 },

  card: { marginBottom: 2 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  avatar: {
    width: 38, height: 38, borderRadius: 19,
    backgroundColor: '#e3f2fd', alignItems: 'center', justifyContent: 'center',
  },
  headerText: { flex: 1 },
  farmerName: { fontWeight: '700', color: '#333' },
  farmerEmail: { color: '#888', marginTop: 1 },

  statsRow: { flexDirection: 'row', gap: 4, flexWrap: 'wrap' },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: 'rgba(0,0,0,0.04)', borderRadius: 8,
    paddingHorizontal: 8, paddingVertical: 4,
  },
  chipValue: { fontSize: 12, fontWeight: '700' },
  chipLabel: { fontSize: 10, color: '#888' },
});
