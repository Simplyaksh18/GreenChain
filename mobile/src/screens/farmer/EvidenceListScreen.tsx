/**
 * EvidenceListScreen — Phase 13
 *
 * Lists evidence files for a farm. Shows file type, description,
 * hash status, and creation date. Supports basic hash verification.
 *
 * GET /evidence/farm/{farmId}
 * GET /evidence/{id}/verify
 */
import React, { useCallback, useState } from 'react';
import {
  Alert,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { Text, Button, Divider } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import {
  getEvidenceByFarm,
  verifyEvidenceHash,
  type EvidenceFile,
} from '../../api/auditApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import { EmptyState } from '../../components/EmptyState';
// Using `any` because this screen is mounted in both FarmerFarmsStack (EvidenceList)
// and FPOFarmsStack (FPOEvidenceList). route.name is used to pick the correct AddEvidence route.
type Props = NativeStackScreenProps<any, any>;

const FILE_ICONS: Record<string, string> = {
  IMAGE:  'image-outline',
  PDF:    'file-pdf-box',
  VIDEO:  'video-outline',
  CSV:    'file-delimited-outline',
  DOC:    'file-document-outline',
};

function EvidenceCard({
  ev,
  onVerify,
  verifying,
}: {
  ev: EvidenceFile;
  onVerify: (id: number) => void;
  verifying: boolean;
}) {
  const icon = FILE_ICONS[ev.file_type] ?? 'file-outline';
  const dateStr = new Date(ev.created_at).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
  });

  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <MaterialCommunityIcons name={icon as any} size={22} color="#1565c0" />
        <View style={styles.cardTitles}>
          <Text variant="labelMedium" style={styles.fileType}>{ev.file_type}</Text>
          {ev.description && (
            <Text variant="bodySmall" style={styles.desc}>{ev.description}</Text>
          )}
        </View>
        <Text variant="bodySmall" style={styles.date}>{dateStr}</Text>
      </View>

      {ev.file_hash ? (
        <View style={styles.hashRow}>
          <MaterialCommunityIcons name="shield-check-outline" size={14} color="#2e7d32" />
          <Text variant="bodySmall" style={styles.hashText}>
            {ev.file_hash.slice(0, 8)}...{ev.file_hash.slice(-6)}
          </Text>
          <Button
            mode="text"
            compact
            loading={verifying}
            onPress={() => onVerify(ev.id)}
            style={styles.verifyBtn}
            labelStyle={styles.verifyLabel}
          >
            Verify
          </Button>
        </View>
      ) : (
        <View style={styles.hashRow}>
          <MaterialCommunityIcons name="shield-alert-outline" size={14} color="#f57f17" />
          <Text variant="bodySmall" style={styles.noHash}>No hash (uploaded before Phase 13)</Text>
        </View>
      )}

      {ev.carbon_report_id && (
        <Text variant="bodySmall" style={styles.reportTag}>
          Linked to Report #{ev.carbon_report_id}
        </Text>
      )}
    </View>
  );
}

export function EvidenceListScreen({ route, navigation }: Props) {
  const { farmId, farmName } = route.params as { farmId: number; farmName: string };

  // Role-based UI:
  //   FPO stack  (route.name starts with 'FPO') → can add/upload evidence
  //   Farmer stack                               → view only, no Add Evidence button
  //
  // This mirrors the backend rule: POST /evidence returns 403 for FARMER role.
  const isFPOStack = (route.name as string).startsWith('FPO');
  const addEvidenceRoute = isFPOStack ? 'FPOAddEvidence' : 'AddEvidence';

  const [evidence, setEvidence] = useState<EvidenceFile[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [verifyingId, setVerifyingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setError('');
      const ev = await getEvidenceByFarm(farmId);
      setEvidence(ev);
    } catch {
      setError('Failed to load evidence.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [farmId]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const handleVerify = async (evidenceId: number) => {
    try {
      setVerifyingId(evidenceId);
      const result = await verifyEvidenceHash(evidenceId);
      if (result.hash_match) {
        Alert.alert(
          '✅ Hash Verified',
          `Hash matches stored value.\n\nAlgorithm: ${result.hash_algorithm}\nHash: ${result.recomputed_hash.slice(0, 16)}...`,
        );
      } else {
        Alert.alert(
          '⚠️ Hash Mismatch',
          `The recomputed hash does not match the stored hash. Evidence may have been modified.\n\nStored: ${result.stored_hash?.slice(0, 16)}...\nRecomputed: ${result.recomputed_hash.slice(0, 16)}...`,
        );
      }
    } catch {
      Alert.alert('Error', 'Failed to verify hash.');
    } finally {
      setVerifyingId(null);
    }
  };

  const onRefresh = () => { setRefreshing(true); load(); };

  if (loading) return <LoadingView message="Loading evidence…" />;
  if (error)   return <ErrorView message={error} onRetry={load} />;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#fff" />
          }
        >
          <SectionHeader icon="folder-open-outline" title={`Evidence — ${farmName}`} light />

          {/* Add Evidence button — FPO stack only. Farmers are view-only. */}
          {isFPOStack && (
            <View style={styles.addRow}>
              <Button
                mode="contained"
                icon="plus-circle-outline"
                onPress={() => navigation.navigate(addEvidenceRoute, { farmId, farmName })}
                style={styles.addBtn}
                contentStyle={styles.addBtnContent}
                buttonColor="#1565c0"
              >
                Add Evidence
              </Button>
            </View>
          )}

          <GlassCard style={styles.infoCard} opacity={0.88}>
            <View style={styles.infoRow}>
              <MaterialCommunityIcons name="information-outline" size={16} color="#1565c0" />
              <Text variant="bodySmall" style={styles.infoText}>
                Each file is hashed at upload. Tap Verify to confirm the evidence has not been modified.
              </Text>
            </View>
          </GlassCard>

          {evidence.length === 0 ? (
            <EmptyState
              icon="folder-open-outline"
              title="No evidence uploaded"
              message="Evidence is uploaded by the FPO on behalf of the farm."
            />
          ) : (
            <GlassCard opacity={0.92}>
              <Text variant="labelSmall" style={styles.count}>
                {evidence.length} file{evidence.length !== 1 ? 's' : ''}
              </Text>
              <Divider style={styles.divider} />
              {evidence.map((ev, i) => (
                <React.Fragment key={ev.id}>
                  <EvidenceCard
                    ev={ev}
                    onVerify={handleVerify}
                    verifying={verifyingId === ev.id}
                  />
                  {i < evidence.length - 1 && <Divider style={styles.divider} />}
                </React.Fragment>
              ))}
            </GlassCard>
          )}
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe:    { flex: 1 },
  scroll:  { paddingBottom: 40 },
  addRow:  { marginHorizontal: 16, marginBottom: 8 },
  addBtn:  { borderRadius: 10 },
  addBtnContent: { paddingVertical: 2 },
  infoCard:   { marginHorizontal: 12, marginBottom: 4 },
  infoRow:    { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  infoText:   { flex: 1, color: '#1565c0', lineHeight: 18 },
  count:      { color: '#888', marginBottom: 6 },
  divider:    { marginVertical: 8 },
  card: {
    paddingVertical: 4,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    marginBottom: 6,
  },
  cardTitles: { flex: 1 },
  fileType:   { color: '#333', fontWeight: '700' },
  desc:       { color: '#666', marginTop: 2 },
  date:       { color: '#aaa', fontSize: 11 },
  hashRow:    { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  hashText:   { color: '#2e7d32', fontSize: 11, fontFamily: 'monospace', flex: 1 },
  noHash:     { color: '#f57f17', fontSize: 11, flex: 1 },
  verifyBtn:  { marginLeft: 'auto' },
  verifyLabel: { fontSize: 11, color: '#1565c0' },
  reportTag:  { color: '#888', fontSize: 11, marginTop: 4, fontStyle: 'italic' },
});
