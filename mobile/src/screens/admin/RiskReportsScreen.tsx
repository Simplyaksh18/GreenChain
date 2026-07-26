import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { getRiskReportsApi } from '../../api/adminApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { StatusBadge } from '../../components/StatusBadge';
import { InfoRow } from '../../components/InfoRow';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { EmptyState } from '../../components/EmptyState';
import type { VerificationRequest } from '../../types';

const RISK_COLOR: Record<string, string> = {
  LOW: '#2e7d32',
  MEDIUM: '#e65100',
  HIGH: '#c62828',
};

export function RiskReportsScreen() {
  const [items, setItems] = useState<VerificationRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const data = await getRiskReportsApi();
      setItems(data);
    } catch {
      setError('Failed to load risk reports.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return <LoadingView message="Loading risk reports…" />;
  if (error) return <ErrorView message={error} onRetry={fetchData} />;

  const highCount = items.filter((r) => r.risk_level === 'HIGH').length;
  const medCount = items.filter((r) => r.risk_level === 'MEDIUM').length;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        {/* Summary */}
        <GlassCard style={styles.summaryCard} opacity={0.92}>
          <View style={styles.summaryRow}>
            <View style={styles.summaryItem}>
              <Text variant="headlineMedium" style={styles.summaryNum}>{items.length}</Text>
              <Text variant="labelSmall" style={styles.summaryLabel}>TOTAL</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.summaryItem}>
              <Text variant="headlineMedium" style={[styles.summaryNum, { color: '#c62828' }]}>{highCount}</Text>
              <Text variant="labelSmall" style={styles.summaryLabel}>HIGH RISK</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.summaryItem}>
              <Text variant="headlineMedium" style={[styles.summaryNum, { color: '#e65100' }]}>{medCount}</Text>
              <Text variant="labelSmall" style={styles.summaryLabel}>MEDIUM</Text>
            </View>
          </View>
        </GlassCard>

        <SectionHeader icon="alert-circle-outline" title="Risk Reports" light />

        <FlatList
          data={items}
          keyExtractor={(i) => String(i.id)}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { setRefreshing(true); fetchData(); }}
              tintColor="#fff"
              colors={['#bf360c']}
            />
          }
          contentContainerStyle={items.length === 0 ? styles.emptyContainer : styles.listContent}
          ListEmptyComponent={
            <EmptyState icon="shield-check-outline" message="No risk reports found." />
          }
          renderItem={({ item }) => {
            const riskColor = RISK_COLOR[item.risk_level] ?? '#555';
            return (
              <GlassCard style={[styles.card, { borderLeftColor: riskColor, borderLeftWidth: 4 }]} opacity={0.9}>
                <View style={styles.cardHeader}>
                  <View style={styles.titleRow}>
                    <MaterialCommunityIcons name="file-document-outline" size={18} color="#bf360c" />
                    <Text variant="labelLarge" style={styles.reportId}>Report #{item.carbon_report_id}</Text>
                  </View>
                  <StatusBadge status={item.status} />
                </View>
                <View style={styles.metaRow}>
                  <View style={[styles.riskPill, { backgroundColor: riskColor + '20' }]}>
                    <Text style={[styles.riskText, { color: riskColor }]}>{item.risk_level} RISK</Text>
                  </View>
                  <Text variant="labelSmall" style={styles.scoreText}>Score: {item.risk_score}</Text>
                </View>
                <InfoRow label="Recommendation" value={item.recommendation.replace('_', ' ')} />
                <InfoRow
                  label="Submitted"
                  value={new Date(item.created_at).toLocaleDateString('en-IN', {
                    day: 'numeric', month: 'short', year: 'numeric',
                  })}
                />
                {item.remarks && <InfoRow label="Remarks" value={item.remarks} />}
              </GlassCard>
            );
          }}
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
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  reportId: { fontWeight: '700', color: '#333' },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  riskPill: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: 10 },
  riskText: { fontSize: 11, fontWeight: '800' },
  scoreText: { color: '#666' },
});
