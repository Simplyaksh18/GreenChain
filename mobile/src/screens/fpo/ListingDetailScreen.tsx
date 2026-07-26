/**
 * ListingDetailScreen — Phase 16
 * FPO views listing details and manages incoming orders.
 *
 * Actions:
 *  - Update price / pause / cancel listing
 *  - View all orders → approve / reject / retire
 */
import React, { useCallback, useState } from 'react';
import {
  Alert,
  ScrollView,
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
  getListingOrders,
  getFPOListings,
  cancelListing,
  approveOrder,
  rejectOrder,
  markOrderPaid,
  type MarketplaceListing,
  type MarketplaceOrder,
} from '../../api/marketplaceApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { StatusBadge } from '../../components/StatusBadge';
import { AppButton } from '../../components/AppButton';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import type { FPOMarketplaceStackParamList } from './FPOListingsScreen';

type Props = NativeStackScreenProps<FPOMarketplaceStackParamList, 'FPOListingDetail'>;

function InfoRow({ label, value }: { label: string; value: string | number }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

function OrderCard({
  order,
  onApprove,
  onReject,
  onMarkPaid,
  onRetire,
  markingPaid,
}: {
  order: MarketplaceOrder;
  onApprove: () => void;
  onReject: () => void;
  onMarkPaid: () => void;
  onRetire: () => void;
  markingPaid: boolean;
}) {
  return (
    <GlassCard style={styles.orderCard}>
      <View style={styles.orderHeader}>
        <Text style={styles.orderBuyer}>{order.buyer_name}</Text>
        <StatusBadge status={order.order_status} />
      </View>
      {order.buyer_organization && (
        <Text style={styles.orderOrg}>{order.buyer_organization}</Text>
      )}
      <View style={styles.orderMeta}>
        <Text style={styles.orderCredits}>{order.credits_requested} credits</Text>
        <Text style={styles.orderAmount}>
          ₹{(order.quoted_amount / 100).toFixed(2)}
        </Text>
      </View>
      <View style={styles.orderActions}>
        {order.order_status === 'INTERESTED' && (
          <>
            <TouchableOpacity style={[styles.actionBtn, styles.approveBtn]} onPress={onApprove}>
              <MaterialCommunityIcons name="check" size={16} color="#fff" />
              <Text style={styles.actionBtnTxt}>Approve</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.actionBtn, styles.rejectBtn]} onPress={onReject}>
              <MaterialCommunityIcons name="close" size={16} color="#fff" />
              <Text style={styles.actionBtnTxt}>Reject</Text>
            </TouchableOpacity>
          </>
        )}
        {order.order_status === 'APPROVED' && (
          <TouchableOpacity
            style={[styles.actionBtn, styles.markPaidBtn, markingPaid && styles.actionBtnDisabled]}
            onPress={onMarkPaid}
            disabled={markingPaid}
          >
            <MaterialCommunityIcons name="cash-check" size={16} color="#fff" />
            <Text style={styles.actionBtnTxt}>
              {markingPaid ? 'Recording…' : 'Mark Paid (Manual/Test)'}
            </Text>
          </TouchableOpacity>
        )}
        {order.order_status === 'PAID' && (
          <TouchableOpacity style={[styles.actionBtn, styles.retireBtn]} onPress={onRetire}>
            <MaterialCommunityIcons name="certificate" size={16} color="#fff" />
            <Text style={styles.actionBtnTxt}>Retire Credits</Text>
          </TouchableOpacity>
        )}
      </View>
    </GlassCard>
  );
}

export function ListingDetailScreen({ route, navigation }: Props) {
  const { listingId } = route.params;
  const [listing, setListing] = useState<MarketplaceListing | null>(null);
  const [orders, setOrders] = useState<MarketplaceOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [markingPaid, setMarkingPaid] = useState<number | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const [allListings, orderData] = await Promise.all([
        getFPOListings(),
        // Returns [] when no orders exist — backend now guarantees this
        getListingOrders(listingId).catch(() => [] as MarketplaceOrder[]),
      ]);
      const found = allListings.find(l => l.id === listingId) ?? null;
      setListing(found);
      setOrders(orderData);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Failed to load listing');
    } finally {
      setLoading(false);
    }
  }, [listingId]);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      fetchData();
    }, [fetchData])
  );

  const handleCancel = () => {
    Alert.alert('Cancel Listing', 'Cancel this listing? This cannot be undone.', [
      { text: 'No', style: 'cancel' },
      {
        text: 'Yes, Cancel',
        style: 'destructive',
        onPress: async () => {
          try {
            await cancelListing(listingId);
            navigation.goBack();
          } catch (e: any) {
            Alert.alert('Error', e?.response?.data?.detail ?? 'Failed to cancel');
          }
        },
      },
    ]);
  };

  const handleApprove = (orderId: number) => {
    Alert.alert('Approve Order', 'Approve this buyer\'s interest?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Approve',
        onPress: async () => {
          try {
            await approveOrder(orderId);
            fetchData();
          } catch (e: any) {
            Alert.alert('Error', e?.response?.data?.detail ?? 'Failed to approve');
          }
        },
      },
    ]);
  };

  const handleReject = (orderId: number) => {
    Alert.alert('Reject Order', 'Reject this buyer\'s interest?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Reject',
        style: 'destructive',
        onPress: async () => {
          try {
            await rejectOrder(orderId, 'Rejected by FPO');
            fetchData();
          } catch (e: any) {
            Alert.alert('Error', e?.response?.data?.detail ?? 'Failed to reject');
          }
        },
      },
    ]);
  };

  const handleMarkPaid = (orderId: number, buyerName: string) => {
    if (markingPaid === orderId) return;
    Alert.alert(
      'Record Manual Payment',
      `Mark order #${orderId} from ${buyerName} as paid?\n\nRecords payment manually in staging/test mode. No real gateway is called.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Mark Paid',
          onPress: async () => {
            setMarkingPaid(orderId);
            try {
              await markOrderPaid(orderId);
              await fetchData();
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

  const handleRetire = (orderId: number) => {
    Alert.alert(
      'Retire Credits',
      'Retire the credits for this order? This is permanent and generates a certificate.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Retire',
          onPress: () =>
            navigation.navigate('FPOBuyerOrders', {
              listingId,
              listingCredits: listing?.credits_available ?? 0,
            }),
        },
      ]
    );
  };

  if (loading) return <LoadingView message="Loading listing…" />;
  if (error) return <ErrorView message={error} onRetry={fetchData} />;
  if (!listing) return <ErrorView message="Listing not found." onRetry={fetchData} />;

  const pendingOrders = orders.filter(o => o.order_status === 'INTERESTED');
  const approvedOrders = orders.filter(o => o.order_status === 'APPROVED');

  return (
    <RoleBackground role="FPO">
      <SafeAreaView style={styles.safe}>
        <ScrollView contentContainerStyle={styles.scroll}>
          <SectionHeader icon="format-list-bulleted" title={`Listing #${listing.id}`} />

          {/* Listing summary */}
          <GlassCard style={styles.card} opacity={0.96}>
            <Text style={styles.sectionTitle}>Listing Details</Text>
            <InfoRow label="Status" value={listing.listing_status} />
            <InfoRow label="Credits Listed" value={listing.credits_listed} />
            <InfoRow label="Credits Available" value={listing.credits_available} />
            <InfoRow label="Price / Credit" value={`₹${(listing.price_per_credit / 100).toFixed(2)}`} />
            <InfoRow label="Currency" value={listing.currency} />
            <InfoRow label="Token ID" value={listing.carbon_token_id} />
          </GlassCard>

          {/* Orders */}
          <GlassCard style={styles.card} opacity={0.96}>
            <Text style={styles.sectionTitle}>
              Orders ({orders.length}) — {pendingOrders.length} pending
            </Text>
            {orders.length === 0 ? (
              <View style={styles.emptyOrdersCard}>
                <MaterialCommunityIcons name="account-search-outline" size={32} color="#9e9e9e" />
                <Text style={styles.emptyOrdersTitle}>No buyer interest yet.</Text>
                <Text style={styles.emptyOrdersSub}>
                  Share this listing with buyers. Orders will appear here once submitted.
                </Text>
              </View>
            ) : (
              orders.map(order => (
                <OrderCard
                  key={order.id}
                  order={order}
                  onApprove={() => handleApprove(order.id)}
                  onReject={() => handleReject(order.id)}
                  onMarkPaid={() => handleMarkPaid(order.id, order.buyer_name)}
                  onRetire={() => handleRetire(order.id)}
                  markingPaid={markingPaid === order.id}
                />
              ))
            )}
          </GlassCard>

          {/* Actions */}
          {listing.listing_status === 'ACTIVE' && (
            <AppButton
              label="Cancel Listing"
              onPress={handleCancel}
              style={styles.cancelBtn}
              mode="outlined"
            />
          )}
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { padding: 16, paddingBottom: 40 },
  card: { marginBottom: 16, padding: 16 },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: '#1b2e1b', marginBottom: 10 },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
  infoLabel: { fontSize: 13, color: '#444' },
  infoValue: { fontSize: 13, fontWeight: '600', color: '#111' },
  emptyOrdersCard: { alignItems: 'center', paddingVertical: 20, gap: 8 },
  emptyOrdersTitle: { fontSize: 15, fontWeight: '700', color: '#444' },
  emptyOrdersSub: { fontSize: 13, color: '#777', textAlign: 'center' },
  orderCard: { marginBottom: 10, padding: 12, borderWidth: 1, borderColor: '#d4e8d4' },
  orderHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  orderBuyer: { fontSize: 14, fontWeight: '600', color: '#1b2e1b' },
  orderOrg: { fontSize: 12, color: '#666', marginBottom: 4 },
  orderMeta: { flexDirection: 'row', gap: 16, marginBottom: 8 },
  orderCredits: { fontSize: 13, color: '#2e7d32', fontWeight: '600' },
  orderAmount: { fontSize: 13, color: '#1565c0', fontWeight: '600' },
  orderActions: { flexDirection: 'row', gap: 8 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 6 },
  approveBtn: { backgroundColor: '#2e7d32' },
  rejectBtn: { backgroundColor: '#c62828' },
  retireBtn: { backgroundColor: '#37474f' },
  markPaidBtn: { backgroundColor: '#00695c' },
  actionBtnDisabled: { opacity: 0.6 },
  actionBtnTxt: { color: '#fff', fontSize: 13, fontWeight: '600' },
  cancelBtn: { borderColor: '#c62828' },
});
