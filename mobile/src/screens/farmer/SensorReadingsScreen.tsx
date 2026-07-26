/**
 * SensorReadingsScreen — Phase 9B
 * GET /sensors/farm/{farm_id}?limit=20&offset=0
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  FlatList,
  StyleSheet,
  View,
  RefreshControl,
} from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getSensorsByFarmApi } from '../../api/sensorApi';
import { RoleBackground } from '../../components/RoleBackground';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import type { SensorReading } from '../../types';
import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'SensorReadings'>;

interface ReadingTile {
  icon: keyof typeof MaterialCommunityIcons.glyphMap;
  label: string;
  value: string;
  color: string;
}

function SensorCard({ reading }: { reading: SensorReading }) {
  const tiles: ReadingTile[] = [
    { icon: 'water-percent',    label: 'Soil Moisture', value: `${reading.soil_moisture.toFixed(1)}%`,             color: '#1565c0' },
    { icon: 'waves',            label: 'Water Depth',   value: `${reading.water_depth_cm.toFixed(1)} cm`,          color: '#0277bd' },
    { icon: 'thermometer',      label: 'Temperature',   value: `${reading.temperature_c.toFixed(1)}°C`,            color: '#e65100' },
    { icon: 'molecule-co2',     label: 'Est. Methane',  value: `${reading.estimated_methane.toFixed(4)} kg/m²`,    color: '#558b2f' },
  ];

  return (
    <View style={styles.readingCard}>
      <View style={styles.readingHeader}>
        <Text variant="labelSmall" style={styles.readingTime}>
          {new Date(reading.reading_time).toLocaleString('en-IN', {
            day: 'numeric', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
          })}
        </Text>
        <View style={[styles.qualityBadge, { backgroundColor: reading.data_quality_score >= 70 ? '#e8f5e9' : '#fff3e0' }]}>
          <Text style={[styles.qualityText, { color: reading.data_quality_score >= 70 ? '#2e7d32' : '#e65100' }]}>
            Q: {reading.data_quality_score.toFixed(0)}
          </Text>
        </View>
      </View>
      <View style={styles.tilesRow}>
        {tiles.map((tile) => (
          <View key={tile.label} style={styles.tile}>
            <MaterialCommunityIcons name={tile.icon} size={20} color={tile.color} />
            <Text variant="labelSmall" style={styles.tileLabel}>{tile.label}</Text>
            <Text variant="bodySmall" style={[styles.tileValue, { color: tile.color }]}>
              {tile.value}
            </Text>
          </View>
        ))}
      </View>
      {reading.humidity !== undefined && (
        <Text variant="labelSmall" style={styles.readingExtra}>
          Humidity: {reading.humidity.toFixed(1)}%  ·  Rainfall: {reading.rainfall_mm.toFixed(1)} mm  ·  Source: {reading.source_type}
        </Text>
      )}
    </View>
  );
}

export function SensorReadingsScreen({ route }: Props) {
  const { farmId, farmName } = route.params;

  const [readings, setReadings]     = useState<SensorReading[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [offset, setOffset]         = useState(0);
  const [hasMore, setHasMore]       = useState(true);
  const LIMIT = 20;

  const load = useCallback(async (reset = false) => {
    const off = reset ? 0 : offset;
    try {
      setError('');
      // value from GET /sensors/farm/{farm_id}
      const raw = await getSensorsByFarmApi(farmId, { limit: LIMIT, offset: off });
      // UI safety: filter out any future-dated readings (backend enforces this too)
      const now = new Date();
      const data = raw.filter((r) => new Date(r.reading_time) <= now);
      if (reset) {
        setReadings(data);
        setOffset(data.length);
      } else {
        setReadings((prev) => [...prev, ...data]);
        setOffset(off + data.length);
      }
      setHasMore(data.length === LIMIT);
    } catch {
      setError('Failed to load sensor readings.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [farmId, offset]);

  useEffect(() => { load(true); }, []); // eslint-disable-line

  const onRefresh = () => { setRefreshing(true); load(true); };

  if (loading) return <LoadingView message="Loading sensor readings…" />;
  if (error)   return <ErrorView message={error} onRetry={() => load(true)} />;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        {readings.length === 0 ? (
          <View style={styles.emptyCenter}>
            <View style={styles.emptyCard}>
              <MaterialCommunityIcons name="access-point-network-off" size={48} color="#9e9e9e" />
              <Text variant="titleMedium" style={styles.emptyTitle}>No Sensor Data</Text>
              <Text variant="bodyMedium" style={styles.emptyMsg}>
                No sensor readings recorded for {farmName} yet.
              </Text>
            </View>
          </View>
        ) : (
          <FlatList
            data={[...readings].reverse()} // newest first
            keyExtractor={(r) => String(r.id)}
            renderItem={({ item }) => <SensorCard reading={item} />}
            contentContainerStyle={styles.list}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={onRefresh}
                tintColor="#fff"
                colors={['#66bb6a']}
              />
            }
            onEndReached={() => { if (hasMore && !loading) load(); }}
            onEndReachedThreshold={0.3}
            ListHeaderComponent={
              <Text variant="bodySmall" style={styles.listHeader}>
                {readings.length} reading{readings.length !== 1 ? 's' : ''} — newest first
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
  list: { padding: 12, paddingBottom: 32 },
  listHeader: { color: 'rgba(255,255,255,0.7)', textAlign: 'center', marginBottom: 10 },

  readingCard: {
    backgroundColor: 'rgba(255,255,255,0.88)',
    borderRadius: 16,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.4)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 6,
    elevation: 2,
  },
  readingHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  readingTime: { color: '#666' },
  qualityBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8 },
  qualityText: { fontSize: 11, fontWeight: '700' },
  tilesRow: { flexDirection: 'row', justifyContent: 'space-between' },
  tile: { alignItems: 'center', flex: 1, gap: 3 },
  tileLabel: { color: '#888', textAlign: 'center' },
  tileValue: { fontWeight: '700', fontSize: 12, textAlign: 'center' },
  readingExtra: { color: '#aaa', marginTop: 8, textAlign: 'center' },

  emptyCenter: { flex: 1, justifyContent: 'center', padding: 24 },
  emptyCard: {
    backgroundColor: 'rgba(255,255,255,0.88)',
    borderRadius: 20, padding: 28, alignItems: 'center', gap: 12,
  },
  emptyTitle: { fontWeight: '800', color: '#555' },
  emptyMsg: { textAlign: 'center', color: '#777', lineHeight: 22 },
});
