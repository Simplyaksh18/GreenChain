import React, { useCallback, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import { FlatList, RefreshControl, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { getFPOFarmersListApi, type FPOFarmer } from '../../api/fpoApi';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { FPOFarmsStackParamList } from '../../navigation/FPOFarmsStack';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { InfoRow } from '../../components/InfoRow';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { EmptyState } from '../../components/EmptyState';

type Props = NativeStackScreenProps<FPOFarmsStackParamList, 'FPOFarmers'>;

export function FPOFarmersScreen({ navigation }: Props) {
  const [farmers, setFarmers] = useState<FPOFarmer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const data = await getFPOFarmersListApi();
      setFarmers(data);
    } catch {
      setError('Failed to load farmers.');
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

  if (loading) return <LoadingView message="Loading farmers…" />;
  if (error) return <ErrorView message={error} onRetry={fetchData} />;

  const activeCount = farmers.filter((f) => f.is_active).length;
  const approvedCount = farmers.filter((f) => f.is_approved).length;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        {/* Summary */}
        <GlassCard style={styles.summaryCard} opacity={0.92}>
          <View style={styles.summaryRow}>
            <View style={styles.summaryItem}>
              <Text variant="headlineMedium" style={styles.summaryNum}>{farmers.length}</Text>
              <Text variant="labelSmall" style={styles.summaryLabel}>TOTAL</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.summaryItem}>
              <Text variant="headlineMedium" style={styles.summaryNum}>{activeCount}</Text>
              <Text variant="labelSmall" style={styles.summaryLabel}>ACTIVE</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.summaryItem}>
              <Text variant="headlineMedium" style={styles.summaryNum}>{approvedCount}</Text>
              <Text variant="labelSmall" style={styles.summaryLabel}>APPROVED</Text>
            </View>
          </View>
        </GlassCard>

        <View style={styles.registryRow}>
          <SectionHeader icon="account-group-outline" title="Farmers in Your FPO" light />
          <TouchableOpacity
            style={styles.registryBtn}
            onPress={() => navigation.navigate('FPOFarmerRegistry')}
          >
            <MaterialCommunityIcons name="view-list-outline" size={16} color="#fff" />
            <Text style={styles.registryBtnText}>Registry</Text>
          </TouchableOpacity>
        </View>

        <FlatList
          data={farmers}
          keyExtractor={(f) => String(f.id)}
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
            <EmptyState icon="account-off-outline" message="No farmers linked to your FPO yet." />
          }
          renderItem={({ item }) => (
            <GlassCard style={styles.card} opacity={0.9}>
              <View style={styles.cardHeader}>
                <View style={styles.avatarCircle}>
                  <MaterialCommunityIcons name="account" size={22} color="#1565c0" />
                </View>
                <View style={styles.headerText}>
                  <Text variant="labelLarge" style={styles.farmerName}>{item.name}</Text>
                  <Text variant="bodySmall" style={styles.farmerEmail}>{item.email}</Text>
                </View>
                <View style={[styles.statusPill, { backgroundColor: item.is_approved ? '#e8f5e9' : '#fff3e0' }]}>
                  <Text style={[styles.statusText, { color: item.is_approved ? '#2e7d32' : '#e65100' }]}>
                    {item.is_approved ? 'Approved' : 'Pending'}
                  </Text>
                </View>
              </View>
              <View style={styles.metaRow}>
                <InfoRow
                  label="Active"
                  value={item.is_active ? 'Yes' : 'No'}
                />
                <InfoRow
                  label="Joined"
                  value={new Date(item.created_at).toLocaleDateString('en-IN', {
                    day: 'numeric', month: 'short', year: 'numeric',
                  })}
                />
              </View>
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
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  avatarCircle: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: '#e3f2fd',
    alignItems: 'center', justifyContent: 'center',
  },
  headerText: { flex: 1 },
  farmerName: { fontWeight: '700', color: '#333' },
  farmerEmail: { color: '#888', marginTop: 1 },
  statusPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10 },
  statusText: { fontSize: 12, fontWeight: '700' },
  metaRow: {},
  registryRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingRight: 16 },
  registryBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(255,255,255,0.25)', borderRadius: 14,
    paddingHorizontal: 10, paddingVertical: 5,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.4)',
  },
  registryBtnText: { color: '#fff', fontSize: 12, fontWeight: '700' },
});
