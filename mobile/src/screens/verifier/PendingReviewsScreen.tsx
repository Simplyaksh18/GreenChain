import React, { useCallback, useEffect, useState } from 'react';
import {
  FlatList,
  RefreshControl,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getPendingVerificationsApi } from '../../api/verificationApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { StatusBadge } from '../../components/StatusBadge';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { EmptyState } from '../../components/EmptyState';
import type { VerificationRequest } from '../../types';
import type { VerifierStackParamList } from '../../navigation/VerifierStack';

type Props = NativeStackScreenProps<VerifierStackParamList, 'PendingReviews'>;

const RISK_COLOR: Record<string, string> = {
  LOW: '#2e7d32',
  MEDIUM: '#e65100',
  HIGH: '#c62828',
};

const REC_ICON: Record<string, keyof typeof MaterialCommunityIcons.glyphMap> = {
  APPROVE: 'check-circle-outline',
  MANUAL_REVIEW: 'eye-outline',
  REJECT: 'close-circle-outline',
};

export function PendingReviewsScreen({ navigation }: Props) {
  const [items, setItems] = useState<VerificationRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const data = await getPendingVerificationsApi();
      setItems(data);
    } catch {
      setError('Failed to load pending verifications.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const onRefresh = () => { setRefreshing(true); fetchData(); };

  if (loading) return <LoadingView message="Loading pending reviews…" />;
  if (error) return <ErrorView message={error} onRetry={fetchData} />;

  const highCount = items.filter((r) => r.risk_level === 'HIGH').length;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        {/* Summary bar */}
        <GlassCard style={styles.summaryCard} opacity={0.92}>
          <View style={styles.summaryRow}>
            <View style={styles.summaryItem}>
              <Text variant="headlineMedium" style={styles.summaryNum}>{items.length}</Text>
              <Text variant="labelSmall" style={styles.summaryLabel}>PENDING</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.summaryItem}>
              <Text variant="headlineMedium" style={[styles.summaryNum, highCount > 0 && styles.danger]}>
                {highCount}
              </Text>
              <Text variant="labelSmall" style={styles.summaryLabel}>HIGH RISK</Text>
            </View>
          </View>
        </GlassCard>

        <SectionHeader icon="clipboard-check-outline" title="Reports Awaiting Review" light />

        <FlatList
          data={items}
          keyExtractor={(i) => String(i.id)}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#fff" colors={['#6a1b9a']} />
          }
          contentContainerStyle={items.length === 0 ? styles.emptyContainer : styles.listContent}
          ListEmptyComponent={
            <EmptyState icon="check-all" message="No pending verifications — all clear!" />
          }
          renderItem={({ item }) => (
            <TouchableOpacity
              onPress={() => navigation.navigate('VerificationDetail', { verificationId: item.id })}
              activeOpacity={0.85}
            >
              <GlassCard style={[
                styles.card,
                item.risk_level === 'HIGH' && styles.highRiskCard,
              ]} opacity={0.9}>
                <View style={styles.cardHeader}>
                  <View style={styles.reportIdRow}>
                    <MaterialCommunityIcons name="file-document-outline" size={18} color="#6a1b9a" />
                    <Text variant="labelLarge" style={styles.reportId}>
                      Report #{item.carbon_report_id}
                    </Text>
                  </View>
                  <StatusBadge status={item.status} />
                </View>

                <View style={styles.cardBody}>
                  <View style={[styles.riskPill, { backgroundColor: RISK_COLOR[item.risk_level] + '20' }]}>
                    <Text style={[styles.riskText, { color: RISK_COLOR[item.risk_level] }]}>
                      {item.risk_level} RISK
                    </Text>
                  </View>
                  <Text variant="labelSmall" style={styles.scoreText}>
                    Score: {item.risk_score}
                  </Text>
                </View>

                <View style={styles.cardFooter}>
                  <View style={styles.recRow}>
                    <MaterialCommunityIcons
                      name={REC_ICON[item.recommendation] ?? 'information-outline'}
                      size={14}
                      color="#555"
                    />
                    <Text variant="bodySmall" style={styles.recText}>
                      AI: {item.recommendation.replace('_', ' ')}
                    </Text>
                  </View>
                  <Text variant="bodySmall" style={styles.dateText}>
                    {new Date(item.created_at).toLocaleDateString('en-IN', {
                      day: 'numeric', month: 'short', year: 'numeric',
                    })}
                  </Text>
                </View>

                <View style={styles.tapHint}>
                  <MaterialCommunityIcons name="chevron-right" size={20} color="#9e9e9e" />
                </View>
              </GlassCard>
            </TouchableOpacity>
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
  danger: { color: '#c62828' },

  card: { marginBottom: 2 },
  highRiskCard: { borderLeftWidth: 4, borderLeftColor: '#c62828' },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  reportIdRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  reportId: { fontWeight: '700', color: '#333' },

  cardBody: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  riskPill: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: 10 },
  riskText: { fontSize: 11, fontWeight: '800' },
  scoreText: { color: '#666' },

  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  recRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  recText: { color: '#555' },
  dateText: { color: '#888' },

  tapHint: { position: 'absolute', right: 12, top: '50%' },
});
