/**
 * FPOListingsScreen — Phase 16
 * FPO views and manages their active marketplace listings.
 * Navigate → CreateListingScreen to add new, ListingDetailScreen for orders.
 */
import React, { useCallback, useState } from 'react';
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
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getFPOListings, type MarketplaceListing } from '../../api/marketplaceApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { StatusBadge } from '../../components/StatusBadge';
import { AppButton } from '../../components/AppButton';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';

export type FPOMarketplaceStackParamList = {
  FPOListings: undefined;
  FPOCreateListing: undefined;
  FPOListingDetail: { listingId: number };
  FPOBuyerOrders: { listingId: number; listingCredits: number };
  FPORetirementCertificate: { orderId: number };
};

type Props = NativeStackScreenProps<FPOMarketplaceStackParamList, 'FPOListings'>;

function ListingCard({
  listing,
  onPress,
}: {
  listing: MarketplaceListing;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.8}>
      <GlassCard style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={styles.cardLeft}>
            <MaterialCommunityIcons name="leaf" size={20} color="#2e7d32" />
            <Text style={styles.cardTitle}>Listing #{listing.id}</Text>
          </View>
          <StatusBadge status={listing.listing_status} />
        </View>
        <View style={styles.cardBody}>
          <View style={styles.metric}>
            <Text style={styles.metricVal}>{listing.credits_available}</Text>
            <Text style={styles.metricLbl}>Credits Available</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricVal}>{listing.credits_listed}</Text>
            <Text style={styles.metricLbl}>Total Listed</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricVal}>
              ₹{(listing.price_per_credit / 100).toFixed(0)}
            </Text>
            <Text style={styles.metricLbl}>Per Credit</Text>
          </View>
        </View>
        <View style={styles.cardFooter}>
          <MaterialCommunityIcons name="chevron-right" size={18} color="#888" />
          <Text style={styles.footerTxt}>Tap to manage orders</Text>
        </View>
      </GlassCard>
    </TouchableOpacity>
  );
}

export function FPOListingsScreen({ navigation }: Props) {
  const [listings, setListings] = useState<MarketplaceListing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async (silent = false) => {
    try {
      if (!silent) setError('');
      const data = await getFPOListings();
      setListings(data);
    } catch (e: any) {
      if (!silent) setError(e?.response?.data?.detail ?? 'Failed to load listings');
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

  if (loading) return <LoadingView message="Loading listings…" />;
  if (error) return <ErrorView message={error} onRetry={() => fetchData()} />;

  const active = listings.filter(l => l.listing_status === 'ACTIVE');

  return (
    <RoleBackground role="FPO">
      <SafeAreaView style={styles.safe}>
        <FlatList
          data={listings}
          keyExtractor={item => String(item.id)}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchData(true); }} />
          }
          ListHeaderComponent={
            <View>
              {/* Title — white text on dark background */}
              <SectionHeader icon="tag-outline" title="My Marketplace Listings" light />

              {/* Explanation card — solid white, dark text */}
              <GlassCard style={styles.explainCard} opacity={0.96}>
                <View style={styles.explainRow}>
                  <MaterialCommunityIcons name="information-outline" size={18} color="#1565c0" />
                  <Text style={styles.explainText}>
                    Marketplace lets your FPO list verified carbon credits for buyers.
                    Credits must be tokenized and available before listing.
                  </Text>
                </View>
              </GlassCard>

              {/* Stats — inside a solid card so numbers are readable */}
              <GlassCard style={styles.statsCard} opacity={0.96}>
                <View style={styles.statsRow}>
                  <View style={styles.stat}>
                    <Text style={styles.statVal}>{active.length}</Text>
                    <Text style={styles.statLbl}>Active Listings</Text>
                  </View>
                  <View style={styles.statDivider} />
                  <View style={styles.stat}>
                    <Text style={styles.statVal}>{listings.length}</Text>
                    <Text style={styles.statLbl}>Total Listings</Text>
                  </View>
                  <View style={styles.statDivider} />
                  <View style={styles.stat}>
                    <Text style={styles.statVal}>
                      {active.reduce((s, l) => s + l.credits_available, 0)}
                    </Text>
                    <Text style={styles.statLbl}>Credits for Sale</Text>
                  </View>
                </View>
              </GlassCard>

              <AppButton
                label="+ Create New Listing"
                onPress={() => navigation.navigate('FPOCreateListing')}
                style={styles.createBtn}
              />
            </View>
          }
          ListEmptyComponent={
            <GlassCard style={styles.emptyCard} opacity={0.96}>
              <MaterialCommunityIcons name="tag-outline" size={44} color="#9e9e9e" style={styles.emptyIcon} />
              <Text style={styles.emptyTitle}>No active listings yet</Text>
              <Text style={styles.emptySub}>
                Verified and tokenized credits with available balance can be listed for buyers.
              </Text>
            </GlassCard>
          }
          renderItem={({ item }) => (
            <ListingCard
              listing={item}
              onPress={() =>
                navigation.navigate('FPOListingDetail', { listingId: item.id })
              }
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

  explainCard: { marginBottom: 10, padding: 12 },
  explainRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  explainText: { flex: 1, fontSize: 12, color: '#1b3a6b', lineHeight: 18 },

  statsCard: { marginBottom: 10, padding: 14 },
  statsRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  stat: { alignItems: 'center', flex: 1 },
  statVal: { fontSize: 22, fontWeight: '800', color: '#1a3a1a' },
  statLbl: { fontSize: 11, color: '#333', textAlign: 'center', marginTop: 2 },
  statDivider: { width: 1, height: 32, backgroundColor: '#e0e0e0' },
  createBtn: { marginBottom: 16 },

  emptyCard: { alignItems: 'center', padding: 28, marginTop: 8 },
  emptyIcon: { marginBottom: 12 },
  emptyTitle: { fontSize: 16, fontWeight: '700', color: '#333', marginBottom: 8, textAlign: 'center' },
  emptySub: { fontSize: 13, color: '#666', textAlign: 'center', lineHeight: 19 },
  card: { marginBottom: 12, padding: 14 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  cardLeft: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  cardTitle: { fontSize: 15, fontWeight: '600', color: '#1b2e1b' },
  cardBody: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 8 },
  metric: { alignItems: 'center' },
  metricVal: { fontSize: 18, fontWeight: '700', color: '#2e7d32' },
  metricLbl: { fontSize: 11, color: '#666' },
  cardFooter: { flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', gap: 4 },
  footerTxt: { fontSize: 12, color: '#888' },
});
