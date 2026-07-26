/**
 * BuyerRetirementCertificateScreen — Phase 22B.
 *
 * A buyer-facing view of the retirement certificate for their own order.
 * Reuses the existing /marketplace/orders/{id}/certificate endpoint; the
 * backend allows the order's own buyer_user_id to fetch it.
 */
import React, { useEffect, useState } from 'react';
import { ScrollView, Share, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import {
  getRetirementCertificate,
  type RetirementCertificate,
} from '../../api/marketplaceApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import type { BuyerMarketplaceStackParamList } from '../../navigation/BuyerMarketplaceStack';

type Props = NativeStackScreenProps<BuyerMarketplaceStackParamList, 'BuyerRetirementCertificate'>;

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

export function BuyerRetirementCertificateScreen({ route }: Props) {
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
      title: 'Carbon Credit Retirement Certificate',
      message:
        `GreenChain Retirement Certificate\n\n` +
        `Certificate #${cert.id}\n` +
        `Order: ${cert.order_id}\n` +
        `Buyer: ${cert.buyer_name}\n` +
        `Credits retired: ${cert.credits_retired}\n` +
        `Hash: ${cert.certificate_hash}\n` +
        `Retired at: ${cert.created_at ?? ''}\n`,
    });
  };

  if (loading) return <LoadingView message="Loading certificate…" />;
  if (error || !cert) return <ErrorView message={error || 'Certificate not available'} />;

  return (
    <RoleBackground role="FARMER">
      <SafeAreaView style={{ flex: 1 }} edges={['bottom']}>
        <ScrollView contentContainerStyle={styles.scroll}>
          <SectionHeader icon="certificate-outline" title="Retirement Certificate" />
          <GlassCard style={styles.card}>
            <CertRow label="Certificate ID" value={String(cert.id)} />
            <CertRow label="Order ID" value={String(cert.order_id)} />
            <CertRow label="Buyer" value={cert.buyer_name} />
            <CertRow label="Credits retired" value={String(cert.credits_retired)} />
            <CertRow label="Retired at" value={cert.created_at ?? ''} />
            <CertRow label="Reason" value={cert.retirement_reason ?? '—'} />
            <CertRow label="Certificate hash" value={cert.certificate_hash} mono />
            <CertRow label="Token ID" value={String(cert.token_id)} />
          </GlassCard>

          <GlassCard style={styles.notice}>
            <View style={styles.noticeRow}>
              <MaterialCommunityIcons name="shield-check-outline" size={18} color="#00695c" />
              <Text style={styles.noticeText}>
                Credits retired on the GreenChain testnet. Blockchain reference:
                Polygon Amoy (test network).
              </Text>
            </View>
          </GlassCard>

          <TouchableOpacity style={styles.shareBtn} onPress={handleShare}>
            <MaterialCommunityIcons name="share-variant" size={18} color="#fff" />
            <Text style={styles.shareText}>Share certificate</Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingBottom: 24 },
  card: { padding: 14, gap: 8 },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
    paddingVertical: 4,
  },
  rowLabel: { color: '#555', fontSize: 13, flexShrink: 0 },
  rowValue: {
    flex: 1,
    textAlign: 'right',
    color: '#1b5e20',
    fontWeight: '600',
    fontSize: 13,
  },
  mono: { fontFamily: 'monospace', fontSize: 11, letterSpacing: 0 },
  notice: { padding: 12 },
  noticeRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  noticeText: { flex: 1, color: '#004d40', fontSize: 12, lineHeight: 18 },
  shareBtn: {
    marginTop: 12,
    marginHorizontal: 16,
    backgroundColor: '#2e7d32',
    paddingVertical: 10,
    borderRadius: 10,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  shareText: { color: '#fff', fontWeight: '700' },
});
