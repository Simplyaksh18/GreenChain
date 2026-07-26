/**
 * InitiatePayoutScreen — Phase 17 Razorpay Checkout
 *
 * FPO initiates payouts for farmers.
 * GET  /fpo/credits/farmers          — list balances
 * POST /fpo/payouts/initiate         — create payout record
 * POST /payments/razorpay/create-order — create Razorpay Order (Step 1)
 *   → mobile opens RazorpayCheckout (Step 2 — native UI)
 * POST /payments/razorpay/verify     — verify HMAC signature (Step 3)
 * POST /fpo/payouts/{id}/complete    — Manual Settlement (separate path)
 * GET  /fpo/payouts                  — list all FPO payouts
 *
 * PAYMENT FLOW (Razorpay Checkout Test Mode):
 *   1. FPO sees INITIATED payout → taps "Pay with Razorpay Test"
 *   2. Backend creates Razorpay Order; returns key_id + order_id
 *   3. Native RazorpayCheckout opens (test card / test UPI)
 *   4. On success: backend verifies HMAC; marks payout COMPLETED
 *   5. No real money is moved — this is test mode only
 *
 * MANUAL SETTLEMENT (separate button):
 *   Use only when payment was handled outside the app (e.g. bank transfer).
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import {
  View, StyleSheet, ScrollView, RefreshControl, Alert,
} from 'react-native';
import { Text, Button, TextInput, Divider } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
// react-native-razorpay requires a dev client rebuild after install (expo run:android)
import RazorpayCheckout from 'react-native-razorpay';

import {
  getFPOFarmerBalances,
  getFPOPayouts,
  initiatePayoutApi,
  completePayoutApi,
} from '../../api/custodialApi';
import { getPaymentStatus, type PaymentStatus } from '../../api/socApi';
import { createRazorpayOrder, verifyRazorpayPayment } from '../../api/razorpayApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { LoadingView } from '../../components/LoadingView';
import { ErrorView } from '../../components/ErrorView';
import type { EnrichedFarmerCreditBalance, Payout } from '../../types';
import type { FPOCreditsStackParamList } from '../../navigation/FPOCreditsStack';

const STATUS_COLOR: Record<string, string> = {
  INITIATED: '#e65100',
  PROCESSING: '#1565c0',
  COMPLETED: '#2e7d32',
  FAILED: '#c62828',
  CANCELLED: '#757575',
};

// ── PayoutCard ─────────────────────────────────────────────────────────────────

function PayoutCard({
  payout,
  onPay,
  onManualSettle,
}: {
  payout: Payout;
  onPay: (payout: Payout) => void;
  onManualSettle: (id: number) => void;
}) {
  const color     = STATUS_COLOR[payout.status] ?? '#555';
  const priceRs   = (payout.price_per_credit / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 });
  const totalRs   = (payout.payout_amount    / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 });
  const isManual  = payout.remarks?.startsWith('[MANUAL]');
  const remark    = payout.remarks?.replace(/^\[(MANUAL)\]\s*/, '') ?? null;

  return (
    <View style={styles.payoutCard}>
      {/* Header row — status + date */}
      <View style={styles.payoutHeader}>
        <View style={styles.payoutHeaderLeft}>
          <Text variant="labelMedium" style={[styles.payoutStatus, { color }]}>
            {payout.status}
          </Text>
          {isManual && (
            <View style={styles.manualTag}>
              <Text variant="labelSmall" style={styles.manualTagText}>MANUAL</Text>
            </View>
          )}
        </View>
        <Text variant="labelSmall" style={styles.payoutDate}>
          {new Date(payout.initiated_at).toLocaleDateString('en-IN', {
            day: 'numeric', month: 'short', year: 'numeric',
          })}
        </Text>
      </View>

      {/* Amount row */}
      <View style={styles.payoutAmountRow}>
        <Text variant="headlineSmall" style={styles.payoutAmount}>₹{totalRs}</Text>
        <Text variant="bodySmall" style={styles.payoutCredits}>
          {payout.amount_credits} tCO₂e @ ₹{priceRs}/credit
        </Text>
      </View>

      {/* Razorpay payment reference (set after successful verify) */}
      {payout.provider_reference_id ? (
        <View style={styles.refRow}>
          <MaterialCommunityIcons name="check-circle" size={13} color="#2e7d32" />
          <Text variant="labelSmall" style={styles.refText}>
            Razorpay: {payout.provider_reference_id}
          </Text>
        </View>
      ) : null}

      {/* Remark (non-manual) */}
      {remark && !isManual && (
        <Text variant="bodySmall" style={styles.payoutRemarks}>"{remark}"</Text>
      )}

      {/* Action buttons — only for INITIATED payouts */}
      {payout.status === 'INITIATED' && (
        <View style={styles.payoutActions}>
          {/* Primary: Razorpay Checkout */}
          <Button
            mode="contained"
            compact
            onPress={() => onPay(payout)}
            style={styles.payBtn}
            buttonColor="#2e7d32"
            icon="credit-card-outline"
          >
            Pay with Razorpay Test
          </Button>

          {/* Secondary: manual settlement */}
          <Button
            mode="outlined"
            compact
            onPress={() => onManualSettle(payout.id)}
            style={styles.manualBtn}
            textColor="#757575"
          >
            Manual Settlement
          </Button>
        </View>
      )}
    </View>
  );
}

// ── Screen ─────────────────────────────────────────────────────────────────────

type Props = NativeStackScreenProps<FPOCreditsStackParamList, 'InitiatePayout'> & {
  route?: { params?: FPOCreditsStackParamList['InitiatePayout'] };
};

export function InitiatePayoutScreen({ route }: Partial<Props> = {}) {
  const preselect = route?.params;

  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [balances, setBalances]     = useState<EnrichedFarmerCreditBalance[]>([]);
  const [payouts, setPayouts]       = useState<Payout[]>([]);
  const [paymentStatus, setPaymentStatus] = useState<PaymentStatus | null>(null);

  // Form state
  const [selectedBalance, setSelectedBalance] = useState<EnrichedFarmerCreditBalance | null>(null);
  const [amountInput, setAmountInput]   = useState('1');
  const [priceInput, setPriceInput]     = useState('500');
  const [remarksInput, setRemarksInput] = useState('');
  const [formError, setFormError]       = useState('');
  const [initiating, setInitiating]     = useState(false);
  const [paying, setPaying]             = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      setError('');
      const [b, p, ps] = await Promise.all([
        getFPOFarmerBalances(),
        getFPOPayouts({ limit: 50 }),
        getPaymentStatus().catch(() => null),
      ]);
      setBalances(b);
      setPayouts(p);
      if (ps) setPaymentStatus(ps);

      if (preselect?.balance_id) {
        const match = b.find((bal) => bal.id === preselect.balance_id);
        if (match) {
          setSelectedBalance(match);
          setAmountInput(String(match.credits_available));
        } else {
          const avail = b.filter((bal) => bal.credits_available > 0);
          if (avail.length > 0) setSelectedBalance(avail[0]);
        }
      } else {
        const avail = b.filter((bal) => bal.credits_available > 0);
        if (avail.length > 0 && !selectedBalance) setSelectedBalance(avail[0]);
      }
    } catch {
      setError('Failed to load payout data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [preselect?.balance_id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const isMounted = useRef(true);
  useEffect(() => () => { isMounted.current = false; }, []);
  useFocusEffect(useCallback(() => {
    getPaymentStatus()
      .then((ps) => { if (isMounted.current) setPaymentStatus(ps); })
      .catch(() => {});
  }, []));

  const onRefresh = () => { setRefreshing(true); fetchAll(); };

  // ── Initiate payout record ─────────────────────────────────────────────────
  const handleInitiate = async () => {
    setFormError('');
    if (!selectedBalance) { setFormError('Select a credit balance.'); return; }
    const amount = parseFloat(amountInput);
    const price  = parseFloat(priceInput);
    if (isNaN(amount) || amount <= 0) { setFormError('Enter a valid credit amount > 0.'); return; }
    if (isNaN(price)  || price  <= 0) { setFormError('Enter a valid price per credit > 0.'); return; }
    if (amount > selectedBalance.credits_available) {
      setFormError(`Only ${selectedBalance.credits_available.toFixed(2)} credits available.`);
      return;
    }
    try {
      setInitiating(true);
      await initiatePayoutApi({
        credit_balance_id: selectedBalance.id,
        amount_credits:    amount,
        // price entered by FPO is in rupees (₹); backend stores paise → multiply by 100
        price_per_credit:  Math.round(price * 100),
        currency: 'INR',
        remarks: remarksInput.trim() || undefined,
      });
      const farmerLabel = selectedBalance.farmer_name ?? `Farmer #${selectedBalance.farmer_id}`;
      Alert.alert(
        'Payout Record Created',
        `Payout of ₹${(amount * price).toLocaleString('en-IN')} created for ${farmerLabel}.\n\nTap "Pay with Razorpay Test" below to complete the payment.`,
      );
      setAmountInput('1');
      setRemarksInput('');
      fetchAll();
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setFormError(detail ?? 'Failed to initiate payout.');
    } finally {
      setInitiating(false);
    }
  };

  // ── Pay via Razorpay Checkout (3-step flow) ────────────────────────────────
  const handleRazorpayPay = async (payout: Payout) => {
    setPaying(true);
    try {
      // Step 1: create Razorpay Order server-side
      const amountRupees = Math.round(payout.payout_amount / 100);  // payout_amount is in paise
      const orderResp = await createRazorpayOrder({
        purpose:      'FARMER_PAYOUT',
        reference_id: payout.id,
        amount:       amountRupees,
        currency:     'INR',
      });

      // Step 2: open Razorpay Checkout (native UI)
      // Use test card: 4111111111111111, CVV: 123, Expiry: any future date, OTP: 1234
      // Or test UPI: success@razorpay
      const checkoutOptions = {
        description:  'GreenChain Carbon Credit Payout (Test)',
        image:        'https://greenchain.app/icon.png',
        currency:     orderResp.currency,
        key:          orderResp.key_id,
        amount:       String(orderResp.amount_paise),  // react-native-razorpay expects string
        name:         'GreenChain',
        order_id:     orderResp.order_id,
        prefill: {
          email:       'fpo@greenchain.app',
          contact:     '9999999999',
          name:        'GreenChain FPO',
        },
        theme: { color: '#1565c0' },
      };

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const paymentData: any = await RazorpayCheckout.open(checkoutOptions);

      // Step 3: verify HMAC signature server-side
      const verifyResp = await verifyRazorpayPayment({
        payment_record_id:   orderResp.payment_record_id,
        razorpay_order_id:   paymentData.razorpay_order_id,
        razorpay_payment_id: paymentData.razorpay_payment_id,
        razorpay_signature:  paymentData.razorpay_signature,
      });

      if (verifyResp.status === 'COMPLETED') {
        Alert.alert(
          '✅ Payment Successful',
          `Payout marked as COMPLETED.\nRazorpay ID: ${verifyResp.razorpay_payment_id}`,
        );
        fetchAll();
      } else {
        Alert.alert('Payment Failed', verifyResp.failure_reason ?? 'Signature verification failed.');
      }
    } catch (e: unknown) {
      // RazorpayCheckout.open rejects when user cancels or payment fails
      const errMsg = (e as { description?: string; message?: string })?.description
        ?? (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? (e as Error)?.message
        ?? 'Payment failed or was cancelled.';
      // Don't alert on user-initiated cancel
      if (!errMsg.toLowerCase().includes('cancel')) {
        Alert.alert('Payment Error', errMsg);
      }
    } finally {
      setPaying(false);
    }
  };

  // ── Manual settlement (bypasses Razorpay — for offline payments) ───────────
  const handleManualSettle = (payoutId: number) => {
    Alert.alert(
      'Manual Settlement',
      'Use this only if payment was handled outside the app (e.g. bank transfer or UPI). This does NOT process a Razorpay payment.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Mark as Settled',
          style: 'destructive',
          onPress: async () => {
            try {
              await completePayoutApi(payoutId, { remarks: '[MANUAL] Settled outside app' });
              fetchAll();
            } catch {
              Alert.alert('Error', 'Failed to mark payout as settled.');
            }
          },
        },
      ],
    );
  };

  if (loading) return <LoadingView message="Loading payouts…" />;
  if (error)   return <ErrorView message={error} onRetry={fetchAll} />;

  const availableBalances = balances.filter((b) => b.credits_available > 0);

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={
            <RefreshControl
              refreshing={refreshing || paying}
              onRefresh={onRefresh}
              tintColor="#fff"
              colors={['#1976d2']}
            />
          }
        >
          {/* Razorpay Checkout Mode banner */}
          <View style={styles.banner}>
            <MaterialCommunityIcons name="credit-card-check-outline" size={16} color="#1565c0" />
            <View style={{ flex: 1 }}>
              <Text variant="labelSmall" style={styles.bannerTitle}>
                Razorpay Checkout — Test Mode
              </Text>
              <Text variant="bodySmall" style={styles.bannerSub}>
                Test payment screen will open. No real money is moved. Use test card 4111 1111 1111 1111 or UPI success@razorpay.
              </Text>
            </View>
          </View>

          {/* Initiate payout form */}
          <GlassCard style={styles.formCard} opacity={0.9}>
            <Text variant="titleSmall" style={styles.sectionTitle}>Create Payout Record</Text>

            {availableBalances.length === 0 ? (
              <View style={styles.noBalances}>
                <MaterialCommunityIcons name="cash-remove" size={32} color="#9e9e9e" />
                <Text variant="bodyMedium" style={styles.noBalancesText}>
                  No farmer balances with available credits.
                </Text>
              </View>
            ) : (
              <>
                {/* Balance selector */}
                <Text variant="labelSmall" style={styles.fieldLabel}>SELECT FARMER BALANCE</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.balanceScroll}>
                  {availableBalances.map((b) => (
                    <Button
                      key={b.id}
                      mode={selectedBalance?.id === b.id ? 'contained' : 'outlined'}
                      compact
                      onPress={() => setSelectedBalance(b)}
                      style={styles.balanceChip}
                      buttonColor={selectedBalance?.id === b.id ? '#1565c0' : undefined}
                    >
                      {b.farmer_name ?? `Farmer #${b.farmer_id}`} · {b.credits_available} tCO₂
                    </Button>
                  ))}
                </ScrollView>

                {selectedBalance && (
                  <View>
                    <Text variant="bodySmall" style={styles.selectedInfo}>
                      Available: {selectedBalance.credits_available} tCO₂e · Balance #{selectedBalance.id}
                    </Text>
                    {selectedBalance.farmer_payout_method ? (
                      <Text variant="labelSmall" style={styles.selectedPayoutMethod}>
                        Payout: {selectedBalance.farmer_payout_method === 'UPI' && selectedBalance.farmer_upi_id
                          ? `UPI — ${selectedBalance.farmer_upi_id}`
                          : selectedBalance.farmer_payout_method}
                      </Text>
                    ) : (
                      <Text variant="labelSmall" style={styles.selectedPayoutWarning}>
                        ⚠ Farmer has no payout details on file
                      </Text>
                    )}
                  </View>
                )}

                <View style={styles.twoCol}>
                  <TextInput
                    label="Credits (tCO₂e)"
                    value={amountInput}
                    onChangeText={setAmountInput}
                    mode="outlined"
                    style={styles.halfInput}
                    keyboardType="decimal-pad"
                  />
                  <TextInput
                    label="Price / credit (₹)"
                    value={priceInput}
                    onChangeText={setPriceInput}
                    mode="outlined"
                    style={styles.halfInput}
                    keyboardType="decimal-pad"
                  />
                </View>

                <TextInput
                  label="Remarks (optional)"
                  value={remarksInput}
                  onChangeText={setRemarksInput}
                  mode="outlined"
                  style={styles.input}
                  multiline
                  numberOfLines={2}
                />

                {formError !== '' && (
                  <Text variant="bodySmall" style={styles.errorText}>{formError}</Text>
                )}

                {amountInput && priceInput && !isNaN(parseFloat(amountInput)) && !isNaN(parseFloat(priceInput)) && (
                  <Text variant="bodyMedium" style={styles.totalText}>
                    Total: ₹{(parseFloat(amountInput) * parseFloat(priceInput)).toLocaleString('en-IN')}
                  </Text>
                )}

                <Button
                  mode="contained"
                  onPress={handleInitiate}
                  loading={initiating}
                  disabled={initiating || !selectedBalance}
                  style={styles.initiateBtn}
                  contentStyle={styles.initiateBtnContent}
                  buttonColor="#1565c0"
                >
                  Create Payout Record
                </Button>
              </>
            )}
          </GlassCard>

          {/* Payout history */}
          {payouts.length > 0 && (
            <GlassCard style={styles.historyCard} opacity={0.88}>
              <Text variant="titleSmall" style={styles.sectionTitle}>Payout History</Text>
              <Divider style={styles.divider} />
              {payouts.map((p) => (
                <PayoutCard
                  key={p.id}
                  payout={p}
                  onPay={handleRazorpayPay}
                  onManualSettle={handleManualSettle}
                />
              ))}
            </GlassCard>
          )}

        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe:   { flex: 1 },
  scroll: { padding: 12, paddingBottom: 40 },

  // Razorpay banner
  banner: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 8,
    backgroundColor: '#e3f2fd', borderColor: '#1565c0',
    borderWidth: 1, borderRadius: 10,
    marginHorizontal: 0, marginBottom: 10, marginTop: 4,
    paddingHorizontal: 12, paddingVertical: 8,
  },
  bannerTitle: { color: '#1565c0', fontWeight: '700' },
  bannerSub:   { color: '#546e7a', marginTop: 2 },

  // Form card
  formCard:     { marginBottom: 10 },
  sectionTitle: { fontWeight: '700', color: '#333', marginBottom: 10 },
  fieldLabel:   { color: '#888', marginBottom: 6, letterSpacing: 0.4 },
  balanceScroll: { marginBottom: 8 },
  balanceChip:  { marginRight: 8 },
  selectedInfo: { color: '#1565c0', marginBottom: 2 },
  selectedPayoutMethod: { color: '#2e7d32', marginBottom: 8 },
  selectedPayoutWarning: { color: '#e65100', marginBottom: 8 },
  twoCol:     { flexDirection: 'row', gap: 8 },
  halfInput:  { flex: 1, backgroundColor: 'rgba(255,255,255,0.6)' },
  input:      { marginBottom: 8, backgroundColor: 'rgba(255,255,255,0.6)' },
  errorText:  { color: '#c62828', marginBottom: 6 },
  totalText:  { color: '#2e7d32', fontWeight: '700', marginBottom: 10 },
  initiateBtn: { borderRadius: 10 },
  initiateBtnContent: { paddingVertical: 6 },
  noBalances: { alignItems: 'center', gap: 8, paddingVertical: 12 },
  noBalancesText: { color: '#777', textAlign: 'center' },

  // History card
  historyCard: { marginBottom: 10 },
  divider:     { marginBottom: 8 },

  // Payout card
  payoutCard: {
    backgroundColor: 'rgba(255,255,255,0.7)',
    borderRadius: 10, padding: 10, marginBottom: 8,
  },
  payoutHeader:     { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  payoutHeaderLeft: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  payoutStatus:     { fontWeight: '700' },
  manualTag:        { backgroundColor: '#fff3e0', borderRadius: 6, paddingHorizontal: 5, paddingVertical: 1 },
  manualTagText:    { color: '#e65100', fontSize: 9, fontWeight: '800', letterSpacing: 0.5 },
  payoutDate:       { color: '#aaa' },
  payoutAmountRow:  { marginBottom: 4 },
  payoutAmount:     { fontWeight: '900', color: '#333' },
  payoutCredits:    { color: '#777' },
  refRow:           { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 4 },
  refText:          { color: '#2e7d32', fontFamily: 'monospace', fontSize: 11 },
  payoutRemarks:    { color: '#888', fontStyle: 'italic', marginBottom: 6 },

  // Action buttons
  payoutActions: { flexDirection: 'row', gap: 8, flexWrap: 'wrap', marginTop: 8 },
  payBtn:        { flex: 1, borderRadius: 8 },
  manualBtn:     { borderRadius: 8 },
});
