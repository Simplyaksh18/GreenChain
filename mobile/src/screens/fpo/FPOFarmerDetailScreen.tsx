/**
 * FPOFarmerDetailScreen — Phase 11
 * GET /fpo/registry/farmers/{farmer_id}
 * Comprehensive farmer profile: farms, crop cycles, credit balances, verification history.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { ScrollView, RefreshControl, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getFPOFarmerDetailApi } from '../../api/farmApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { InfoRow } from '../../components/InfoRow';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { EmptyState } from '../../components/EmptyState';
import type { FPOFarmsStackParamList } from '../../navigation/FPOFarmsStack';

type Props = NativeStackScreenProps<FPOFarmsStackParamList, 'FPOFarmerDetail'>;

interface FarmerDetail {
  farmer: { id: number; name: string; email: string; is_active: boolean; is_approved: boolean; created_at: string };
  farms: Array<{ id: number; farm_name: string; farm_status: string; land_area_acres: number; village: string; district: string }>;
  credit_balances: Array<{ id: number; credits_earned: number; credits_available: number; credits_distributed: number; status: string; carbon_report_id: number }>;
  verification_history: Array<{ id: number; status: string; risk_level: string; risk_score: number; created_at: string; verified_at: string | null }>;
}

const STATUS_COLOR: Record<string, string> = {
  APPROVED: '#2e7d32', PENDING_APPROVAL: '#e65100', SUSPENDED: '#ad1457',
  DRAFT: '#9e9e9e', ARCHIVED: '#546e7a',
  VERIFIED: '#2e7d32', REJECTED: '#c62828', PENDING: '#e65100', MANUAL_REVIEW: '#7b1fa2',
  EARNED: '#1565c0', TOKENIZED: '#6a1b9a', DISTRIBUTED: '#2e7d32',
};

export function FPOFarmerDetailScreen({ route, navigation }: Props) {
  const { farmer: summaryFarmer } = route.params;
  const [detail, setDetail] = useState<FarmerDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const data = await getFPOFarmerDetailApi(summaryFarmer.farmer_id);
      setDetail(data);
    } catch {
      setError('Failed to load farmer details.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [summaryFarmer.farmer_id]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return <LoadingView message="Loading farmer details…" />;
  if (error) return <ErrorView message={error} onRetry={fetchData} />;
  if (!detail) return <ErrorView message="Farmer data not found." onRetry={fetchData} />;

  const { farmer, farms, credit_balances, verification_history } = detail;
  const totalEarned = credit_balances.reduce((s, b) => s + b.credits_earned, 0);
  const totalAvailable = credit_balances.reduce((s, b) => s + b.credits_available, 0);
  const totalDistributed = credit_balances.reduce((s, b) => s + b.credits_distributed, 0);

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { setRefreshing(true); fetchData(); }}
              tintColor="#fff"
              colors={['#1565c0']}
            />
          }
        >
          {/* Farmer Profile */}
          <GlassCard style={styles.profileCard} opacity={0.95}>
            <View style={styles.profileRow}>
              <View style={styles.avatar}>
                <MaterialCommunityIcons name="account" size={32} color="#1565c0" />
              </View>
              <View style={styles.profileText}>
                <Text variant="titleMedium" style={styles.farmerName}>{farmer.name}</Text>
                <Text variant="bodySmall" style={styles.farmerEmail}>{farmer.email}</Text>
                <View style={styles.badgeRow}>
                  <View style={[styles.badge, { backgroundColor: farmer.is_active ? '#e8f5e9' : '#fce4ec' }]}>
                    <Text style={[styles.badgeText, { color: farmer.is_active ? '#2e7d32' : '#c62828' }]}>
                      {farmer.is_active ? 'Active' : 'Inactive'}
                    </Text>
                  </View>
                  <View style={[styles.badge, { backgroundColor: farmer.is_approved ? '#e8f5e9' : '#fff3e0' }]}>
                    <Text style={[styles.badgeText, { color: farmer.is_approved ? '#2e7d32' : '#e65100' }]}>
                      {farmer.is_approved ? 'Verified' : 'Unverified'}
                    </Text>
                  </View>
                </View>
              </View>
            </View>
            <InfoRow
              label="Member Since"
              value={new Date(farmer.created_at).toLocaleDateString('en-IN', {
                day: 'numeric', month: 'long', year: 'numeric',
              })}
              last
            />
          </GlassCard>

          {/* Credit Summary */}
          <SectionHeader icon="leaf" title="Credit Summary" light />
          <GlassCard opacity={0.9}>
            <View style={styles.creditRow}>
              <CreditStat label="EARNED" value={totalEarned} color="#1565c0" />
              <View style={styles.vDivider} />
              <CreditStat label="AVAILABLE" value={totalAvailable} color="#2e7d32" />
              <View style={styles.vDivider} />
              <CreditStat label="DISTRIBUTED" value={totalDistributed} color="#6a1b9a" />
            </View>
          </GlassCard>

          {/* Farms */}
          <SectionHeader icon="home-group" title={`Farms (${farms.length})`} light />
          {farms.length === 0 ? (
            <EmptyState icon="home-off-outline" message="No farms linked." />
          ) : (
            farms.map((farm) => {
              const color = STATUS_COLOR[farm.farm_status] ?? '#9e9e9e';
              return (
                <GlassCard key={farm.id} style={styles.listCard} opacity={0.88}>
                  <View style={styles.listCardHeader}>
                    <MaterialCommunityIcons name="home-outline" size={16} color={color} />
                    <Text variant="labelMedium" style={styles.listCardTitle}>{farm.farm_name}</Text>
                    <View style={[styles.pill, { backgroundColor: color + '22' }]}>
                      <Text style={[styles.pillText, { color }]}>
                        {farm.farm_status.replace('_', ' ')}
                      </Text>
                    </View>
                  </View>
                  <InfoRow label="Location" value={`${farm.village}, ${farm.district}`} />
                  <InfoRow label="Area" value={`${farm.land_area_acres} acres`} last />

                  {/* Evidence & MRV quick-actions — FPO primary workflow */}
                  <View style={styles.actionRow}>
                    <TouchableOpacity
                      style={[styles.actionBtn, { backgroundColor: '#e3f2fd' }]}
                      onPress={() => navigation.navigate('FPOEvidenceList', { farmId: farm.id, farmName: farm.farm_name })}
                      activeOpacity={0.75}
                    >
                      <MaterialCommunityIcons name="image-multiple-outline" size={15} color="#1565c0" />
                      <Text style={[styles.actionBtnText, { color: '#1565c0' }]}>Evidence</Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                      style={[styles.actionBtn, { backgroundColor: '#e8f5e9' }]}
                      onPress={() => navigation.navigate('FPOAddEvidence', { farmId: farm.id, farmName: farm.farm_name })}
                      activeOpacity={0.75}
                    >
                      <MaterialCommunityIcons name="plus-circle-outline" size={15} color="#2e7d32" />
                      <Text style={[styles.actionBtnText, { color: '#2e7d32' }]}>Add Evidence</Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                      style={[styles.actionBtn, { backgroundColor: '#fce4ec' }]}
                      onPress={() => navigation.navigate('FPOMrvImport', { farmId: farm.id, farmName: farm.farm_name })}
                      activeOpacity={0.75}
                    >
                      <MaterialCommunityIcons name="file-import-outline" size={15} color="#ad1457" />
                      <Text style={[styles.actionBtnText, { color: '#ad1457' }]}>MRV Import</Text>
                    </TouchableOpacity>
                  </View>
                </GlassCard>
              );
            })
          )}

          {/* Credit Balances */}
          <SectionHeader icon="cash-multiple" title={`Credit Balances (${credit_balances.length})`} light />
          {credit_balances.length === 0 ? (
            <EmptyState icon="cash-remove" message="No credit balances yet." />
          ) : (
            credit_balances.map((bal) => {
              const color = STATUS_COLOR[bal.status] ?? '#9e9e9e';
              return (
                <GlassCard key={bal.id} style={styles.listCard} opacity={0.88}>
                  <View style={styles.listCardHeader}>
                    <MaterialCommunityIcons name="cash" size={16} color={color} />
                    <Text variant="labelMedium" style={styles.listCardTitle}>
                      Balance #{bal.id}
                    </Text>
                    <View style={[styles.pill, { backgroundColor: color + '22' }]}>
                      <Text style={[styles.pillText, { color }]}>{bal.status}</Text>
                    </View>
                  </View>
                  <InfoRow label="Report #" value={String(bal.carbon_report_id)} />
                  <InfoRow label="Earned" value={`${bal.credits_earned} credits`} />
                  <InfoRow label="Available" value={`${bal.credits_available} credits`} />
                  <InfoRow label="Distributed" value={`${bal.credits_distributed} credits`} last />
                </GlassCard>
              );
            })
          )}

          {/* Verification History */}
          <SectionHeader icon="shield-check-outline" title={`Verification History (${verification_history.length})`} light />
          {verification_history.length === 0 ? (
            <EmptyState icon="shield-off-outline" message="No verification records." />
          ) : (
            verification_history.map((vr) => {
              const color = STATUS_COLOR[vr.status] ?? '#9e9e9e';
              const riskColor =
                vr.risk_level === 'HIGH' ? '#c62828'
                : vr.risk_level === 'MEDIUM' ? '#e65100'
                : '#2e7d32';
              return (
                <GlassCard key={vr.id} style={styles.listCard} opacity={0.88}>
                  <View style={styles.listCardHeader}>
                    <MaterialCommunityIcons name="shield-outline" size={16} color={color} />
                    <Text variant="labelMedium" style={styles.listCardTitle}>VR #{vr.id}</Text>
                    <View style={[styles.pill, { backgroundColor: color + '22' }]}>
                      <Text style={[styles.pillText, { color }]}>{vr.status}</Text>
                    </View>
                  </View>
                  <InfoRow label="Risk Score" value={`${(vr.risk_score * 100).toFixed(0)}%`} />
                  <InfoRow
                    label="Risk Level"
                    value={<Text style={{ color: riskColor, fontWeight: '700', fontSize: 13 }}>{vr.risk_level}</Text>}
                  />
                  <InfoRow
                    label="Submitted"
                    value={new Date(vr.created_at).toLocaleDateString('en-IN', {
                      day: 'numeric', month: 'short', year: 'numeric',
                    })}
                  />
                  {vr.verified_at && (
                    <InfoRow
                      label="Verified"
                      value={new Date(vr.verified_at).toLocaleDateString('en-IN', {
                        day: 'numeric', month: 'short', year: 'numeric',
                      })}
                      last
                    />
                  )}
                </GlassCard>
              );
            })
          )}

          <View style={styles.bottomPad} />
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

function CreditStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <View style={styles.creditStat}>
      <Text variant="headlineSmall" style={[styles.creditValue, { color }]}>{value}</Text>
      <Text variant="labelSmall" style={styles.creditLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { paddingTop: 8, paddingBottom: 32 },

  profileCard: { marginTop: 8 },
  profileRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, marginBottom: 12 },
  avatar: {
    width: 56, height: 56, borderRadius: 28,
    backgroundColor: '#e3f2fd', alignItems: 'center', justifyContent: 'center',
  },
  profileText: { flex: 1 },
  farmerName: { fontWeight: '800', color: '#1b5e20', marginBottom: 2 },
  farmerEmail: { color: '#888', marginBottom: 6 },
  badgeRow: { flexDirection: 'row', gap: 6 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  badgeText: { fontSize: 11, fontWeight: '700' },

  creditRow: { flexDirection: 'row', justifyContent: 'space-around', paddingVertical: 4 },
  creditStat: { alignItems: 'center', flex: 1 },
  creditValue: { fontWeight: '900' },
  creditLabel: { color: '#888', marginTop: 2, fontSize: 9 },
  vDivider: { width: 1, height: 40, backgroundColor: '#e0e0e0' },

  listCard: { marginBottom: 2 },
  listCardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  listCardTitle: { flex: 1, fontWeight: '700', color: '#333' },
  pill: { paddingHorizontal: 7, paddingVertical: 2, borderRadius: 8 },
  pillText: { fontSize: 10, fontWeight: '700' },

  bottomPad: { height: 16 },

  actionRow: { flexDirection: 'row', gap: 6, marginTop: 8, flexWrap: 'wrap' },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  actionBtnText: { fontSize: 11, fontWeight: '700' },
});
