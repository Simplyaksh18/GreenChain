/**
 * MarketplaceBrowseScreen — Phase 22B buyer flow.
 *
 * Lists active carbon-credit listings across all FPOs so an authenticated
 * user (buyer) can pick one to purchase. Reuses GlassCard/EmptyState/
 * LoadingView/ErrorView. Refresh-to-refetch.
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

import { browseActiveListings, type MarketplaceListing } from '../../api/marketplaceApi';
import { GlassCard } from '../../components/GlassCard';
import { EmptyState } from '../../components/EmptyState';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { StatusBadge } from '../../components/StatusBadge';
import { RoleBackground } from '../../components/RoleBackground';
import { SectionHeader } from '../../components/SectionHeader';
import type { BuyerMarketplaceStackParamList } from '../../navigation/BuyerMarketplaceStack';

type Props = NativeStackScreenProps<BuyerMarketplaceStackParamList, 'BuyerMarketplaceBrowse'>;

function paiseToRupees(paise: number): string {
  return (paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function ListingCard({
  listing,
  onPress,
}: {
  listing: MarketplaceListing;
  onPress: () => void;
}) {
  const totalRs = paiseToRupees(listing.credits_available * listing.price_per_credit);
  const unitRs = paiseToRupees(listing.price_per_credit);
  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.85}>
      <GlassCard style={styles.card}>
        <View style={styles.cardHeader}>
          <Text variant="labelLarge" style={styles.listingId}>Listing #{listing.id}</Text>
          <StatusBadge status={listing.listing_status} />
        </View>
        <View style={styles.row}>
          <MaterialCommunityIcons name="leaf" size={16} color="#2e7d32" />
          <Text style={styles.rowText}>
            {listing.credits_available} of {listing.credits_listed} credits available
          </Text>
        </View>
        <View style={styles.row}>
          <MaterialCommunityIcons name="currency-inr" size={16} color="#1565c0" />
          <Text style={styles.rowText}>₹{unitRs} per credit · total ₹{totalRs}</Text>
        </View>
        <View style={styles.row}>
          <MaterialCommunityIcons name="account-group-outline" size={16} color="#555" />
          <Text style={styles.rowText}>Seller FPO #{listing.fpo_id}</Text>
        </View>
        <View style={styles.ctaRow}>
          <Text style={styles.ctaText}>View details</Text>
          <MaterialCommunityIcons name="chevron-right" size={18} color="#2e7d32" />
        </View>
      </GlassCard>
    </TouchableOpacity>
  );
}

export function MarketplaceBrowseScreen({ navigation }: Props) {
  const [listings, setListings] = useState<MarketplaceListing[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const fetchListings = useCallback(async (silent = false) => {
    try {
      if (!silent) setError('');
      const data = await browseActiveListings();
      // Belt-and-braces: only show ACTIVE (backend already filters non-FPO/non-admin,
      // but this makes the buyer screen robust to future backend changes).
      setListings(data.filter((l) => l.listing_status === 'ACTIVE'));
    } catch (e: any) {
      if (!silent) setError(e?.response?.data?.detail ?? 'Failed to load marketplace listings');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchListings();
  }, [fetchListings]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchListings(true);
  };

  if (loading) return <LoadingView message="Loading marketplace…" />;
  if (error) return <ErrorView message={error} onRetry={() => { setLoading(true); fetchListings(); }} />;

  return (
    <RoleBackground role="FARMER">
      <SafeAreaView style={{ flex: 1 }} edges={['bottom']}>
        <SectionHeader icon="storefront-outline" title="Carbon Credit Marketplace" />
        <FlatList
          data={listings}
          keyExtractor={(l) => String(l.id)}
          contentContainerStyle={listings.length === 0 ? styles.emptyContent : styles.listContent}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          ListEmptyComponent={
            <EmptyState
              icon="storefront-outline"
              title="No active listings"
              message="Check back later — FPOs list credits as they become available."
            />
          }
          renderItem={({ item }) => (
            <ListingCard
              listing={item}
              onPress={() =>
                navigation.navigate('BuyerMarketplaceListingDetail', { listingId: item.id })
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
  card: { padding: 14, gap: 8 },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  listingId: { color: '#1b5e20', fontWeight: '700' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rowText: { fontSize: 13, color: '#333' },
  ctaRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    alignItems: 'center',
    marginTop: 6,
  },
  ctaText: { color: '#2e7d32', fontWeight: '600', fontSize: 13, marginRight: 2 },
});
