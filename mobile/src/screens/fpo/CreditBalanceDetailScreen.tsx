/**
 * CreditBalanceDetailScreen — Phase 10A FPO Detail View
 *
 * Full detail of a single farmer credit balance:
 * - Farmer name / email / farm name
 * - Report ID / Token or Certificate ID
 * - Credits earned / available / distributed
 * - Masked payout method + verification status
 * - Payout eligibility
 * - Initiate Payout button (when credits_available > 0 and not zero-cert)
 *
 * GET /fpo/credits/farmers/{balance_id}/payout-details
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Alert, ScrollView, StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getFPOFarmerPayoutDetails } from '../../api/custodialApi';
import { ErrorView } from '../../components/ErrorView';
import { GlassCard } from '../../components/GlassCard';
import { LoadingView } from '../../components/LoadingView';
import { RoleBackground } from '../../components/RoleBackground';
import type { FPOCreditsStackParamList } from '../../navigation/FPOCreditsStack';

type Props = NativeStackScreenProps<FPOCreditsStackParamList, 'CreditBalanceDetail'>;

const STATUS_COLOR: Record<string, string> = {
  EARNED:      '#1565c0',
  TOKENIZED:   '#2e7d32',
  DISTRIBUTED: '#6a1b9a',
  HELD:        '#e65100',
  CANCELLED:   '#757575',
};

function DetailRow({ label, value, mono }: { label: string; value: string | null | undefined; mono?: boolean }) {
  if (!value) return null;
  return (
    <View style={detailStyles.row}>
      <Text variant="labelSmall" style={detailStyles.label}>{label}</Text>
      <Text variant="bodySmall" style={[detailStyles.value, mono && detailStyles.mono]}>
        {value}
      </Text>
    </View>
  );
}

const detailStyles = StyleSheet.create({
  row: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 6, alignItems: 'flex-start' },
  label: { color: '#888', flex: 1, marginRight: 8 },
  value: { color: '#333', flex: 2, textAlign: 'right' },
  mono: { fontFamily: 'monospace', fontSize: 12, color: '#1565c0' },
});

export function CreditBalanceDetailScreen({ route, navigation }: Props) {
  const { balance } = route.params;
  const [payoutDetails, setPayoutDetails] = useState<{
    preferred_payout_method: string | null;
    upi_id_masked: string | null;
    bank_account_holder_name: string | null;
    bank_account_number_masked: string | null;
    ifsc_code: string | null;
    payout_details_verified: boolean;
    has_payout_details: boolean;
  } | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(true);
  const [detailsError, setDetailsError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const data = await getFPOFarmerPayoutDetails(balance.id);
        setPayoutDetails(data);
      } catch {
        setDetailsError('Could not load payout details.');
      } finally {
        setLoadingDetails(false);
      }
    })();
  }, [balance.id]);

  const isZeroCert    = balance.credits_earned === 0;
  const canPayout     = !isZeroCert && balance.credits_available > 0;
  const farmerLabel   = balance.farmer_name ?? `Farmer #${balance.farmer_id}`;
  const statusColor   = STATUS_COLOR[balance.status] ?? '#555';

  const handleInitiatePayout = () => {
    if (!payoutDetails?.has_payout_details) {
      Alert.alert(
        'No Payout Details',
        `${farmerLabel} has not set up a payout method. Ask the farmer to add their UPI or bank details.`,
      );
      return;
    }
    navigation.navigate('InitiatePayout', {
      farmer_id: balance.farmer_id,
      balance_id: balance.id,
      credits_available: balance.credits_available,
      farmer_name: farmerLabel,
    });
  };

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <ScrollView contentContainerStyle={styles.scroll}>

          {/* ── Farmer / Farm ───────────────────────────────────────── */}
          <GlassCard style={styles.card} opacity={0.9}>
            <View style={styles.sectionHeader}>
              <MaterialCommunityIcons name="account-circle-outline" size={20} color="#1565c0" />
              <Text variant="titleSmall" style={styles.sectionTitle}>Farmer Details</Text>
            </View>
            <DetailRow label="Name" value={farmerLabel} />
            <DetailRow label="Email" value={balance.farmer_email} />
            <DetailRow label="Farm" value={balance.farm_name} />
          </GlassCard>

          {/* ── Credit Record ──────────────────────────────────────── */}
          <GlassCard style={styles.card} opacity={0.9}>
            <View style={styles.sectionHeader}>
              <MaterialCommunityIcons name="leaf-circle-outline" size={20} color={statusColor} />
              <Text variant="titleSmall" style={styles.sectionTitle}>Credit Record</Text>
              <View style={[styles.statusBadge, { backgroundColor: statusColor + '20' }]}>
                <Text variant="labelSmall" style={{ color: statusColor }}>{balance.status}</Text>
              </View>
            </View>
            <DetailRow label="Report ID" value={`#${balance.carbon_report_id}`} />
            {balance.carbon_token_id && (
              <DetailRow
                label={isZeroCert ? 'Certificate ID' : 'Token ID'}
                value={`#${balance.carbon_token_id}`}
              />
            )}
            <DetailRow label="Created" value={new Date(balance.created_at).toLocaleDateString('en-IN', {
              day: 'numeric', month: 'long', year: 'numeric',
            })} />

            {isZeroCert ? (
              <View style={styles.certNote}>
                <MaterialCommunityIcons name="certificate-outline" size={14} color="#6a1b9a" />
                <Text variant="labelSmall" style={styles.certNoteText}>
                  Verification certificate only — CO₂e below 1 tCO₂e threshold. No tradable credits
                  were generated. No payout is possible for this record.
                </Text>
              </View>
            ) : (
              <View style={styles.creditsGrid}>
                <CreditBox label="EARNED" value={balance.credits_earned} color="#1b5e20" />
                <CreditBox label="AVAILABLE" value={balance.credits_available} color="#2e7d32" />
                <CreditBox label="PAID OUT" value={balance.credits_distributed} color="#6a1b9a" />
              </View>
            )}
          </GlassCard>

          {/* ── Payout Details (FPO view — always masked) ─────────── */}
          <GlassCard style={styles.card} opacity={0.9}>
            <View style={styles.sectionHeader}>
              <MaterialCommunityIcons name="bank-outline" size={20} color="#1565c0" />
              <Text variant="titleSmall" style={styles.sectionTitle}>Payout Details</Text>
            </View>

            {loadingDetails ? (
              <Text variant="bodySmall" style={styles.dimText}>Loading…</Text>
            ) : detailsError ? (
              <Text variant="bodySmall" style={styles.errText}>{detailsError}</Text>
            ) : !payoutDetails?.has_payout_details ? (
              <View style={styles.noPayoutWrap}>
                <MaterialCommunityIcons name="alert-circle-outline" size={16} color="#e65100" />
                <Text variant="bodySmall" style={styles.noPayoutText}>
                  {farmerLabel} has not added payout details yet.
                </Text>
              </View>
            ) : (
              <>
                <DetailRow label="Method" value={payoutDetails.preferred_payout_method} />
                {payoutDetails.upi_id_masked && (
                  <DetailRow label="UPI ID" value={payoutDetails.upi_id_masked} mono />
                )}
                {payoutDetails.bank_account_holder_name && (
                  <DetailRow label="Account Holder" value={payoutDetails.bank_account_holder_name} />
                )}
                {payoutDetails.bank_account_number_masked && (
                  <DetailRow label="Account No." value={payoutDetails.bank_account_number_masked} mono />
                )}
                {payoutDetails.ifsc_code && (
                  <DetailRow label="IFSC" value={payoutDetails.ifsc_code} mono />
                )}
                <View style={[styles.verifiedBadge, {
                  backgroundColor: payoutDetails.payout_details_verified ? '#e8f5e9' : '#fff3e0',
                }]}>
                  <MaterialCommunityIcons
                    name={payoutDetails.payout_details_verified ? 'check-circle' : 'alert-circle-outline'}
                    size={13}
                    color={payoutDetails.payout_details_verified ? '#2e7d32' : '#e65100'}
                  />
                  <Text variant="labelSmall" style={{
                    color: payoutDetails.payout_details_verified ? '#2e7d32' : '#e65100',
                    marginLeft: 5,
                  }}>
                    {payoutDetails.payout_details_verified ? 'Format Verified' : 'Not Verified by Farmer'}
                  </Text>
                </View>
              </>
            )}
          </GlassCard>

          {/* ── Payout Eligibility + Action ───────────────────────── */}
          <GlassCard style={styles.card} opacity={0.9}>
            <View style={styles.sectionHeader}>
              <MaterialCommunityIcons name="cash-fast" size={20} color={canPayout ? '#2e7d32' : '#9e9e9e'} />
              <Text variant="titleSmall" style={styles.sectionTitle}>Payout Eligibility</Text>
            </View>

            {isZeroCert ? (
              <View style={styles.blockedNote}>
                <MaterialCommunityIcons name="information-outline" size={15} color="#6a1b9a" />
                <Text variant="bodySmall" style={styles.blockedText}>
                  No payout available — this is a certificate-only record. No tradable credits
                  were generated.
                </Text>
              </View>
            ) : balance.credits_available === 0 ? (
              <View style={styles.blockedNote}>
                <MaterialCommunityIcons name="check-circle-outline" size={15} color="#6a1b9a" />
                <Text variant="bodySmall" style={styles.blockedText}>
                  All {balance.credits_distributed} credit{balance.credits_distributed !== 1 ? 's' : ''} have
                  already been distributed. No further payout is possible for this record.
                </Text>
              </View>
            ) : (
              <>
                <Text variant="bodySmall" style={styles.eligibleText}>
                  {balance.credits_available} credit{balance.credits_available !== 1 ? 's' : ''} available
                  for payout.
                </Text>
                <Button
                  mode="contained"
                  onPress={handleInitiatePayout}
                  buttonColor="#1565c0"
                  icon="cash-fast"
                  style={styles.payoutBtn}
                  contentStyle={styles.payoutBtnContent}
                >
                  Initiate Payout ({balance.credits_available} credits)
                </Button>
              </>
            )}
          </GlassCard>

        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

function CreditBox({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <View style={styles.creditBox}>
      <Text variant="titleLarge" style={[styles.creditValue, { color }]}>{value}</Text>
      <Text variant="labelSmall" style={styles.creditLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { padding: 14, paddingBottom: 40 },

  card: { marginBottom: 10 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  sectionTitle: { fontWeight: '700', color: '#333', flex: 1 },
  statusBadge: { borderRadius: 12, paddingHorizontal: 8, paddingVertical: 3 },

  creditsGrid: {
    flexDirection: 'row', justifyContent: 'space-around',
    marginTop: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: '#f0f0f0',
  },
  creditBox: { alignItems: 'center' },
  creditValue: { fontWeight: '900' },
  creditLabel: { color: '#888', marginTop: 2 },

  certNote: {
    flexDirection: 'row', gap: 6, alignItems: 'flex-start',
    backgroundColor: '#f3e5f5', borderRadius: 8, padding: 8, marginTop: 10,
  },
  certNoteText: { flex: 1, color: '#6a1b9a', lineHeight: 16 },

  dimText: { color: '#aaa' },
  errText: { color: '#c62828' },

  noPayoutWrap: { flexDirection: 'row', gap: 6, alignItems: 'center' },
  noPayoutText: { color: '#e65100', flex: 1 },

  verifiedBadge: {
    flexDirection: 'row', alignItems: 'center',
    borderRadius: 12, paddingHorizontal: 8, paddingVertical: 4, marginTop: 10, alignSelf: 'flex-start',
  },

  blockedNote: {
    flexDirection: 'row', gap: 6, alignItems: 'flex-start',
    backgroundColor: '#f3e5f5', borderRadius: 8, padding: 10,
  },
  blockedText: { color: '#6a1b9a', flex: 1, lineHeight: 17 },
  eligibleText: { color: '#333', marginBottom: 12 },
  payoutBtn: { borderRadius: 10 },
  payoutBtnContent: { paddingVertical: 4 },
});
