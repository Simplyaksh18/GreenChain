import React, { useCallback, useEffect, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import { Alert, FlatList, RefreshControl, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { getFPOFarmsApi } from '../../api/fpoApi';
import { approveFarmApi } from '../../api/farmApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { InfoRow } from '../../components/InfoRow';
import { AppButton } from '../../components/AppButton';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { EmptyState } from '../../components/EmptyState';
import type { Farm } from '../../types';

type FilterMode = 'all' | 'pending' | 'approved';

export function FPOFarmsScreen() {
  const [farms, setFarms] = useState<Farm[]>([]);
  const [filter, setFilter] = useState<FilterMode>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [approvingId, setApprovingId] = useState<number | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const data = await getFPOFarmsApi();
      setFarms(data);
    } catch {
      setError('Failed to load farms.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Refresh when screen gains focus so newly submitted farmer farms appear immediately
  useFocusEffect(
    useCallback(() => {
      fetchData();
    }, [fetchData]),
  );

  const handleApprove = (farm: Farm) => {
    Alert.alert(
      'Approve Farm',
      `Approve "${farm.farm_name}" (${farm.land_area_acres} acres, ${farm.village})?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Approve',
          onPress: async () => {
            try {
              setApprovingId(farm.id);
              const updated = await approveFarmApi(farm.id);
              setFarms((prev) => prev.map((f) => (f.id === farm.id ? updated : f)));
            } catch (e: any) {
              const msg = e?.response?.data?.detail ?? 'Failed to approve farm.';
              Alert.alert('Error', msg);
            } finally {
              setApprovingId(null);
            }
          },
        },
      ],
    );
  };

  if (loading) return <LoadingView message="Loading farms…" />;
  if (error) return <ErrorView message={error} onRetry={fetchData} />;

  const approvedCount = farms.filter((f) => f.is_approved).length;
  const pendingCount = farms.length - approvedCount;

  const filtered = filter === 'pending'
    ? farms.filter((f) => !f.is_approved)
    : filter === 'approved'
    ? farms.filter((f) => f.is_approved)
    : farms;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        {/* Summary */}
        <GlassCard style={styles.summaryCard} opacity={0.92}>
          <View style={styles.summaryRow}>
            <View style={styles.summaryItem}>
              <Text variant="headlineMedium" style={styles.summaryNum}>{farms.length}</Text>
              <Text variant="labelSmall" style={styles.summaryLabel}>TOTAL</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.summaryItem}>
              <Text variant="headlineMedium" style={[styles.summaryNum, { color: '#2e7d32' }]}>{approvedCount}</Text>
              <Text variant="labelSmall" style={styles.summaryLabel}>APPROVED</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.summaryItem}>
              <Text variant="headlineMedium" style={[styles.summaryNum, { color: '#e65100' }]}>{pendingCount}</Text>
              <Text variant="labelSmall" style={styles.summaryLabel}>PENDING</Text>
            </View>
          </View>
        </GlassCard>

        {/* Filter tabs */}
        <View style={styles.filterRow}>
          {(['all', 'pending', 'approved'] as FilterMode[]).map((f) => (
            <TouchableOpacity
              key={f}
              style={[styles.filterChip, filter === f && styles.filterChipActive]}
              onPress={() => setFilter(f)}
            >
              <Text style={[styles.filterText, filter === f && styles.filterTextActive]}>
                {f === 'all' ? `All (${farms.length})` : f === 'pending' ? `Pending (${pendingCount})` : `Approved (${approvedCount})`}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <SectionHeader icon="home-group" title="Farms in Your FPO" light />

        <FlatList
          data={filtered}
          keyExtractor={(f) => String(f.id)}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { setRefreshing(true); fetchData(); }}
              tintColor="#fff"
              colors={['#1565c0']}
            />
          }
          contentContainerStyle={farms.length === 0 ? styles.emptyContainer : styles.listContent}
          ListEmptyComponent={
            <EmptyState icon="home-off-outline" message="No farms linked to your FPO." />
          }
          renderItem={({ item }) => (
            <GlassCard
              style={[styles.card, !item.is_approved && styles.pendingCard]}
              opacity={0.9}
            >
              <View style={styles.cardHeader}>
                <MaterialCommunityIcons
                  name="home-outline"
                  size={20}
                  color={item.is_approved ? '#2e7d32' : '#e65100'}
                />
                <Text variant="labelLarge" style={styles.farmName}>{item.farm_name}</Text>
                <View style={[
                  styles.statusPill,
                  { backgroundColor: item.is_approved ? '#e8f5e9' : '#fff3e0' },
                ]}>
                  <Text style={[styles.statusText, { color: item.is_approved ? '#2e7d32' : '#e65100' }]}>
                    {item.is_approved ? 'Approved' : 'Pending'}
                  </Text>
                </View>
              </View>

              <InfoRow label="Location" value={`${item.village}, ${item.district}, ${item.state}`} />
              <InfoRow label="Area" value={`${item.land_area_acres} acres`} />
              <InfoRow label="Soil Type" value={item.soil_type} />
              <InfoRow label="Water Source" value={item.water_source} />

              {!item.is_approved && (
                <AppButton
                  mode="contained"
                  onPress={() => handleApprove(item)}
                  loading={approvingId === item.id}
                  disabled={approvingId !== null}
                  buttonColor="#1565c0"
                  icon="check-circle-outline"
                >
                  Approve Farm
                </AppButton>
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
  listContent: { paddingBottom: 24 },
  emptyContainer: { flex: 1, justifyContent: 'center' },

  summaryCard: { marginTop: 8 },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-around', paddingVertical: 4 },
  summaryItem: { alignItems: 'center', flex: 1 },
  divider: { width: 1, height: 40, backgroundColor: '#e0e0e0' },
  summaryNum: { fontWeight: '900', color: '#1b5e20' },
  summaryLabel: { color: '#888', marginTop: 2 },

  card: { marginBottom: 2 },
  pendingCard: { borderLeftWidth: 4, borderLeftColor: '#e65100' },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  farmName: { flex: 1, fontWeight: '700', color: '#333' },
  statusPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10 },
  statusText: { fontSize: 12, fontWeight: '700' },
  approveBtn: { marginTop: 10 },
  filterRow: { flexDirection: 'row', gap: 8, paddingHorizontal: 16, paddingTop: 8 },
  filterChip: {
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.5)',
    backgroundColor: 'rgba(255,255,255,0.2)',
  },
  filterChipActive: { backgroundColor: 'rgba(255,255,255,0.92)', borderColor: '#1565c0' },
  filterText: { color: 'rgba(255,255,255,0.8)', fontSize: 12, fontWeight: '600' },
  filterTextActive: { color: '#1565c0' },
});
