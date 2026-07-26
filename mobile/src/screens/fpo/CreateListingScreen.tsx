/**
 * CreateListingScreen — Phase 16
 * FPO selects a tokenized credit balance and creates a marketplace listing.
 *
 * Flow:
 *   1. Load FPO credit balances (GET /fpo/credit-balances)
 *   2. FPO selects balance, enters credits_to_list and price_per_credit
 *   3. POST /marketplace/listings
 *   4. Navigate back to FPOListingsScreen on success
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { createListing } from '../../api/marketplaceApi';
import { getFPOFarmerBalances } from '../../api/custodialApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { AppButton } from '../../components/AppButton';
import { LoadingView } from '../../components/LoadingView';
import type { FPOMarketplaceStackParamList } from './FPOListingsScreen';

type Props = NativeStackScreenProps<FPOMarketplaceStackParamList, 'FPOCreateListing'>;

interface CreditBalance {
  id: number;
  farmer_id: number;
  carbon_report_id: number;
  carbon_token_id: number | null;
  credits_available: number;
  credits_earned: number;
  status: string;
  farmer_name?: string | null;
  farm_name?: string | null;
}

export function CreateListingScreen({ navigation }: Props) {
  const [balances, setBalances] = useState<CreditBalance[]>([]);
  const [selectedBalance, setSelectedBalance] = useState<CreditBalance | null>(null);
  const [creditsToList, setCreditsToList] = useState('');
  // priceInput is in RUPEES (₹) — multiplied ×100 before sending to backend (which stores paise)
  const [priceInput, setPriceInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const data = await getFPOFarmerBalances();
        // Only TOKENIZED balances with available credits and a minted token can be listed
        const tokenized = (data as CreditBalance[]).filter(
          b => b.status === 'TOKENIZED' && b.credits_available > 0 && b.carbon_token_id
        );
        setBalances(tokenized);
      } catch {
        Alert.alert('Error', 'Failed to load credit balances');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleSubmit = async () => {
    if (!selectedBalance) {
      Alert.alert('Validation', 'Please select a credit balance to list.');
      return;
    }
    const credits = parseInt(creditsToList, 10);
    // priceInput is rupees → convert to paise for API
    const priceRs = parseFloat(priceInput);
    const pricePaise = Math.round(priceRs * 100);

    if (!credits || credits <= 0) {
      Alert.alert('Validation', 'Enter a valid number of credits to list.');
      return;
    }
    if (credits > selectedBalance.credits_available) {
      Alert.alert('Validation', `Cannot list more than ${selectedBalance.credits_available} available credits.`);
      return;
    }
    if (!priceRs || priceRs <= 0) {
      Alert.alert('Validation', 'Enter a valid price per credit in ₹ (e.g. 500 for ₹500).');
      return;
    }
    if (!selectedBalance.carbon_token_id) {
      Alert.alert('Error', 'Selected balance has no associated token. Please mint first.');
      return;
    }

    setSubmitting(true);
    try {
      await createListing({
        farmer_credit_balance_id: selectedBalance.id,
        carbon_token_id: selectedBalance.carbon_token_id,
        credits_listed: credits,
        price_per_credit: pricePaise,   // backend stores paise
        currency: 'INR',
      });
      Alert.alert('Success', 'Listing created successfully!', [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Failed to create listing');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingView message="Loading balances…" />;

  const creditsNum = parseInt(creditsToList, 10);
  const priceRsNum = parseFloat(priceInput);
  const totalRs = !isNaN(creditsNum) && !isNaN(priceRsNum) ? creditsNum * priceRsNum : null;

  return (
    <RoleBackground role="FPO">
      <SafeAreaView style={styles.safe}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={{ flex: 1 }}
        >
          <ScrollView contentContainerStyle={styles.scroll}>
            <SectionHeader icon="tag-plus-outline" title="Create Marketplace Listing" />

            {/* Explanation card */}
            <GlassCard style={styles.explainCard}>
              <View style={styles.explainRow}>
                <MaterialCommunityIcons name="information-outline" size={18} color="#1565c0" />
                <Text style={styles.explainText}>
                  Select a tokenized farmer credit balance. These credits are held by your FPO vault
                  and can be listed for buyers on the carbon marketplace.
                </Text>
              </View>
            </GlassCard>

            {/* Balance selector */}
            <GlassCard style={styles.card}>
              <Text style={styles.sectionLabel}>Select Credit Balance</Text>
              {balances.length === 0 ? (
                <View style={styles.emptyWrap}>
                  <MaterialCommunityIcons name="alert-circle-outline" size={28} color="#e65100" />
                  <Text style={styles.emptyTitle}>No Tokenized Balances Found</Text>
                  <Text style={styles.emptyDesc}>
                    No tokenized balances with available credits were found.{'\n'}
                    Required steps: Verify report → Admin mints token → credits_available {'>'} 0
                  </Text>
                </View>
              ) : (
                balances.map(b => (
                  <TouchableOpacity
                    key={b.id}
                    style={[
                      styles.balanceRow,
                      selectedBalance?.id === b.id && styles.balanceSelected,
                    ]}
                    onPress={() => setSelectedBalance(b)}
                    activeOpacity={0.8}
                  >
                    <MaterialCommunityIcons
                      name="leaf"
                      size={18}
                      color={selectedBalance?.id === b.id ? '#fff' : '#2e7d32'}
                    />
                    <View style={styles.balanceInfo}>
                      <Text style={[styles.balanceName, selectedBalance?.id === b.id && styles.selectedText]}>
                        {b.farmer_name ? b.farmer_name : `Farmer #${b.farmer_id}`}
                        {b.farm_name ? ` · ${b.farm_name}` : ''}
                      </Text>
                      <Text style={[styles.balanceMeta, selectedBalance?.id === b.id && styles.selectedTextMuted]}>
                        Report #{b.carbon_report_id} · Token #{b.carbon_token_id}
                      </Text>
                      <Text style={[styles.balanceSub, selectedBalance?.id === b.id && styles.selectedText]}>
                        {b.credits_available} credits available
                      </Text>
                    </View>
                    {selectedBalance?.id === b.id && (
                      <MaterialCommunityIcons name="check-circle" size={20} color="#fff" />
                    )}
                  </TouchableOpacity>
                ))
              )}
            </GlassCard>

            {/* Listing details */}
            <GlassCard style={styles.card}>
              <Text style={styles.sectionLabel}>Listing Details</Text>

              <Text style={styles.label}>Credits to List</Text>
              <TextInput
                style={styles.input}
                keyboardType="numeric"
                placeholder={selectedBalance ? `1 – ${selectedBalance.credits_available}` : 'Select a balance first'}
                value={creditsToList}
                onChangeText={setCreditsToList}
                editable={!!selectedBalance}
              />

              <Text style={[styles.label, { marginTop: 14 }]}>Price per Credit (₹)</Text>
              <TextInput
                style={styles.input}
                keyboardType="decimal-pad"
                placeholder="e.g. 500 for ₹500 per credit"
                value={priceInput}
                onChangeText={setPriceInput}
                editable={!!selectedBalance}
              />
              {priceInput.length > 0 && !isNaN(priceRsNum) && priceRsNum > 0 && (
                <Text style={styles.hint}>₹{priceRsNum.toFixed(2)} per credit</Text>
              )}
              {totalRs !== null && totalRs > 0 && (
                <Text style={styles.totalHint}>
                  Total listing value: ₹{totalRs.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </Text>
              )}
            </GlassCard>

            <AppButton
              label={submitting ? 'Creating…' : 'Create Listing'}
              onPress={handleSubmit}
              disabled={submitting || !selectedBalance || balances.length === 0}
              style={styles.submitBtn}
            />
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { padding: 16, paddingBottom: 40 },

  explainCard: { marginBottom: 12, padding: 12 },
  explainRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  explainText: { flex: 1, fontSize: 12, color: '#1b3a6b', lineHeight: 18 },

  card: { marginBottom: 16, padding: 16 },
  sectionLabel: { fontSize: 14, fontWeight: '700', color: '#1b2e1b', marginBottom: 12 },
  label: { fontSize: 13, fontWeight: '600', color: '#444', marginBottom: 6 },

  emptyWrap: { alignItems: 'center', gap: 8, paddingVertical: 12 },
  emptyTitle: { fontSize: 14, fontWeight: '700', color: '#e65100' },
  emptyDesc: { fontSize: 12, color: '#777', textAlign: 'center', lineHeight: 18 },

  balanceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#cde8cd',
    marginBottom: 8,
    backgroundColor: '#f1f8f1',
  },
  balanceSelected: { backgroundColor: '#2e7d32', borderColor: '#2e7d32' },
  balanceInfo: { flex: 1 },
  balanceName: { fontSize: 14, fontWeight: '700', color: '#1b2e1b' },
  balanceMeta: { fontSize: 11, color: '#888', marginTop: 1, fontFamily: 'monospace' },
  balanceSub: { fontSize: 12, color: '#2e7d32', marginTop: 2, fontWeight: '600' },
  selectedText: { color: '#fff' },
  selectedTextMuted: { color: 'rgba(255,255,255,0.75)' },

  input: {
    borderWidth: 1,
    borderColor: '#b0c4b0',
    borderRadius: 8,
    padding: 10,
    fontSize: 15,
    backgroundColor: '#fff',
    color: '#1b2e1b',
  },
  hint: { fontSize: 12, color: '#2e7d32', marginTop: 4 },
  totalHint: { fontSize: 13, fontWeight: '700', color: '#1b5e20', marginTop: 8 },
  submitBtn: { marginTop: 8 },
});
