/**
 * RetirementCertificateScreen — Phase 16
 * Displays the immutable retirement certificate for a retired carbon credit order.
 * Certificate includes buyer name, credits retired, token ID, hash (SHA-256).
 */
import React, { useEffect, useState } from 'react';
import {
  ScrollView,
  Share,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getRetirementCertificate, type RetirementCertificate } from '../../api/marketplaceApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import type { FPOMarketplaceStackParamList } from './FPOListingsScreen';

type Props = NativeStackScreenProps<FPOMarketplaceStackParamList, 'FPORetirementCertificate'>;

function CertRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={[styles.rowValue, mono && styles.mono]} selectable>
        {value}
      </Text>
    </View>
  );
}

export function RetirementCertificateScreen({ route }: Props) {
  const { orderId } = route.params;
  const [cert, setCert] = useState<RetirementCertificate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const data = await getRetirementCertificate(orderId);
        setCert(data);
      } catch (e: any) {
        setError(e?.response?.data?.detail ?? 'Failed to load certificate');
      } finally {
        setLoading(false);
      }
    })();
  }, [orderId]);

  const handleShare = async () => {
    if (!cert) return;
    await Share.share({
      title: 'GreenChain Carbon Retirement Certificate',
      message: [
        '🌱 GreenChain Carbon Retirement Certificate',
        `Buyer: ${cert.buyer_name}`,
        `Credits Retired: ${cert.credits_retired} tCO₂e`,
        `Token ID: ${cert.token_id}`,
        `Date: ${new Date(cert.created_at).toLocaleDateString()}`,
        `Certificate Hash: ${cert.certificate_hash}`,
        'Verified on GreenChain Registry',
      ].join('\n'),
    });
  };

  if (loading) return <LoadingView message="Loading certificate…" />;
  if (error) return <ErrorView message={error} />;
  if (!cert) return <ErrorView message="Certificate not found." />;

  const retiredDate = new Date(cert.created_at).toLocaleString();

  return (
    <RoleBackground role="FPO">
      <SafeAreaView style={styles.safe}>
        <ScrollView contentContainerStyle={styles.scroll}>
          <SectionHeader icon="certificate" title="Retirement Certificate" />

          {/* Hero */}
          <View style={styles.heroCard}>
            <MaterialCommunityIcons name="certificate" size={52} color="#2e7d32" />
            <Text style={styles.heroTitle}>Carbon Credits Retired</Text>
            <Text style={styles.heroCredits}>{cert.credits_retired} tCO₂e</Text>
            <Text style={styles.heroBuyer}>Retired by {cert.buyer_name}</Text>
          </View>

          {/* Details */}
          <GlassCard style={styles.card}>
            <Text style={styles.sectionTitle}>Certificate Details</Text>
            <CertRow label="Certificate ID" value={`#${cert.id}`} />
            <CertRow label="Order ID" value={`#${cert.order_id}`} />
            <CertRow label="Token ID" value={`#${cert.token_id}`} />
            <CertRow label="Buyer Name" value={cert.buyer_name} />
            <CertRow label="Credits Retired" value={`${cert.credits_retired} tCO₂e`} />
            <CertRow label="Retired On" value={retiredDate} />
            {cert.retirement_reason && (
              <CertRow label="Purpose" value={cert.retirement_reason} />
            )}
          </GlassCard>

          {/* Hash */}
          <GlassCard style={styles.card}>
            <View style={styles.hashHeader}>
              <MaterialCommunityIcons name="shield-check" size={18} color="#2e7d32" />
              <Text style={styles.sectionTitle}>Cryptographic Proof</Text>
            </View>
            <Text style={styles.hashLabel}>SHA-256 Certificate Hash</Text>
            <Text style={styles.hash} selectable>{cert.certificate_hash}</Text>
            <Text style={styles.hashNote}>
              This hash is a SHA-256 digest of the retirement record. It can be independently
              verified and is immutable once issued.
            </Text>
          </GlassCard>

          {/* Share */}
          <TouchableOpacity style={styles.shareBtn} onPress={handleShare}>
            <MaterialCommunityIcons name="share-variant" size={18} color="#fff" />
            <Text style={styles.shareBtnTxt}>Share Certificate</Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { padding: 16, paddingBottom: 40 },
  heroCard: {
    alignItems: 'center',
    backgroundColor: '#e8f5e9',
    borderRadius: 16,
    padding: 24,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#a5d6a7',
  },
  heroTitle: { fontSize: 17, fontWeight: '600', color: '#1b5e20', marginTop: 8 },
  heroCredits: { fontSize: 40, fontWeight: '900', color: '#2e7d32', marginVertical: 4 },
  heroBuyer: { fontSize: 14, color: '#555' },
  card: { marginBottom: 16, padding: 16 },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: '#1b2e1b', marginBottom: 10 },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 5, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#e0e0e0' },
  rowLabel: { fontSize: 13, color: '#666', flex: 1 },
  rowValue: { fontSize: 13, fontWeight: '600', color: '#1b2e1b', flex: 2, textAlign: 'right' },
  mono: { fontFamily: 'monospace', fontSize: 11 },
  hashHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 },
  hashLabel: { fontSize: 12, color: '#666', marginBottom: 4 },
  hash: {
    fontFamily: 'monospace',
    fontSize: 12,
    color: '#1b5e20',
    backgroundColor: '#f1f8f1',
    padding: 10,
    borderRadius: 8,
    marginBottom: 8,
  },
  hashNote: { fontSize: 11, color: '#888', fontStyle: 'italic', lineHeight: 16 },
  shareBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#2e7d32',
    borderRadius: 12,
    paddingVertical: 14,
    marginTop: 4,
  },
  shareBtnTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
