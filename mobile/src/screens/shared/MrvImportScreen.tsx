/**
 * MrvImportScreen — Phase 14 MRV Import Center
 *
 * Allows Farmer and FPO to import real-world MRV data:
 *   1. Sensor CSV
 *   2. Satellite CSV
 *   3. Drone CSV
 *   4. Farm Boundary GeoJSON
 *   5. Satellite GeoJSON
 *
 * Uses expo-document-picker to select files from the device.
 * Sends multipart POST to the backend import endpoints.
 * Shows import summary (rows received/inserted/skipped/invalid).
 *
 * Navigation params: farmId, farmName, cropCycleId?
 */
import React, { useState } from 'react';
import {
  Alert,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { Text, Button, Divider } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import * as DocumentPicker from 'expo-document-picker';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import {
  importSensorCsv,
  importSatelliteCsv,
  importDroneCsv,
  importFarmBoundaryGeoJson,
  importSatelliteGeoJson,
  type MrvImportResult,
  type BoundaryImportResult,
} from '../../api/auditApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';

export type MrvImportParams = {
  farmId: number;
  farmName: string;
  cropCycleId?: number;
};

type ImportType =
  | 'sensor-csv'
  | 'satellite-csv'
  | 'drone-csv'
  | 'boundary-geojson'
  | 'satellite-geojson';

interface ImportOption {
  type: ImportType;
  label: string;
  description: string;
  icon: string;
  color: string;
  needsCycle: boolean;
  acceptedTypes: string[];
  csvExample: string;
}

const IMPORT_OPTIONS: ImportOption[] = [
  {
    type: 'sensor-csv',
    label: 'Sensor CSV',
    description: 'Import sensor readings: date, temperature_c, soil_moisture, water_depth_cm',
    icon: 'thermometer',
    color: '#1565c0',
    needsCycle: true,
    acceptedTypes: ['text/csv', 'text/comma-separated-values', '*/*'],
    csvExample: 'date,temperature_c,soil_moisture,water_depth_cm',
  },
  {
    type: 'satellite-csv',
    label: 'Satellite CSV',
    description: 'Import satellite observations: date, ndvi, ndwi, cloud_cover_percent, source',
    icon: 'satellite-variant',
    color: '#4a148c',
    needsCycle: true,
    acceptedTypes: ['text/csv', '*/*'],
    csvExample: 'date,ndvi,ndwi,cloud_cover_percent,source',
  },
  {
    type: 'drone-csv',
    label: 'Drone CSV',
    description: 'Import drone observations: date, vegetation_cover_percent, standing_water_percent, anomaly_score',
    icon: 'quadcopter',
    color: '#1b5e20',
    needsCycle: true,
    acceptedTypes: ['text/csv', '*/*'],
    csvExample: 'date,vegetation_cover_percent,standing_water_percent,anomaly_score',
  },
  {
    type: 'boundary-geojson',
    label: 'Farm Boundary GeoJSON',
    description: 'Import farm boundary as GeoJSON Polygon or FeatureCollection',
    icon: 'map-marker-radius',
    color: '#e65100',
    needsCycle: false,
    acceptedTypes: ['application/json', 'application/geo+json', '*/*'],
    csvExample: '',
  },
  {
    type: 'satellite-geojson',
    label: 'Satellite GeoJSON',
    description: 'Import satellite scene summaries from GeoJSON FeatureCollection',
    icon: 'map-search',
    color: '#880e4f',
    needsCycle: true,
    acceptedTypes: ['application/json', 'application/geo+json', '*/*'],
    csvExample: '',
  },
];

interface ImportResultDisplay {
  type: ImportType;
  label: string;
  result: MrvImportResult | BoundaryImportResult | null;
  error: string | null;
}

type Props = NativeStackScreenProps<any, any>;

export function MrvImportScreen({ route }: Props) {
  const { farmId, farmName, cropCycleId } = route.params as MrvImportParams;

  const [loading, setLoading]   = useState<ImportType | null>(null);
  const [results, setResults]   = useState<ImportResultDisplay[]>([]);

  const _isMrvResult = (r: any): r is MrvImportResult => 'rows_inserted' in r;

  async function handleImport(opt: ImportOption) {
    if (opt.needsCycle && !cropCycleId) {
      Alert.alert(
        'Crop cycle required',
        'This import type requires a linked crop cycle. Navigate to a crop cycle first.',
      );
      return;
    }

    const result = await DocumentPicker.getDocumentAsync({
      type: opt.acceptedTypes,
      copyToCacheDirectory: true,
    });
    if (result.canceled || result.assets.length === 0) return;

    const asset = result.assets[0];
    setLoading(opt.type);

    try {
      let importResult: MrvImportResult | BoundaryImportResult;
      switch (opt.type) {
        case 'sensor-csv':
          importResult = await importSensorCsv(farmId, cropCycleId!, asset.uri, asset.name);
          break;
        case 'satellite-csv':
          importResult = await importSatelliteCsv(farmId, cropCycleId!, asset.uri, asset.name);
          break;
        case 'drone-csv':
          importResult = await importDroneCsv(farmId, cropCycleId!, asset.uri, asset.name);
          break;
        case 'boundary-geojson':
          importResult = await importFarmBoundaryGeoJson(farmId, asset.uri, asset.name);
          break;
        case 'satellite-geojson':
          importResult = await importSatelliteGeoJson(farmId, cropCycleId!, asset.uri, asset.name);
          break;
      }
      setResults((prev) => [
        { type: opt.type, label: opt.label, result: importResult, error: null },
        ...prev.filter((r) => r.type !== opt.type),
      ]);
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err?.message ?? 'Import failed';
      setResults((prev) => [
        { type: opt.type, label: opt.label, result: null, error: msg },
        ...prev.filter((r) => r.type !== opt.type),
      ]);
    } finally {
      setLoading(null);
    }
  }

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <ScrollView contentContainerStyle={styles.scroll}>
          <SectionHeader icon="database-import-outline" title="MRV Import Center" light />

          <GlassCard opacity={0.85} style={styles.infoCard}>
            <View style={styles.infoRow}>
              <MaterialCommunityIcons name="information-outline" size={16} color="#1565c0" />
              <Text variant="bodySmall" style={styles.infoText}>
                Import real-world MRV data from CSV or GeoJSON files.
                Farm: <Text style={{ fontWeight: '700' }}>{farmName}</Text>
                {cropCycleId ? `  •  Cycle #${cropCycleId}` : '  •  No cycle selected'}
              </Text>
            </View>
          </GlassCard>

          {/* Import options */}
          {IMPORT_OPTIONS.map((opt) => (
            <GlassCard key={opt.type} opacity={0.92} style={styles.card}>
              <View style={styles.optHeader}>
                <MaterialCommunityIcons name={opt.icon as any} size={26} color={opt.color} />
                <View style={styles.optText}>
                  <Text variant="titleSmall" style={[styles.optLabel, { color: opt.color }]}>
                    {opt.label}
                  </Text>
                  <Text variant="bodySmall" style={styles.optDesc}>{opt.description}</Text>
                  {opt.csvExample ? (
                    <Text variant="bodySmall" style={styles.csvExample}>{opt.csvExample}</Text>
                  ) : null}
                </View>
              </View>
              <Button
                mode="outlined"
                compact
                loading={loading === opt.type}
                disabled={loading !== null}
                onPress={() => handleImport(opt)}
                icon="upload"
                style={[styles.importBtn, { borderColor: opt.color }]}
                labelStyle={{ color: opt.color }}
              >
                Select & Import
              </Button>
            </GlassCard>
          ))}

          {/* Results */}
          {results.length > 0 && (
            <>
              <Text variant="titleSmall" style={styles.resultsHeader}>Import Results</Text>
              {results.map((r) => (
                <GlassCard key={r.type} opacity={0.90} style={styles.card}>
                  <Text variant="labelMedium" style={styles.resultLabel}>{r.label}</Text>
                  <Divider style={{ marginVertical: 6 }} />
                  {r.error ? (
                    <Text style={styles.errorText}>⚠ {r.error}</Text>
                  ) : r.result ? (
                    _isMrvResult(r.result) ? (
                      <MrvResultView result={r.result} />
                    ) : (
                      <BoundaryResultView result={r.result as BoundaryImportResult} />
                    )
                  ) : null}
                </GlassCard>
              ))}
            </>
          )}

          <View style={{ height: 24 }} />
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

function MrvResultView({ result }: { result: MrvImportResult }) {
  return (
    <View style={{ gap: 4 }}>
      <ResultRow icon="database-check" label="Received" value={result.rows_received} color="#333" />
      <ResultRow icon="database-plus"  label="Inserted" value={result.rows_inserted} color="#2e7d32" />
      <ResultRow icon="database-minus" label="Duplicates skipped" value={result.duplicates_skipped} color="#e65100" />
      <ResultRow icon="alert-circle-outline" label="Invalid rows" value={result.invalid_rows} color="#c62828" />
      {result.errors.length > 0 && (
        <View style={{ marginTop: 6 }}>
          <Text variant="labelSmall" style={{ color: '#c62828' }}>Errors:</Text>
          {result.errors.slice(0, 5).map((e, i) => (
            <Text key={i} variant="bodySmall" style={{ color: '#c62828', fontSize: 11 }}>{e}</Text>
          ))}
          {result.errors.length > 5 && (
            <Text variant="bodySmall" style={{ color: '#aaa', fontSize: 11 }}>
              …and {result.errors.length - 5} more
            </Text>
          )}
        </View>
      )}
    </View>
  );
}

function BoundaryResultView({ result }: { result: BoundaryImportResult }) {
  return (
    <View style={{ gap: 4 }}>
      <ResultRow icon="map-check" label="Area (ha)" value={result.boundary_area_hectares.toFixed(2)} color="#2e7d32" />
      <ResultRow icon="map-check" label="Area (acres)" value={result.boundary_area_acres.toFixed(2)} color="#1565c0" />
      <Text variant="bodySmall" style={{ color: '#666', fontSize: 11 }}>
        Hash: {result.file_hash.slice(0, 12)}…
      </Text>
      <Text variant="bodySmall" style={{ color: '#2e7d32' }}>{result.message}</Text>
    </View>
  );
}

function ResultRow({ icon, label, value, color }: {
  icon: string; label: string; value: number | string; color: string;
}) {
  return (
    <View style={styles.resultRow}>
      <MaterialCommunityIcons name={icon as any} size={14} color={color} />
      <Text variant="bodySmall" style={styles.resultKey}>{label}</Text>
      <Text variant="bodySmall" style={[styles.resultVal, { color }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe:         { flex: 1 },
  scroll:       { paddingBottom: 40 },
  infoCard:     { marginHorizontal: 12, marginBottom: 4 },
  infoRow:      { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  infoText:     { flex: 1, color: '#555', lineHeight: 18 },
  card:         { marginBottom: 8 },
  optHeader:    { flexDirection: 'row', gap: 12, alignItems: 'flex-start', marginBottom: 10 },
  optText:      { flex: 1 },
  optLabel:     { fontWeight: '700', marginBottom: 2 },
  optDesc:      { color: '#555', lineHeight: 16 },
  csvExample:   { color: '#1565c0', fontFamily: 'monospace', fontSize: 10, marginTop: 4 },
  importBtn:    { marginTop: 4 },
  resultsHeader:{ paddingHorizontal: 16, paddingVertical: 8, fontWeight: '700', color: '#fff' },
  resultLabel:  { fontWeight: '700', color: '#333' },
  errorText:    { color: '#c62828', fontSize: 12 },
  resultRow:    { flexDirection: 'row', alignItems: 'center', gap: 6 },
  resultKey:    { flex: 1, color: '#555' },
  resultVal:    { fontWeight: '700' },
});
