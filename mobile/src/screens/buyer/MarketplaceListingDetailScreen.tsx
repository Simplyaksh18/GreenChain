/**
 * MarketplaceListingDetailScreen — Phase 22B buyer flow.
 *
 * Full details of a single listing + a quantity input to submit a purchase
 * REQUEST. This is a request, not a payment — the FPO must approve, then
 * a manual/test payment is recorded, then the FPO retires credits.
 * There is no Razorpay Checkout for buyer payment.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Alert, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { apiClient } from '../../api/client';
import { submitOrder, type MarketplaceListing } from '../../api/marketplaceApi';
import { useAuthStore } from '../../store/authStore';
import { GlassCard } from '../../components/GlassCard';
import { InfoRow } from '../../components/InfoRow';
import { AppButton } from '../../components/AppButton';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { StatusBadge } from '../../components/StatusBadge';
import { RoleBackground } from '../../components/RoleBackground';
import { SectionHeader } from '../../components/SectionHeader';
import type { BuyerMarketplaceStackParamList } from '../../navigation/BuyerMarketplaceStack';

type Props = NativeStackScreenProps<BuyerMarketplaceStackParamList, 'BuyerMarketplaceListingDetail'>;

function paiseToRupees(paise: number): string {
  return (paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function MarketplaceListingDetailScreen({ route, navigation }: Props) {
  const { listingId } = route.params;
  const user = useAuthStore((s) => s.user);
  const [listing, setListing] = useState<MarketplaceListing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [quantity, setQuantity] = useState('1');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await apiClient.get(`/marketplace/listings/${listingId}`);
        setListing(data);
      } catch (e: any) {
        setError(e?.response?.data?.detail ?? 'Failed to load listing');
      } finally {
        setLoading(false);
      }
    })();
  }, [listingId]);

  const qtyNum = Number(quantity);
  const isValidQty =
    Number.isFinite(qtyNum) &&
    Number.isInteger(qtyNum) &&
    qtyNum >= 1 &&
    (listing ? qtyNum <= listing.credits_available : false);

  const totalPaise = listing ? qtyNum * listing.price_per_credit : 0;
  const totalRs = useMemo(() => paiseToRupees(totalPaise), [totalPaise]);

  const onSubmit = async () => {
    if (!listing || !isValidQty || submitting) return;
    setSubmitting(true);
    try {
      const order = await submitOrder({
        listing_id: listing.id,
        buyer_name: user?.name ?? 'Buyer',
        buyer_email: user?.email ?? 'unknown@buyer.local',
        credits_requested: qtyNum,
      });
      Alert.alert(
        'Request submitted',
        `Your purchase request for ${order.credits_requested} credits has been sent to the seller FPO for approval.`,
        [{ text: 'View my orders', onPress: () => navigation.navigate('BuyerMyOrders') }],
      );
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? 'Failed to submit purchase request';
      Alert.alert('Could not submit', String(detail));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingView message="Loading listing…" />;
  if (error || !listing) return <ErrorView message={error || 'Listing not found'} onRetry={() => navigation.goBack()} />;

  return (
    <RoleBackground role="FARMER">
      <SafeAreaView style={{ flex: 1 }} edges={['bottom']}>
        <ScrollView contentContainerStyle={styles.scroll}>
          <View style={styles.headerRow}>
            <SectionHeader icon="storefront-outline" title={`Listing #${listing.id}`} />
            <View style={styles.headerBadge}>
              <StatusBadge status={listing.listing_status} />
            </View>
          </View>

          <GlassCard style={styles.card}>
            <InfoRow icon="leaf" label="Credits available" value={String(listing.credits_available)} />
            <InfoRow icon="chart-line" label="Originally listed" value={String(listing.credits_listed)} />
            <InfoRow
              icon="currency-inr"
              label="Price per credit"
              value={`₹${paiseToRupees(listing.price_per_credit)}`}
            />
            <InfoRow icon="identifier" label="Carbon token" value={`#${listing.carbon_token_id}`} last />
          </GlassCard>

          <GlassCard style={styles.card}>
            <Text variant="titleSmall" style={styles.blockTitle}>How many credits?</Text>
            <View style={styles.qtyRow}>
              <TextInput
                style={styles.qtyInput}
                keyboardType="number-pad"
                value={quantity}
                onChangeText={setQuantity}
                editable={!submitting}
              />
              <Text style={styles.qtyMax}>max {listing.credits_available}</Text>
            </View>
            <InfoRow icon="calculator" label="Total" value={`₹${totalRs}`} last />
          </GlassCard>

          <GlassCard style={styles.notice}>
            <View style={styles.noticeRow}>
              <MaterialCommunityIcons name="information-outline" size={18} color="#e65100" />
              <Text style={styles.noticeText}>
                Test marketplace. Payment is recorded manually by the seller FPO
                after they approve your request. No card details are collected.
              </Text>
            </View>
          </GlassCard>

          <View style={styles.submitWrap}>
            <AppButton
              icon="hand-coin-outline"
              mode="contained"
              onPress={onSubmit}
              loading={submitting}
              disabled={!isValidQty || submitting || listing.listing_status !== 'ACTIVE'}
            >
              Submit Purchase Request
            </AppButton>
          </View>
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingBottom: 24 },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerBadge: { marginRight: 16, marginTop: 12 },
  card: { padding: 14, gap: 6 },
  blockTitle: { color: '#1b5e20', fontWeight: '700', marginBottom: 6 },
  qtyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 6,
  },
  qtyInput: {
    borderWidth: 1,
    borderColor: '#c8e6c9',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 16,
    minWidth: 90,
    color: '#1b5e20',
    backgroundColor: '#fff',
  },
  qtyMax: { color: '#616161', fontSize: 12 },
  notice: { padding: 12 },
  noticeRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  noticeText: { flex: 1, color: '#4e342e', fontSize: 12, lineHeight: 18 },
  submitWrap: { paddingHorizontal: 16, marginTop: 12 },
});
