/**
 * PayoutDetailsScreen — Phase 10A Secure Custodial Payout UX
 *
 * Features:
 * - Masked UPI display (first char + *** + @domain)
 * - Masked bank account display (last 4 digits)
 * - Verify button (POST /farmers/payout-details/verify)
 * - Verification status badge (Unverified / Format Verified)
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { Button, RadioButton, Text, TextInput } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { getPayoutDetails, upsertPayoutDetails, verifyPayoutDetails } from '../../api/custodialApi';
import { ErrorView } from '../../components/ErrorView';
import { GlassCard } from '../../components/GlassCard';
import { LoadingView } from '../../components/LoadingView';
import { RoleBackground } from '../../components/RoleBackground';
import type { FarmerPayoutDetails } from '../../types';

type PayoutMethod = 'UPI' | 'BANK_TRANSFER';

export function PayoutDetailsScreen() {
  const [loading, setLoading]       = useState(true);
  const [saving, setSaving]         = useState(false);
  const [verifying, setVerifying]   = useState(false);
  const [existing, setExisting]     = useState<FarmerPayoutDetails | null>(null);
  const [method, setMethod]         = useState<PayoutMethod>('UPI');
  const [upiId, setUpiId]           = useState('');
  const [holderName, setHolderName] = useState('');
  const [accountNo, setAccountNo]   = useState('');
  const [ifsc, setIfsc]             = useState('');
  const [bankName, setBankName]     = useState('');
  const [error, setError]           = useState('');
  const [fetchError, setFetchError] = useState('');

  const loadDetails = useCallback(async () => {
    try {
      setFetchError('');
      const data = await getPayoutDetails();
      setExisting(data);
      if (data.preferred_payout_method) setMethod(data.preferred_payout_method);
      // Never prefill UPI or bank from masked values
      if (data.bank_account_holder_name) setHolderName(data.bank_account_holder_name);
      if (data.ifsc_code) setIfsc(data.ifsc_code);
      if (data.bank_name) setBankName(data.bank_name);
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      if (status !== 404) {
        setFetchError('Could not load your payout details.');
      }
      // 404 = no details yet; fine
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadDetails(); }, [loadDetails]);

  const handleSave = async () => {
    setError('');
    const body: Parameters<typeof upsertPayoutDetails>[0] = {
      preferred_payout_method: method,
    };
    if (method === 'UPI') {
      if (!upiId.trim()) { setError('UPI ID is required.'); return; }
      if (!upiId.includes('@')) { setError('UPI ID must contain "@" (e.g. name@upi).'); return; }
      body.upi_id = upiId.trim().toLowerCase();
    } else {
      if (!holderName.trim()) { setError('Account holder name is required.'); return; }
      if (!accountNo.trim()) { setError('Account number is required.'); return; }
      if (accountNo.trim().length < 9 || accountNo.trim().length > 18) {
        setError('Account number must be 9–18 digits.'); return;
      }
      if (!ifsc.trim() || ifsc.trim().length !== 11) {
        setError('IFSC code must be exactly 11 characters.'); return;
      }
      body.bank_account_holder_name = holderName.trim();
      body.bank_account_number      = accountNo.trim();
      body.ifsc_code                = ifsc.trim().toUpperCase();
      if (bankName.trim()) body.bank_name = bankName.trim();
    }
    try {
      setSaving(true);
      const updated = await upsertPayoutDetails(body);
      setExisting(updated);
      setUpiId('');
      setAccountNo('');
      Alert.alert('Saved', 'Payout details updated. Tap "Verify Details" to confirm format.');
      loadDetails();
    } catch {
      setError('Failed to save payout details. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleVerify = async () => {
    try {
      setVerifying(true);
      const updated = await verifyPayoutDetails();
      setExisting(updated);
      Alert.alert('Verified ✓', 'Your payout details have been format-verified.');
    } catch (e: any) {
      Alert.alert('Verification Failed', e?.response?.data?.detail ?? 'Could not verify. Check your details.');
    } finally {
      setVerifying(false);
    }
  };

  if (loading) return <LoadingView message="Loading payout details…" />;
  if (fetchError) return <ErrorView message={fetchError} onRetry={loadDetails} />;

  const isVerified = existing?.payout_details_verified === true;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.flex}
        >
          <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">

            {/* ── Info banner ─────────────────────────────────────────────── */}
            <GlassCard style={styles.infoCard} opacity={0.88}>
              <View style={styles.infoRow}>
                <MaterialCommunityIcons name="shield-lock-outline" size={20} color="#1565c0" />
                <Text variant="bodySmall" style={styles.infoText}>
                  Your FPO will use these details to send carbon credit payouts.
                  Account numbers are stored encrypted and shown masked — only the last 4 digits
                  are visible. UPI IDs are always displayed masked for your privacy.
                </Text>
              </View>
            </GlassCard>

            {/* ── Current masked details ─────────────────────────────────── */}
            {existing && (
              <GlassCard style={styles.existingCard} opacity={0.88}>
                <View style={styles.verifiedRow}>
                  <Text variant="labelSmall" style={styles.existingLabel}>SAVED PAYOUT METHOD</Text>
                  <View style={[
                    styles.verifiedBadge,
                    { backgroundColor: isVerified ? '#e8f5e9' : '#fff3e0' },
                  ]}>
                    <MaterialCommunityIcons
                      name={isVerified ? 'check-circle' : 'alert-circle-outline'}
                      size={12}
                      color={isVerified ? '#2e7d32' : '#e65100'}
                    />
                    <Text variant="labelSmall" style={{
                      color: isVerified ? '#2e7d32' : '#e65100', marginLeft: 4,
                    }}>
                      {isVerified
                        ? `Verified (${existing.payout_verification_method ?? 'FORMAT_CHECK'})`
                        : 'Not Verified'}
                    </Text>
                  </View>
                </View>

                {existing.preferred_payout_method === 'UPI' && (
                  <>
                    <Text variant="bodySmall" style={styles.methodLabel}>UPI</Text>
                    <Text style={styles.maskedValue}>
                      {existing.upi_id_masked ?? '•••@•••'}
                    </Text>
                  </>
                )}
                {existing.preferred_payout_method === 'BANK_TRANSFER' && (
                  <>
                    <Text variant="bodySmall" style={styles.methodLabel}>Bank Transfer</Text>
                    {existing.bank_account_holder_name && (
                      <Text variant="bodySmall" style={styles.existingDetail}>
                        {existing.bank_account_holder_name}
                      </Text>
                    )}
                    <Text style={styles.maskedValue}>
                      {existing.bank_account_number_masked ?? '••••••••'}
                    </Text>
                    {existing.ifsc_code && (
                      <Text variant="bodySmall" style={styles.existingDetail}>
                        IFSC: {existing.ifsc_code}
                      </Text>
                    )}
                    {existing.bank_name && (
                      <Text variant="bodySmall" style={styles.existingDetail}>
                        Bank: {existing.bank_name}
                      </Text>
                    )}
                  </>
                )}

                {!isVerified && (
                  <Button
                    mode="outlined"
                    onPress={handleVerify}
                    loading={verifying}
                    disabled={verifying}
                    style={styles.verifyBtn}
                    compact
                  >
                    Verify Details
                  </Button>
                )}
              </GlassCard>
            )}

            {/* ── Update form ─────────────────────────────────────────────── */}
            <GlassCard style={styles.formCard} opacity={0.88}>
              <Text variant="titleSmall" style={styles.sectionTitle}>
                {existing ? 'Update Payout Method' : 'Set Payout Method'}
              </Text>

              <RadioButton.Group
                onValueChange={(v) => setMethod(v as PayoutMethod)}
                value={method}
              >
                <View style={styles.radioRow}>
                  <RadioButton.Android value="UPI" color="#2e7d32" />
                  <Text variant="bodyMedium" style={styles.radioLabel}>UPI</Text>
                  <MaterialCommunityIcons name="cellphone" size={18} color="#555" style={styles.radioIcon} />
                </View>
                <View style={styles.radioRow}>
                  <RadioButton.Android value="BANK_TRANSFER" color="#2e7d32" />
                  <Text variant="bodyMedium" style={styles.radioLabel}>Bank Transfer</Text>
                  <MaterialCommunityIcons name="bank-outline" size={18} color="#555" style={styles.radioIcon} />
                </View>
              </RadioButton.Group>

              {method === 'UPI' ? (
                <TextInput
                  label="New UPI ID (e.g. name@upi)"
                  value={upiId}
                  onChangeText={setUpiId}
                  mode="outlined"
                  style={styles.input}
                  autoCapitalize="none"
                  keyboardType="email-address"
                  placeholder="yourname@okicici"
                />
              ) : (
                <>
                  <TextInput
                    label="Account Holder Name"
                    value={holderName}
                    onChangeText={setHolderName}
                    mode="outlined"
                    style={styles.input}
                    autoCapitalize="words"
                  />
                  <TextInput
                    label="Bank Account Number (9–18 digits)"
                    value={accountNo}
                    onChangeText={setAccountNo}
                    mode="outlined"
                    style={styles.input}
                    keyboardType="numeric"
                    secureTextEntry
                    placeholder="Enter new account number"
                  />
                  <TextInput
                    label="IFSC Code (11 characters)"
                    value={ifsc}
                    onChangeText={(t) => setIfsc(t.toUpperCase())}
                    mode="outlined"
                    style={styles.input}
                    autoCapitalize="characters"
                    maxLength={11}
                  />
                  <TextInput
                    label="Bank Name (e.g. State Bank of India)"
                    value={bankName}
                    onChangeText={setBankName}
                    mode="outlined"
                    style={styles.input}
                    autoCapitalize="words"
                    placeholder="State Bank of India"
                  />
                </>
              )}

              {error !== '' && (
                <Text variant="bodySmall" style={styles.errorText}>{error}</Text>
              )}

              <Button
                mode="contained"
                onPress={handleSave}
                loading={saving}
                disabled={saving}
                style={styles.saveBtn}
                contentStyle={styles.saveBtnContent}
                buttonColor="#2e7d32"
              >
                {existing ? 'Update Details' : 'Save Details'}
              </Button>
            </GlassCard>

          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  flex: { flex: 1 },
  scroll: { padding: 14, paddingBottom: 40 },

  infoCard: { marginBottom: 10 },
  infoRow: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  infoText: { color: '#1565c0', flex: 1, lineHeight: 18 },

  existingCard: { marginBottom: 10 },
  verifiedRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  existingLabel: { color: '#888', letterSpacing: 0.5 },
  verifiedBadge: { flexDirection: 'row', alignItems: 'center', borderRadius: 12, paddingHorizontal: 8, paddingVertical: 3 },
  methodLabel: { color: '#888', marginBottom: 2 },
  maskedValue: {
    fontFamily: 'monospace', fontSize: 15, color: '#1b5e20', fontWeight: '700', marginBottom: 4,
  },
  existingDetail: { color: '#666', marginTop: 2 },
  verifyBtn: { marginTop: 12, borderRadius: 8, alignSelf: 'flex-start' },

  formCard: {},
  sectionTitle: { fontWeight: '700', color: '#333', marginBottom: 10 },
  radioRow: { flexDirection: 'row', alignItems: 'center', marginVertical: 2 },
  radioLabel: { color: '#333', flex: 1 },
  radioIcon: { marginLeft: 4 },
  input: { marginBottom: 10, backgroundColor: 'rgba(255,255,255,0.6)' },
  errorText: { color: '#c62828', marginBottom: 8 },
  saveBtn: { marginTop: 4, borderRadius: 10 },
  saveBtnContent: { paddingVertical: 6 },
});
