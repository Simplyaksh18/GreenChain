/**
 * MyFarmsScreen — Phase 9B
 * GET /farms?limit=20&offset=0  (role-aware: returns only this farmer's farms)
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  FlatList,
  StyleSheet,
  TouchableOpacity,
  View,
  RefreshControl,
} from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getFarmsApi } from '../../api/farmApi';
import { RoleBackground } from '../../components/RoleBackground';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { StatusBadge } from '../../components/StatusBadge';
import type { Farm } from '../../types';
import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'MyFarms'>;

export function MyFarmsScreen({ navigation }: Props) {
  // Add "+" button to header
  React.useLayoutEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <TouchableOpacity
          onPress={() => navigation.navigate('AddFarm')}
          style={{ marginRight: 4, padding: 4 }}
        >
          <MaterialCommunityIcons name="plus-circle-outline" size={28} color="#fff" />
        </TouchableOpacity>
      ),
    });
  }, [navigation]);
  const [farms, setFarms]       = useState<Farm[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [offset, setOffset]     = useState(0);
  const [hasMore, setHasMore]   = useState(true);
  const LIMIT = 20;

  const loadFarms = useCallback(async (reset = false) => {
    const currentOffset = reset ? 0 : offset;
    try {
      setError('');
      // value from GET /farms
      const data = await getFarmsApi({ limit: LIMIT, offset: currentOffset });
      if (reset) {
        setFarms(data);
        setOffset(data.length);
      } else {
        setFarms((prev) => [...prev, ...data]);
        setOffset(currentOffset + data.length);
      }
      setHasMore(data.length === LIMIT);
    } catch {
      setError('Failed to load farms. Pull to retry.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [offset]);

  useEffect(() => { loadFarms(true); }, []); // eslint-disable-line

  const onRefresh = () => { setRefreshing(true); loadFarms(true); };

  if (loading) return <LoadingView message="Loading your farms…" />;
  if (error)   return <ErrorView message={error} onRetry={() => loadFarms(true)} />;

  const renderFarm = ({ item }: { item: Farm }) => (
    <TouchableOpacity
      style={styles.farmCard}
      onPress={() => navigation.navigate('FarmDetail', { farmId: item.id, farmName: item.farm_name })}
      activeOpacity={0.82}
    >
      <View style={styles.farmRow}>
        <View style={styles.farmIcon}>
          <MaterialCommunityIcons name="sprout" size={24} color="#2e7d32" />
        </View>
        <View style={styles.farmInfo}>
          <Text variant="titleSmall" style={styles.farmName} numberOfLines={1}>
            {item.farm_name}
          </Text>
          <Text variant="bodySmall" style={styles.farmLocation}>
            {item.village}, {item.district}, {item.state}
          </Text>
          <View style={styles.farmMeta}>
            <Text variant="labelSmall" style={styles.acreage}>
              {item.land_area_acres.toFixed(1)} acres · {item.soil_type}
            </Text>
          </View>
        </View>
        <View style={styles.farmRight}>
          <StatusBadge status={item.is_approved ? 'APPROVED' : 'PENDING'} />
          <MaterialCommunityIcons name="chevron-right" size={20} color="#bbb" style={styles.chevron} />
        </View>
      </View>
    </TouchableOpacity>
  );

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        {farms.length === 0 ? (
          <View style={styles.emptyCenter}>
            <View style={styles.emptyCard}>
              <MaterialCommunityIcons name="map-marker-off-outline" size={48} color="#9e9e9e" />
              <Text variant="titleMedium" style={styles.emptyTitle}>No Farms Yet</Text>
              <Text variant="bodyMedium" style={styles.emptyMsg}>
                Register your first farm to begin tracking carbon credits.
              </Text>
              <TouchableOpacity
                style={styles.emptyAddBtn}
                onPress={() => navigation.navigate('AddFarm')}
                activeOpacity={0.8}
              >
                <MaterialCommunityIcons name="plus" size={20} color="#fff" />
                <Text style={styles.emptyAddText}>Add Farm</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <FlatList
            data={farms}
            keyExtractor={(f) => String(f.id)}
            renderItem={renderFarm}
            contentContainerStyle={styles.list}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={onRefresh}
                tintColor="#fff"
                colors={['#66bb6a']}
              />
            }
            onEndReached={() => { if (hasMore && !loading) loadFarms(); }}
            onEndReachedThreshold={0.3}
            ListHeaderComponent={
              <Text variant="bodySmall" style={styles.listHeader}>
                {farms.length} farm{farms.length !== 1 ? 's' : ''} registered
              </Text>
            }
          />
        )}
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },

  list: { padding: 16, paddingBottom: 32 },
  listHeader: { color: 'rgba(255,255,255,0.7)', marginBottom: 12, textAlign: 'center' },

  farmCard: {
    backgroundColor: 'rgba(255,255,255,0.88)',
    borderRadius: 16,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.4)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 6,
    elevation: 3,
  },
  farmRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  farmIcon: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: '#e8f5e9',
    alignItems: 'center', justifyContent: 'center',
  },
  farmInfo: { flex: 1 },
  farmName: { fontWeight: '700', color: '#1b5e20', marginBottom: 2 },
  farmLocation: { color: '#555', marginBottom: 4 },
  farmMeta: { flexDirection: 'row' },
  acreage: { color: '#888' },
  farmRight: { alignItems: 'flex-end', gap: 4 },
  chevron: { marginTop: 4 },

  // Empty state
  emptyCenter: { flex: 1, justifyContent: 'center', padding: 24 },
  emptyCard: {
    backgroundColor: 'rgba(255,255,255,0.88)',
    borderRadius: 20, padding: 28, alignItems: 'center', gap: 12,
  },
  emptyTitle: { fontWeight: '800', color: '#555' },
  emptyMsg: { textAlign: 'center', color: '#777', lineHeight: 22 },
  emptyAddBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#2e7d32', borderRadius: 24,
    paddingHorizontal: 20, paddingVertical: 10, marginTop: 4,
  },
  emptyAddText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
