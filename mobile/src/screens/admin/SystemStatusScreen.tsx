import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { getSystemStatusApi, getPaymentStatusApi, type PaymentStatus } from '../../api/adminApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { InfoRow } from '../../components/InfoRow';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import type { SystemStatus } from '../../types';

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <View style={[styles.dot, { backgroundColor: ok ? '#2e7d32' : '#c62828' }]} />
  );
}

export function SystemStatusScreen() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [payment, setPayment] = useState<PaymentStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const [sysData, payData] = await Promise.allSettled([
        getSystemStatusApi(),
        getPaymentStatusApi(),
      ]);
      if (sysData.status === 'fulfilled') setStatus(sysData.value);
      else throw new Error('System status unreachable');
      if (payData.status === 'fulfilled') setPayment(payData.value);
      // Payment status failing is non-fatal — user may not be authenticated
    } catch {
      setError('Failed to load system status. Backend may be unreachable.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return <LoadingView message="Checking system status…" />;
  if (error) return <ErrorView message={error} onRetry={fetchData} />;
  if (!status) return <ErrorView message="No status data." onRetry={fetchData} />;

  const apiOk = status.api_status === 'ok' || status.api_status === 'healthy';
  const dbOk = status.database_status === 'ok' || status.database_status === 'healthy';
  const blockchainConfigured = status.blockchain_configured;
  const overallOk = apiOk && dbOk;

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
              colors={['#bf360c']}
            />
          }
        >
          {/* Overall health banner */}
          <GlassCard
            style={[styles.overallCard, { borderLeftColor: overallOk ? '#2e7d32' : '#c62828' }]}
            opacity={0.95}
          >
            <View style={styles.overallRow}>
              <MaterialCommunityIcons
                name={overallOk ? 'check-circle' : 'alert-circle'}
                size={40}
                color={overallOk ? '#2e7d32' : '#c62828'}
              />
              <View style={styles.overallText}>
                <Text variant="titleMedium" style={[styles.overallTitle, { color: overallOk ? '#2e7d32' : '#c62828' }]}>
                  {overallOk ? 'All Systems Operational' : 'System Issue Detected'}
                </Text>
                <Text variant="bodySmall" style={styles.timestampText}>
                  {new Date(status.timestamp).toLocaleString('en-IN', {
                    day: 'numeric', month: 'short', year: 'numeric',
                    hour: '2-digit', minute: '2-digit',
                  })}
                </Text>
              </View>
            </View>
          </GlassCard>

          {/* Service health */}
          <SectionHeader icon="server" title="Service Health" light />
          <GlassCard opacity={0.92}>
            <View style={styles.serviceRow}>
              <StatusDot ok={apiOk} />
              <Text variant="labelMedium" style={styles.serviceLabel}>API Server</Text>
              <Text variant="bodySmall" style={[styles.serviceStatus, { color: apiOk ? '#2e7d32' : '#c62828' }]}>
                {status.api_status.toUpperCase()}
              </Text>
            </View>
            <View style={[styles.serviceRow, styles.serviceBorder]}>
              <StatusDot ok={dbOk} />
              <Text variant="labelMedium" style={styles.serviceLabel}>Database</Text>
              <Text variant="bodySmall" style={[styles.serviceStatus, { color: dbOk ? '#2e7d32' : '#c62828' }]}>
                {status.database_status.toUpperCase()}
              </Text>
            </View>
            <View style={[styles.serviceRow, styles.serviceBorder]}>
              <StatusDot ok={blockchainConfigured} />
              <Text variant="labelMedium" style={styles.serviceLabel}>Blockchain</Text>
              <Text variant="bodySmall" style={[styles.serviceStatus, { color: blockchainConfigured ? '#2e7d32' : '#e65100' }]}>
                {status.blockchain_mode.toUpperCase()}
              </Text>
            </View>
          </GlassCard>

          {/* Details */}
          <SectionHeader icon="information-outline" title="Configuration" light />
          <GlassCard opacity={0.92}>
            <InfoRow label="Blockchain Mode" value={status.blockchain_mode} />
            <InfoRow label="Blockchain Configured" value={blockchainConfigured ? 'Yes' : 'No (Mock Mode)'} />
            <InfoRow label="Total API Routes" value={String(status.total_routes)} />
          </GlassCard>

          {/* Payment Provider Status — sourced from GET /system/payment-status */}
          <SectionHeader icon="cash-multiple" title="Payment Provider" light />
          <GlassCard opacity={0.92}>
            {payment ? (
              <>
                <View style={styles.serviceRow}>
                  <StatusDot ok={payment.provider !== 'mock'} />
                  <Text variant="labelMedium" style={styles.serviceLabel}>Provider</Text>
                  <Text variant="bodySmall" style={[styles.serviceStatus,
                    { color: payment.provider === 'mock' ? '#e65100' : '#2e7d32' }]}>
                    {payment.provider.toUpperCase()}
                  </Text>
                </View>
                <View style={[styles.serviceRow, styles.serviceBorder]}>
                  <StatusDot ok={payment.mode !== 'mock'} />
                  <Text variant="labelMedium" style={styles.serviceLabel}>Mode</Text>
                  <Text variant="bodySmall" style={[styles.serviceStatus,
                    { color: payment.mode === 'live' ? '#2e7d32' : payment.mode === 'test' ? '#1565c0' : '#e65100' }]}>
                    {payment.mode.toUpperCase()}
                  </Text>
                </View>
                <View style={[styles.serviceRow, styles.serviceBorder]}>
                  <StatusDot ok={payment.configured} />
                  <Text variant="labelMedium" style={styles.serviceLabel}>Configured</Text>
                  <Text variant="bodySmall" style={[styles.serviceStatus,
                    { color: payment.configured ? '#2e7d32' : '#c62828' }]}>
                    {payment.configured ? 'YES' : 'NO'}
                  </Text>
                </View>
                {payment.provider !== 'mock' && (
                  <View style={[styles.serviceRow, styles.serviceBorder]}>
                    <StatusDot ok={!payment.execution_enabled} />
                    <Text variant="labelMedium" style={styles.serviceLabel}>Execution</Text>
                    <Text variant="bodySmall" style={[styles.serviceStatus,
                      { color: payment.execution_enabled ? '#e65100' : '#2e7d32' }]}>
                      {payment.execution_enabled ? 'ENABLED (test payouts on)' : 'DISABLED (safe)'}
                    </Text>
                  </View>
                )}
              </>
            ) : (
              <InfoRow label="Payment Status" value="Not available (requires auth)" last />
            )}
          </GlassCard>

          <View style={styles.bottomPad} />
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { paddingTop: 8, paddingBottom: 24 },

  overallCard: { marginTop: 8, borderLeftWidth: 5 },
  overallRow: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  overallText: { flex: 1 },
  overallTitle: { fontWeight: '800' },
  timestampText: { color: '#888', marginTop: 4 },

  serviceRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, gap: 10 },
  serviceBorder: { borderTopWidth: 1, borderTopColor: '#f0f0f0' },
  dot: { width: 10, height: 10, borderRadius: 5 },
  serviceLabel: { flex: 1, color: '#333', fontWeight: '600' },
  serviceStatus: { fontWeight: '700' },

  bottomPad: { height: 16 },
});
