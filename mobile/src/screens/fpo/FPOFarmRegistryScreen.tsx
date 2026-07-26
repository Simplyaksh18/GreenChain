/**
 * FPOFarmRegistryScreen — Phase 11
 * GET /fpo/registry/farms?farm_status_filter=...
 * Shows all farms under FPO with lifecycle status tabs and actions.
 * Actions: Approve (PENDING_APPROVAL), Suspend (APPROVED), Restore (SUSPENDED)
 */
import React, { useCallback, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import {
  Alert, FlatList, RefreshControl, StyleSheet, TouchableOpacity, View,
} from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import {
  getFPOFarmRegistryApi,
  getFPORegistrySummaryApi,
  approveFarmNewApi,
  suspendFarmApi,
  restoreFarmApi,
  type FPORegistrySummary,
} from '../../api/farmApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { InfoRow } from '../../components/InfoRow';
import { AppButton } from '../../components/AppButton';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { EmptyState } from '../../components/EmptyState';
import type { Farm, FarmStatus } from '../../types';

type FilterTab = 'ALL' | 'PENDING_APPROVAL' | 'APPROVED' | 'SUSPENDED';

const TAB_LABELS: Record<FilterTab, string> = {
  ALL: 'All',
  PENDING_APPROVAL: 'Pending',
  APPROVED: 'Approved',
  SUSPENDED: 'Suspended',
};

const STATUS_COLOR: Record<string, string> = {
  DRAFT: '#9e9e9e',
  PENDING_APPROVAL: '#e65100',
  APPROVED: '#2e7d32',
  SUSPENDED: '#ad1457',
  ARCHIVED: '#546e7a',
};

export function FPOFarmRegistryScreen() {
  const [farms, setFarms] = useState<Farm[]>([]);
  const [summary, setSummary] = useState<FPORegistrySummary | null>(null);
  const [tab, setTab] = useState<FilterTab>('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [actionId, setActionId] = useState<number | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const [farmsData, summaryData] = await Promise.allSettled([
        getFPOFarmRegistryApi(),
        getFPORegistrySummaryApi(),
      ]);
      if (farmsData.status === 'fulfilled') setFarms(farmsData.value);
      if (summaryData.status === 'fulfilled') setSummary(summaryData.value);
    } catch {
      setError('Failed to load farm registry.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { fetchData(); }, [fetchData]));

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
              setActionId(farm.id);
              const updated = await approveFarmNewApi(farm.id);
              setFarms((prev) => prev.map((f) => (f.id === farm.id ? updated : f)));
              Alert.alert('Approved', `"${farm.farm_name}" is now approved.`);
            } catch (e: any) {
              Alert.alert('Error', e?.response?.data?.detail ?? 'Failed to approve farm.');
            } finally {
              setActionId(null);
            }
          },
        },
      ],
    );
  };

  const handleSuspend = (farm: Farm) => {
    Alert.alert(
      'Suspend Farm',
      `Suspend "${farm.farm_name}"? The farmer will not be able to submit new reports.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Suspend',
          style: 'destructive',
          onPress: async () => {
            try {
              setActionId(farm.id);
              const updated = await suspendFarmApi(farm.id, 'Suspended by FPO');
              setFarms((prev) => prev.map((f) => (f.id === farm.id ? updated : f)));
            } catch (e: any) {
              Alert.alert('Error', e?.response?.data?.detail ?? 'Failed to suspend farm.');
            } finally {
              setActionId(null);
            }
          },
        },
      ],
    );
  };

  const handleRestore = (farm: Farm) => {
    Alert.alert(
      'Restore Farm',
      `Restore "${farm.farm_name}" to active status?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Restore',
          onPress: async () => {
            try {
              setActionId(farm.id);
              const updated = await restoreFarmApi(farm.id);
              setFarms((prev) => prev.map((f) => (f.id === farm.id ? updated : f)));
            } catch (e: any) {
              Alert.alert('Error', e?.response?.data?.detail ?? 'Failed to restore farm.');
            } finally {
              setActionId(null);
            }
          },
        },
      ],
    );
  };

  if (loading) return <LoadingView message="Loading farm registry…" />;
  if (error) return <ErrorView message={error} onRetry={fetchData} />;

  const filtered = tab === 'ALL'
    ? farms
    : farms.filter((f) => f.farm_status === tab);

  const tabs: FilterTab[] = ['ALL', 'PENDING_APPROVAL', 'APPROVED', 'SUSPENDED'];

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        {/* Summary strip */}
        {summary && (
          <GlassCard style={styles.summaryCard} opacity={0.92}>
            <View style={styles.summaryRow}>
              <SummaryItem value={summary.total_farms} label="TOTAL" />
              <View style={styles.divider} />
              <SummaryItem value={summary.approved_farms} label="APPROVED" color="#2e7d32" />
              <View style={styles.divider} />
              <SummaryItem value={summary.pending_farms} label="PENDING" color="#e65100" />
              <View style={styles.divider} />
              <SummaryItem value={summary.suspended_farms} label="SUSPENDED" color="#ad1457" />
            </View>
            <View style={styles.acreageRow}>
              <MaterialCommunityIcons name="texture-box" size={14} color="#888" />
              <Text variant="labelSmall" style={styles.acreageText}>
                {summary.total_acreage.toFixed(1)} acres total · {summary.active_crop_cycles} active cycles
              </Text>
            </View>
          </GlassCard>
        )}

        {/* Filter tabs */}
        <View style={styles.tabRow}>
          {tabs.map((t) => {
            const count = t === 'ALL'
              ? farms.length
              : farms.filter((f) => f.farm_status === t).length;
            return (
              <TouchableOpacity
                key={t}
                style={[styles.tabChip, tab === t && styles.tabChipActive]}
                onPress={() => setTab(t)}
              >
                <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
                  {TAB_LABELS[t]} ({count})
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        <SectionHeader icon="home-group" title="Farm Registry" light />

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
          contentContainerStyle={filtered.length === 0 ? styles.emptyContainer : styles.listContent}
          ListEmptyComponent={
            <EmptyState icon="home-off-outline" message="No farms in this category." />
          }
          renderItem={({ item }) => {
            const statusColor = STATUS_COLOR[item.farm_status] ?? '#9e9e9e';
            const isPending = item.farm_status === 'PENDING_APPROVAL';
            const isApproved = item.farm_status === 'APPROVED';
            const isSuspended = item.farm_status === 'SUSPENDED';

            return (
              <GlassCard style={styles.card} opacity={0.9}>
                <View style={styles.cardHeader}>
                  <MaterialCommunityIcons name="home-outline" size={18} color={statusColor} />
                  <Text variant="labelLarge" style={styles.farmName}>{item.farm_name}</Text>
                  <StatusPill label={item.farm_status} color={statusColor} />
                </View>

                <InfoRow label="Location" value={`${item.village}, ${item.district}`} />
                <InfoRow label="Area" value={`${item.land_area_acres} acres`} />
                <InfoRow label="Soil" value={item.soil_type} />
                <InfoRow label="Water" value={item.water_source} />
                {item.approved_at && (
                  <InfoRow
                    label="Approved"
                    value={new Date(item.approved_at).toLocaleDateString('en-IN', {
                      day: 'numeric', month: 'short', year: 'numeric',
                    })}
                  />
                )}

                <View style={styles.actionsRow}>
                  {isPending && (
                    <AppButton
                      mode="contained"
                      buttonColor="#2e7d32"
                      icon="check-circle-outline"
                      onPress={() => handleApprove(item)}
                      loading={actionId === item.id}
                      disabled={actionId !== null}
                      style={styles.actionBtn}
                    >
                      Approve
                    </AppButton>
                  )}
                  {isApproved && (
                    <AppButton
                      mode="outlined"
                      icon="pause-circle-outline"
                      onPress={() => handleSuspend(item)}
                      loading={actionId === item.id}
                      disabled={actionId !== null}
                      style={[styles.actionBtn, styles.suspendBtn]}
                    >
                      Suspend
                    </AppButton>
                  )}
                  {isSuspended && (
                    <AppButton
                      mode="contained"
                      buttonColor="#1565c0"
                      icon="restore"
                      onPress={() => handleRestore(item)}
                      loading={actionId === item.id}
                      disabled={actionId !== null}
                      style={styles.actionBtn}
                    >
                      Restore
                    </AppButton>
                  )}
                </View>
              </GlassCard>
            );
          }}
        />
      </SafeAreaView>
    </RoleBackground>
  );
}

function SummaryItem({
  value, label, color = '#1b5e20',
}: { value: number; label: string; color?: string }) {
  return (
    <View style={styles.summaryItem}>
      <Text variant="headlineSmall" style={[styles.summaryNum, { color }]}>
        {value}
      </Text>
      <Text variant="labelSmall" style={styles.summaryLabel}>{label}</Text>
    </View>
  );
}

function StatusPill({ label, color }: { label: string; color: string }) {
  return (
    <View style={[styles.statusPill, { backgroundColor: color + '22' }]}>
      <Text style={[styles.statusText, { color }]}>
        {label.replace('_', ' ')}
      </Text>
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
  summaryNum: { fontWeight: '900' },
  summaryLabel: { color: '#888', marginTop: 2, fontSize: 9 },
  acreageRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 6, justifyContent: 'center' },
  acreageText: { color: '#888' },

  tabRow: { flexDirection: 'row', gap: 6, paddingHorizontal: 16, paddingTop: 8, flexWrap: 'wrap' },
  tabChip: {
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: 16,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.5)',
    backgroundColor: 'rgba(255,255,255,0.2)',
  },
  tabChipActive: { backgroundColor: 'rgba(255,255,255,0.92)', borderColor: '#1565c0' },
  tabText: { color: 'rgba(255,255,255,0.85)', fontSize: 11, fontWeight: '600' },
  tabTextActive: { color: '#1565c0' },

  card: { marginBottom: 2 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  farmName: { flex: 1, fontWeight: '700', color: '#333' },
  statusPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10 },
  statusText: { fontSize: 10, fontWeight: '700' },

  actionsRow: { marginTop: 8, flexDirection: 'row', gap: 8 },
  actionBtn: { flex: 1 },
  suspendBtn: { borderColor: '#ad1457' },
});
