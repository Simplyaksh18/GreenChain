/**
 * BuyerOrdersScreen — Phase 16
 * FPO views all orders across their listings and retires approved orders.
 * Navigate → RetirementCertificateScreen after retiring.
 */
import React, { useCallback, useState } from 'react';
import {
  Alert,
  FlatList,
  RefreshControl,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import {
  getAllOrders,
  markOrderPaid,
  retireOrder,
  type MarketplaceOrder,
} from '../../api/marketplaceApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { StatusBadge } from '../../components/StatusBadge';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { EmptyState } from '../../components/EmptyState';
import type { FPOMarketplaceStackParamList } from './FPOListingsScreen';

type Props = NativeStackScreenProps<FPOMarketplaceStackParamList, 'FPOBuyerOrders'>;

function OrderRow({
  order,
  onMarkPaid,
  onRetire,
  markingPaid,
  retiring,
}: {
  order: MarketplaceOrder;
  onMarkPaid: () => void;
  onRetire: () => void;
  markingPaid: boolean;
  retiring: boolean;
}) {
  return (
    <GlassCard style={styles.card}>
      <View style={styles.cardHeader}>
        <View>
          <Text style={styles.buyerName}>{order.buyer_name}</Text>
          {order.buyer_organization && (
            <Text style={styles.buyerOrg}>{order.buyer_organization}</Text>
          )}
        </View>
        <StatusBadge status={order.order_status} />
      </View>
      <View style={styles.cardMeta}>
        <View style={styles.metaItem}>
          <MaterialCommunityIcons name="leaf" size={14} color="#2e7d32" />
          <Text style={styles.metaText}>{order.credits_requested} credits</Text>
        </View>
        <View style={styles.metaItem}>
          <MaterialCommunityIcons name="currency-inr" size={14} color="#1565c0" />
          <Text style={styles.metaText}>₹{(order.quoted_amount / 100).toFixed(2)}</Text>
        </View>
        <View style={styles.metaItem}>
          <MaterialCommunityIcons name="format-list-numbered" size={14} color="#555" />
          <Text style={styles.metaText}>Listing #{order.listing_id}</Text>
        </View>
      </View>
      {order.order_status === 'APPROVED' && (
        <>
          <TouchableOpacity
            style={[styles.markPaidBtn, markingPaid && styles.btnDisabled]}
            onPress={onMarkPaid}
            disabled={markingPaid}
          >
            <MaterialCommunityIcons name="cash-check" size={16} color="#fff" />
            <Text style={styles.markPaidBtnTxt}>
              {markingPaid ? 'Recording…' : 'Mark Paid (Manual/Test)'}
            </Text>
          </TouchableOpacity>
          <Text style={styles.helperText}>
            Records payment manually for staging/test. No real gateway is called.
          </Text>
        </>
      )}
      {order.order_status === 'PAID' && (
        <TouchableOpacity
          style={[styles.retireBtn, retiring && styles.btnDisabled]}
          onPress={onRetire}
          disabled={retiring}
        >
          <MaterialCommunityIcons name="certificate" size={16} color="#fff" />
          <Text style={styles.retireBtnTxt}>
            {retiring ? 'Retiring…' : 'Retire Credits & Issue Certificate'}
          </Text>
        </TouchableOpacity>
      )}
    </GlassCard>
  );
}

export function BuyerOrdersScreen({ navigation }: Props) {
  const [orders, setOrders] = useState<MarketplaceOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [retiring, setRetiring] = useState<number | null>(null);
  const [markingPaid, setMarkingPaid] = useState<number | null>(null);

  const fetchData = useCallback(async (silent = false) => {
    try {
      if (!silent) setError('');
      const data = await getAllOrders();
      setOrders(data);
    } catch (e: any) {
      if (!silent) setError(e?.response?.data?.detail ?? 'Failed to load orders');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      fetchData();
    }, [fetchData])
  );

  const handleMarkPaid = (order: MarketplaceOrder) => {
    if (markingPaid === order.id) return;
    Alert.alert(
      'Record Manual Payment',
      `Mark order #${order.id} from ${order.buyer_name} as paid?\n\nThis records payment manually in staging/test mode. No real payment gateway is called.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Mark Paid',
          onPress: async () => {
            setMarkingPaid(order.id);
            try {
              await markOrderPaid(order.id);
              await fetchData(true);
            } catch (e: any) {
              Alert.alert(
                'Error',
                e?.response?.data?.detail ?? 'Unable to record payment. Please try again.',
              );
            } finally {
              setMarkingPaid(null);
            }
          },
        },
      ],
    );
  };

  const handleRetire = (order: MarketplaceOrder) => {
    Alert.prompt(
      'Retire Credits',
      `Retire ${order.credits_requested} credits for ${order.buyer_name}?\n\nEnter a retirement reason (optional):`,
      async (reason) => {
        setRetiring(order.id);
        try {
          await retireOrder(order.id, reason || undefined);
          navigation.navigate('FPORetirementCertificate', { orderId: order.id });
        } catch (e: any) {
          Alert.alert('Error', e?.response?.data?.detail ?? 'Failed to retire credits');
        } finally {
          setRetiring(null);
          fetchData(true);
        }
      },
      'plain-text',
      '',
    );
  };

  if (loading) return <LoadingView message="Loading orders…" />;
  if (error) return <ErrorView message={error} onRetry={() => fetchData()} />;

  const approved = orders.filter(o => o.order_status === 'APPROVED');
  const interested = orders.filter(o => o.order_status === 'INTERESTED');
  const retired = orders.filter(o => o.order_status === 'RETIRED');

  return (
    <RoleBackground role="FPO">
      <SafeAreaView style={styles.safe}>
        <FlatList
          data={orders}
          keyExtractor={item => String(item.id)}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { setRefreshing(true); fetchData(true); }}
            />
          }
          ListHeaderComponent={
            <View>
              <SectionHeader icon="receipt" title="Buyer Orders" />
              <View style={styles.statsRow}>
                <View style={styles.stat}>
                  <Text style={styles.statVal}>{interested.length}</Text>
                  <Text style={styles.statLbl}>Pending</Text>
                </View>
                <View style={styles.stat}>
                  <Text style={styles.statVal}>{approved.length}</Text>
                  <Text style={styles.statLbl}>Approved</Text>
                </View>
                <View style={styles.stat}>
                  <Text style={styles.statVal}>{retired.length}</Text>
                  <Text style={styles.statLbl}>Retired</Text>
                </View>
              </View>
            </View>
          }
          ListEmptyComponent={
            <EmptyState
              icon="receipt"
              title="No orders yet"
              message="When buyers express interest in your listings, orders will appear here."
            />
          }
          renderItem={({ item }) => (
            <OrderRow
              order={item}
              onMarkPaid={() => handleMarkPaid(item)}
              onRetire={() => handleRetire(item)}
              markingPaid={markingPaid === item.id}
              retiring={retiring === item.id}
            />
          )}
          contentContainerStyle={styles.list}
        />
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  list: { paddingBottom: 32, paddingHorizontal: 16 },
  statsRow: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 12 },
  stat: { alignItems: 'center' },
  statVal: { fontSize: 22, fontWeight: '700', color: '#1b5e20' },
  statLbl: { fontSize: 11, color: '#555' },
  card: { marginBottom: 12, padding: 14 },
  cardHeader: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 8 },
  buyerName: { fontSize: 15, fontWeight: '700', color: '#1b2e1b' },
  buyerOrg: { fontSize: 12, color: '#666', marginTop: 2 },
  cardMeta: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 10 },
  metaItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  metaText: { fontSize: 13, color: '#444' },
  retireBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: '#37474f',
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 16,
  },
  retireBtnTxt: { color: '#fff', fontWeight: '600', fontSize: 13 },
  markPaidBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: '#00695c',
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 16,
  },
  markPaidBtnTxt: { color: '#fff', fontWeight: '600', fontSize: 13 },
  helperText: {
    fontSize: 11,
    color: '#4e342e',
    marginTop: 6,
    textAlign: 'center',
  },
  btnDisabled: { opacity: 0.6 },
});
