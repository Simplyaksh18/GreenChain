/**
 * PublicRegistryScreen — Phase 16
 * Public read-only view of the GreenChain carbon credit registry.
 * No authentication required — shows verified reports and minted tokens.
 *
 * Privacy: only safe public fields shown (no PII, no wallet addresses).
 */
import React, { useCallback, useState } from 'react';
import {
  FlatList,
  RefreshControl,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';

import {
  getPublicReports,
  type PublicReport,
  type RegistryFilters,
} from '../api/marketplaceApi';
import { RoleBackground } from '../components/RoleBackground';
import { GlassCard } from '../components/GlassCard';
import { SectionHeader } from '../components/SectionHeader';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingView } from '../components/LoadingView';
import { ErrorView } from '../components/ErrorView';
import { EmptyState } from '../components/EmptyState';

function ReportCard({ report }: { report: PublicReport }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <TouchableOpacity onPress={() => setExpanded(e => !e)} activeOpacity={0.85}>
      <GlassCard style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={styles.cardLeft}>
            <MaterialCommunityIcons name="leaf" size={18} color="#2e7d32" />
            <Text style={styles.farmName} numberOfLines={1}>
              {report.farm_name ?? `Farm #${report.farm_id}`}
            </Text>
          </View>
          <StatusBadge status={report.verification_status ?? report.report_status} />
        </View>

        <View style={styles.locationRow}>
          <MaterialCommunityIcons name="map-marker" size={13} color="#888" />
          <Text style={styles.location}>
            {[report.district, report.state].filter(Boolean).join(', ') || 'Location not available'}
          </Text>
        </View>

        <View style={styles.metricsRow}>
          <View style={styles.metric}>
            <Text style={styles.metricVal}>{report.estimated_credits}</Text>
            <Text style={styles.metricLbl}>Credits</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricVal}>{report.verified_co2e_tonnes.toFixed(2)}</Text>
            <Text style={styles.metricLbl}>tCO₂e</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricVal}>{report.evidence_count}</Text>
            <Text style={styles.metricLbl}>Evidence</Text>
          </View>
        </View>

        {expanded && (
          <View style={styles.expandSection}>
            {report.crop_type && (
              <Text style={styles.expandRow}>
                <Text style={styles.expandLabel}>Crop: </Text>{report.crop_type}
                {report.season ? ` (${report.season})` : ''}
              </Text>
            )}
            {report.fpo_name && (
              <Text style={styles.expandRow}>
                <Text style={styles.expandLabel}>FPO: </Text>{report.fpo_name}
              </Text>
            )}
            {report.baseline_method && (
              <Text style={styles.expandRow}>
                <Text style={styles.expandLabel}>Method: </Text>{report.baseline_method}
              </Text>
            )}
            {report.reduction_practice && (
              <Text style={styles.expandRow}>
                <Text style={styles.expandLabel}>Practice: </Text>{report.reduction_practice}
              </Text>
            )}
            {report.report_hash_short && (
              <Text style={styles.expandRow}>
                <Text style={styles.expandLabel}>Report Hash: </Text>
                <Text style={styles.hashText}>{report.report_hash_short}</Text>
              </Text>
            )}
            {report.created_at && (
              <Text style={styles.expandRow}>
                <Text style={styles.expandLabel}>Date: </Text>
                {new Date(report.created_at).toLocaleDateString()}
              </Text>
            )}
          </View>
        )}

        <View style={styles.expandHint}>
          <MaterialCommunityIcons
            name={expanded ? 'chevron-up' : 'chevron-down'}
            size={16}
            color="#aaa"
          />
        </View>
      </GlassCard>
    </TouchableOpacity>
  );
}

export function PublicRegistryScreen() {
  const [reports, setReports] = useState<PublicReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<RegistryFilters>({ limit: 50 });

  const fetchData = useCallback(async (silent = false) => {
    try {
      if (!silent) setError('');
      const data = await getPublicReports(filters);
      setReports(data);
    } catch (e: any) {
      if (!silent) setError(e?.response?.data?.detail ?? 'Failed to load registry');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filters]);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      fetchData();
    }, [fetchData])
  );

  const handleSearch = () => {
    setFilters(prev => ({
      ...prev,
      state: search.trim() || undefined,
      district: search.trim() || undefined,
    }));
  };

  const handleClear = () => {
    setSearch('');
    setFilters({ limit: 50 });
  };

  const filtered = search.trim()
    ? reports.filter(r =>
        (r.state ?? '').toLowerCase().includes(search.toLowerCase()) ||
        (r.district ?? '').toLowerCase().includes(search.toLowerCase()) ||
        (r.farm_name ?? '').toLowerCase().includes(search.toLowerCase()) ||
        (r.fpo_name ?? '').toLowerCase().includes(search.toLowerCase()) ||
        (r.crop_type ?? '').toLowerCase().includes(search.toLowerCase())
      )
    : reports;

  if (loading) return <LoadingView message="Loading public registry…" />;
  if (error) return <ErrorView message={error} onRetry={() => fetchData()} />;

  const totalCredits = reports.reduce((s, r) => s + r.estimated_credits, 0);
  const totalCo2e = reports.reduce((s, r) => s + r.verified_co2e_tonnes, 0);

  return (
    <RoleBackground role="FARMER">
      <SafeAreaView style={styles.safe}>
        <FlatList
          data={filtered}
          keyExtractor={item => String(item.id)}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { setRefreshing(true); fetchData(true); }}
            />
          }
          ListHeaderComponent={
            <View>
              <SectionHeader icon="earth" title="Public Carbon Registry" />

              {/* Registry summary */}
              <GlassCard style={styles.summaryCard}>
                <View style={styles.summaryRow}>
                  <View style={styles.summaryItem}>
                    <MaterialCommunityIcons name="file-check" size={22} color="#2e7d32" />
                    <Text style={styles.summaryVal}>{reports.length}</Text>
                    <Text style={styles.summaryLbl}>Reports</Text>
                  </View>
                  <View style={styles.summaryItem}>
                    <MaterialCommunityIcons name="leaf" size={22} color="#1565c0" />
                    <Text style={styles.summaryVal}>{totalCredits}</Text>
                    <Text style={styles.summaryLbl}>Credits</Text>
                  </View>
                  <View style={styles.summaryItem}>
                    <MaterialCommunityIcons name="molecule-co2" size={22} color="#37474f" />
                    <Text style={styles.summaryVal}>{totalCo2e.toFixed(1)}</Text>
                    <Text style={styles.summaryLbl}>tCO₂e</Text>
                  </View>
                </View>
              </GlassCard>

              {/* Search bar */}
              <View style={styles.searchRow}>
                <TextInput
                  style={styles.searchInput}
                  placeholder="Search by state, district, farm, crop…"
                  value={search}
                  onChangeText={setSearch}
                  returnKeyType="search"
                  onSubmitEditing={handleSearch}
                />
                {search.length > 0 && (
                  <TouchableOpacity style={styles.clearBtn} onPress={handleClear}>
                    <MaterialCommunityIcons name="close-circle" size={20} color="#aaa" />
                  </TouchableOpacity>
                )}
              </View>

              {filtered.length !== reports.length && (
                <Text style={styles.filterNote}>
                  Showing {filtered.length} of {reports.length} reports
                </Text>
              )}
            </View>
          }
          ListEmptyComponent={
            <EmptyState
              icon="database-search"
              title="No verified reports found"
              message="The public registry shows only VERIFIED or SUBMITTED reports."
            />
          }
          renderItem={({ item }) => <ReportCard report={item} />}
          contentContainerStyle={styles.list}
        />
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  list: { paddingBottom: 32, paddingHorizontal: 16 },
  summaryCard: { marginBottom: 12, padding: 14 },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-around' },
  summaryItem: { alignItems: 'center', gap: 2 },
  summaryVal: { fontSize: 20, fontWeight: '800', color: '#1b2e1b' },
  summaryLbl: { fontSize: 11, color: '#555' },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#c8e6c9',
    marginBottom: 8,
    paddingHorizontal: 12,
  },
  searchInput: { flex: 1, height: 42, fontSize: 14, color: '#1b2e1b' },
  clearBtn: { padding: 4 },
  filterNote: { fontSize: 12, color: '#888', marginBottom: 8, textAlign: 'center' },
  card: { marginBottom: 10, padding: 14 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 },
  cardLeft: { flexDirection: 'row', alignItems: 'center', gap: 6, flex: 1 },
  farmName: { fontSize: 14, fontWeight: '700', color: '#1b2e1b', flex: 1 },
  locationRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 8 },
  location: { fontSize: 12, color: '#888' },
  metricsRow: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 4 },
  metric: { alignItems: 'center' },
  metricVal: { fontSize: 17, fontWeight: '700', color: '#2e7d32' },
  metricLbl: { fontSize: 11, color: '#666' },
  expandSection: { marginTop: 10, paddingTop: 10, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: '#e0e0e0' },
  expandRow: { fontSize: 13, color: '#444', marginBottom: 4, lineHeight: 18 },
  expandLabel: { fontWeight: '600', color: '#2e7d32' },
  hashText: { fontFamily: 'monospace', fontSize: 12 },
  expandHint: { alignItems: 'center', marginTop: 4 },
});
