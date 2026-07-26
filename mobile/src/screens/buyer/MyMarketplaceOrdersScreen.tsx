/**
 * MyMarketplaceOrdersScreen — Phase 22B buyer flow.
 *
 * The current user's own purchase requests (buyer_user_id = self). Uses
 * humanized status labels per Phase H:
 *   INTERESTED → Request submitted
 *   APPROVED   → Approved — awaiting payment confirmation
 *   PAID       → Payment recorded
 *   REJECTED   → Rejected
 *   RETIRED    → Retired — certificate available
 */
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

import { getMyOrders, type MyOrder } from '../../api/marketplaceApi';
import { GlassCard } from '../../components/GlassCard';
import { EmptyState } from '../../components/EmptyState';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { StatusBadge } from '../../components/StatusBadge';
import { RoleBackground } from '../../components/RoleBackground';
import { SectionHeader } from '../../components/SectionHeader';
import type { BuyerMarketplaceStackParamList } from '../../navigation/BuyerMarketplaceStack';

type Props = NativeStackScreenProps<BuyerMarketplaceStackParamList, 'BuyerMyOrders'>;

function paiseToRupees(paise: number): string {
  return (paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const STATUS_LABEL: Record<string, string> = {
  INTERESTED: 'Request submitted',
  APPROVED: 'Approved — awaiting payment confirmation',
  PAID: 'Payment recorded',
  REJECTED: 'Rejected',
  RETIRED: 'Retired — certificate available',
};

function OrderCard({ order, onOpenCertificate }: { order: MyOrder; onOpenCertificate?: () => void }) {
  const label = STATUS_LABEL[order.order_status] ?? order.order_status;
  const totalRs = paiseToRupees(order.quoted_amount);
  return (
    <GlassCard style={styles.card}>
      <View style={styles.headerRow}>
        <Text variant="labelLarge" style={styles.orderId}>Order #{order.id}</Text>
        <StatusBadge status={order.order_status} />
      </View>
      <Text style={styles.statusText}>{label}</Text>

      <View style={styles.metaRow}>
        <MaterialCommunityIcons name="leaf" size={14} color="#2e7d32" />
        <Text style={styles.metaText}>{order.credits_requested} credits</Text>
      </View>
      <View style={styles.metaRow}>
        <MaterialCommunityIcons name="currency-inr" size={14} color="#1565c0" />
        <Text style={styles.metaText}>Total ₹{totalRs}</Text>
      </View>
      <View style={styles.metaRow}>
        <MaterialCommunityIcons name="format-list-numbered" size={14} color="#555" />
        <Text style={styles.metaText}>Listing #{order.listing_id}</Text>
      </View>
      {order.paid_at ? (
        <View style={styles.metaRow}>
          <MaterialCommunityIcons name="check-circle-outline" size={14} color="#00695c" />
          <Text style={styles.metaText}>Payment recorded</Text>
        </View>
      ) : null}

      {order.order_status === 'RETIRED' && onOpenCertificate ? (
        <TouchableOpacity style={styles.certBtn} onPress={onOpenCertificate}>
          <MaterialCommunityIcons name="certificate" size={16} color="#fff" />
          <Text style={styles.certBtnText}>View Certificate</Text>
        </TouchableOpacity>
      ) : null}
    </GlassCard>
  );
}

export function MyMarketplaceOrdersScreen({ navigation }: Props) {
  const [orders, setOrders] = useState<MyOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const fetchOrders = useCallback(async (silent = false) => {
    try {
      if (!silent) setError('');
      const data = await getMyOrders();
      setOrders(data);
    } catch (e: any) {
      if (!silent) setError(e?.response?.data?.detail ?? 'Failed to load your orders');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchOrders(true);
  };

  if (loading) return <LoadingView message="Loading your orders…" />;
  if (error) return <ErrorView message={error} onRetry={() => { setLoading(true); fetchOrders(); }} />;

  return (
    <RoleBackground role="FARMER">
      <SafeAreaView style={{ flex: 1 }} edges={['bottom']}>
        <SectionHeader icon="cart-outline" title="My Purchases" />
        <FlatList
          data={orders}
          keyExtractor={(o) => String(o.id)}
          contentContainerStyle={orders.length === 0 ? styles.emptyContent : styles.listContent}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          ListEmptyComponent={
            <EmptyState
              icon="cart-outline"
              title="No purchases yet"
              message="Browse the marketplace to submit your first request."
            />
          }
          renderItem={({ item }) => (
            <OrderCard
              order={item}
              onOpenCertificate={() =>
                navigation.navigate('BuyerRetirementCertificate', { orderId: item.id })
              }
            />
          )}
        />
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  listContent: { paddingVertical: 8, paddingBottom: 24 },
  emptyContent: { flexGrow: 1 },
  card: { padding: 14, gap: 4 },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  orderId: { color: '#1b5e20', fontWeight: '700' },
  statusText: { color: '#333', fontSize: 13, marginBottom: 6 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  metaText: { fontSize: 12, color: '#555' },
  certBtn: {
    marginTop: 10,
    backgroundColor: '#6a1b9a',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'flex-start',
  },
  certBtnText: { color: '#fff', fontWeight: '600' },
});
