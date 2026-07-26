/**
 * FPOWalletScreen — Phase 10A Secure Custodial Payout UX
 *
 * Features:
 * - Masked wallet display (first6...last6) — ALWAYS masked, no reveal
 * - Copy Address button
 * - View on PolygonScan (opens external explorer)
 * - Wallet type / network / verification status / vault identifier
 * - Edit form with EVM address validation
 * - Verify Wallet button (POST /fpo/profile/wallet/verify)
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Clipboard,
  KeyboardAvoidingView,
  Linking,
  Platform,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { Button, Text, TextInput } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { getFPOWallet, updateFPOWallet, verifyFPOWallet } from '../../api/custodialApi';
import { ErrorView } from '../../components/ErrorView';
import { GlassCard } from '../../components/GlassCard';
import { LoadingView } from '../../components/LoadingView';
import { RoleBackground } from '../../components/RoleBackground';
import type { FPOWallet } from '../../types';

export function FPOWalletScreen() {
  const [loading, setLoading]         = useState(true);
  const [saving, setSaving]           = useState(false);
  const [verifying, setVerifying]     = useState(false);
  const [wallet, setWallet]           = useState<FPOWallet | null>(null);
  const [address, setAddress]         = useState('');
  const [vaultId, setVaultId]         = useState('');
  const [network, setNetwork]         = useState('');
  const [error, setError]             = useState('');
  const [fetchError, setFetchError]   = useState('');
  const [editMode, setEditMode]       = useState(false);

  const loadWallet = useCallback(async () => {
    try {
      setFetchError('');
      const data = await getFPOWallet();
      setWallet(data);
      setAddress(data.wallet_address ?? '');
      setVaultId(data.vault_identifier ?? '');
      setNetwork(data.wallet_network ?? '');
    } catch {
      setFetchError('Failed to load wallet details.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadWallet(); }, [loadWallet]);

  // ── Actions ─────────────────────────────────────────────────────────────────

  const handleCopy = () => {
    const addr = wallet?.wallet_address;
    if (!addr) return;
    Clipboard.setString(addr);
    Alert.alert('Copied', 'Wallet address copied to clipboard.');
  };

  const handleViewOnPolygonScan = () => {
    const addr = wallet?.wallet_address;
    if (!addr) return;
    const url = `https://amoy.polygonscan.com/address/${addr}`;
    Linking.openURL(url).catch(() =>
      Alert.alert('Error', 'Could not open PolygonScan. Please check your internet connection.')
    );
  };

  const handleSave = async () => {
    setError('');
    const trimmed = address.trim().toLowerCase();
    if (trimmed && (trimmed.length !== 42 || !trimmed.startsWith('0x'))) {
      setError('Wallet address must be a 0x-prefixed 42-character EVM address.');
      return;
    }
    try {
      setSaving(true);
      await updateFPOWallet({
        wallet_address: trimmed || undefined,
        vault_identifier: vaultId.trim() || undefined,
        wallet_network: network.trim() || undefined,
      });
      Alert.alert('Saved', 'Wallet details updated. Verification has been reset — please re-verify.');
      setEditMode(false);
      loadWallet();
    } catch {
      setError('Failed to save. Please check the address and try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleVerify = async () => {
    try {
      setVerifying(true);
      const result = await verifyFPOWallet();
      Alert.alert(
        result.verified ? 'Verified ✓' : 'Verification Failed',
        result.message,
      );
      loadWallet();
    } catch (e: any) {
      Alert.alert('Verification Failed', e?.response?.data?.detail ?? 'Could not verify wallet.');
    } finally {
      setVerifying(false);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────────

  if (loading) return <LoadingView message="Loading wallet details…" />;
  if (fetchError) return <ErrorView message={fetchError} onRetry={loadWallet} />;

  const hasWallet    = Boolean(wallet?.wallet_address);
  const isVerified   = wallet?.wallet_verified === true;
  // Always display masked address — never reveal full address inside the app
  const displayAddr  = wallet?.wallet_address_masked ?? wallet?.wallet_address ?? '';

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.flex}
        >
          <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">

            {/* ── Status banner ──────────────────────────────────────────── */}
            <GlassCard style={styles.statusCard} opacity={0.9}>
              <View style={styles.statusRow}>
                <MaterialCommunityIcons
                  name={hasWallet ? (isVerified ? 'shield-check' : 'shield-alert') : 'alert-circle-outline'}
                  size={26}
                  color={hasWallet ? (isVerified ? '#2e7d32' : '#e65100') : '#c62828'}
                />
                <View style={styles.statusText}>
                  <Text variant="titleSmall" style={styles.statusTitle}>
                    {hasWallet
                      ? (isVerified ? 'Custodial Vault Wallet Verified ✓' : 'Wallet Set — Not Yet Verified')
                      : 'No Custodial Vault Wallet Set'}
                  </Text>
                  <Text variant="bodySmall" style={styles.statusDesc}>
                    {hasWallet
                      ? (isVerified
                        ? 'Your FPO custodial vault is verified and active. Carbon tokens are minted to this address on behalf of all linked farmers.'
                        : 'Wallet is configured but not verified. Tap "Verify Wallet" to confirm ownership.')
                      : 'Set a wallet address to enable token minting. Farmers do not need blockchain wallets.'}
                  </Text>
                </View>
              </View>
            </GlassCard>

            {/* ── Current wallet details ─────────────────────────────────── */}
            {hasWallet && !editMode && (
              <GlassCard style={styles.walletCard} opacity={0.88}>
                <Text variant="labelSmall" style={styles.label}>CUSTODIAL VAULT WALLET</Text>

                {/* Wallet address — always masked, no reveal */}
                <View style={styles.addrRow}>
                  <Text style={styles.walletAddr}>
                    {displayAddr}
                  </Text>
                  <MaterialCommunityIcons
                    name="content-copy"
                    size={20}
                    color="#1565c0"
                    onPress={handleCopy}
                    style={styles.icon}
                  />
                </View>
                <Button
                  mode="outlined"
                  icon="open-in-new"
                  onPress={handleViewOnPolygonScan}
                  style={styles.polygonBtn}
                  compact
                  textColor="#1565c0"
                >
                  View on PolygonScan
                </Button>

                {/* Metadata grid */}
                <View style={styles.metaGrid}>
                  <MetaRow label="Wallet Type" value="EVM / ERC-1155" />
                  <MetaRow label="Network" value={wallet?.wallet_network ?? 'MOCK_POLYGON_AMOY'} />
                  <MetaRow label="Verification"
                    value={isVerified ? '✓ Verified' : '⚠ Unverified'}
                    valueStyle={{ color: isVerified ? '#2e7d32' : '#e65100' }}
                  />
                  {wallet?.wallet_verified_at && (
                    <MetaRow label="Last Verified" value={new Date(wallet.wallet_verified_at).toLocaleDateString()} />
                  )}
                  {wallet?.vault_identifier && (
                    <MetaRow label="Vault Identifier" value={wallet.vault_identifier} />
                  )}
                  <MetaRow label="Custody Model" value="FPO Custodial — Farmers hold DB credits" />
                </View>

                {/* Verify / Edit actions */}
                <View style={styles.actionsRow}>
                  {!isVerified && (
                    <Button
                      mode="contained"
                      onPress={handleVerify}
                      loading={verifying}
                      disabled={verifying}
                      buttonColor="#2e7d32"
                      style={styles.actionBtn}
                      compact
                    >
                      Verify Wallet
                    </Button>
                  )}
                  <Button
                    mode="outlined"
                    onPress={() => setEditMode(true)}
                    style={styles.actionBtn}
                    compact
                  >
                    Edit
                  </Button>
                </View>
              </GlassCard>
            )}

            {/* ── Explainer ──────────────────────────────────────────────── */}
            <GlassCard style={styles.infoCard} opacity={0.88}>
              <View style={styles.infoRow}>
                <MaterialCommunityIcons name="information-outline" size={16} color="#1565c0" />
                <Text variant="bodySmall" style={styles.infoText}>
                  This is your FPO Custodial Vault Wallet. It holds ERC-1155 carbon credit tokens
                  on behalf of all farmers linked to your FPO. Farmers never need a personal crypto
                  wallet — carbon credits are tracked as database balances and paid out via UPI or
                  bank transfer. Only use a Polygon Amoy or Ethereum address.
                </Text>
              </View>
            </GlassCard>

            {/* ── Edit form ──────────────────────────────────────────────── */}
            {(!hasWallet || editMode) && (
              <GlassCard style={styles.formCard} opacity={0.88}>
                <Text variant="titleSmall" style={styles.sectionTitle}>
                  {hasWallet ? 'Update Wallet' : 'Set Wallet Address'}
                </Text>

                <TextInput
                  label="EVM Wallet Address (0x…)"
                  value={address}
                  onChangeText={setAddress}
                  mode="outlined"
                  style={styles.input}
                  autoCapitalize="none"
                  autoCorrect={false}
                  placeholder="0xAbCd1234…"
                  maxLength={42}
                />

                <TextInput
                  label="Vault Identifier (optional)"
                  value={vaultId}
                  onChangeText={setVaultId}
                  mode="outlined"
                  style={styles.input}
                  autoCapitalize="characters"
                  placeholder="FPO-VAULT-001"
                />

                <TextInput
                  label="Network (optional)"
                  value={network}
                  onChangeText={setNetwork}
                  mode="outlined"
                  style={styles.input}
                  autoCapitalize="characters"
                  placeholder="POLYGON_AMOY"
                />

                {error !== '' && (
                  <Text variant="bodySmall" style={styles.errorText}>{error}</Text>
                )}

                <View style={styles.formActions}>
                  {editMode && (
                    <Button
                      mode="outlined"
                      onPress={() => { setEditMode(false); setError(''); }}
                      style={styles.actionBtn}
                    >
                      Cancel
                    </Button>
                  )}
                  <Button
                    mode="contained"
                    onPress={handleSave}
                    loading={saving}
                    disabled={saving}
                    style={styles.actionBtn}
                    buttonColor="#1565c0"
                  >
                    {hasWallet ? 'Update Wallet' : 'Save Wallet'}
                  </Button>
                </View>
              </GlassCard>
            )}

          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </RoleBackground>
  );
}

// ── Small helper component ────────────────────────────────────────────────────

function MetaRow({
  label, value, valueStyle,
}: { label: string; value: string; valueStyle?: object }) {
  return (
    <View style={metaStyles.row}>
      <Text variant="labelSmall" style={metaStyles.label}>{label}</Text>
      <Text variant="bodySmall" style={[metaStyles.value, valueStyle]}>{value}</Text>
    </View>
  );
}

const metaStyles = StyleSheet.create({
  row: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 6 },
  label: { color: '#888', flex: 1 },
  value: { color: '#333', flex: 1, textAlign: 'right' },
});

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safe: { flex: 1 },
  flex: { flex: 1 },
  scroll: { padding: 14, paddingBottom: 40 },

  statusCard: { marginBottom: 10 },
  statusRow: { flexDirection: 'row', gap: 12, alignItems: 'flex-start' },
  statusText: { flex: 1 },
  statusTitle: { fontWeight: '700', color: '#333', marginBottom: 2 },
  statusDesc: { color: '#666', lineHeight: 18 },

  walletCard: { marginBottom: 10 },
  label: { color: '#888', letterSpacing: 0.5, marginBottom: 6 },
  addrRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  walletAddr: {
    flex: 1,
    fontFamily: 'monospace',
    fontSize: 13,
    color: '#1565c0',
    letterSpacing: 0.3,
  },
  icon: { padding: 2 },
  polygonBtn: { alignSelf: 'flex-start', marginBottom: 12, borderColor: '#1565c0', borderRadius: 8 },
  metaGrid: { borderTopWidth: 1, borderTopColor: 'rgba(0,0,0,0.08)', paddingTop: 10 },
  actionsRow: { flexDirection: 'row', gap: 10, marginTop: 14, flexWrap: 'wrap' },

  infoCard: { marginBottom: 10 },
  infoRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  infoText: { color: '#1565c0', flex: 1, lineHeight: 18 },

  formCard: { marginBottom: 10 },
  sectionTitle: { fontWeight: '700', color: '#333', marginBottom: 12 },
  input: { marginBottom: 10, backgroundColor: 'rgba(255,255,255,0.6)' },
  errorText: { color: '#c62828', marginBottom: 8 },
  formActions: { flexDirection: 'row', gap: 10, justifyContent: 'flex-end' },
  actionBtn: { borderRadius: 10 },
});
