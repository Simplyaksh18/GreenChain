/**
 * CreateAccountScreen — Phase 9A+++
 *
 * POST /auth/register  →  { name, email, password, role }
 * Backend enforces:
 *   - password >= 8 characters (Pydantic field_validator)
 *   - email must be valid EmailStr
 *   - role must be one of: FARMER | FPO | VERIFIER | ADMIN
 *
 * Only those four fields are sent to the backend.
 * confirmPassword exists ONLY on the frontend for UX validation.
 */
import React, { useState, useMemo, useEffect } from 'react';
import {
  Image,
  ImageBackground,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import { Text, TextInput, HelperText } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { registerApi } from '../../api/authApi';
import { AppButton } from '../../components/AppButton';
import { GOOGLE_AUTH_ENABLED } from '../../utils/featureFlags';
import {
  useGoogleAuth,
  handleGoogleAuthResponse,
} from '../../services/googleAuthService';
import type { UserRole } from '../../types';

const BG_IMAGE = require('../../../assets/images/bg_login.jpg');
const LOGO = require('../../../assets/logo-transparent.png');

const ROLES: {
  label: string;
  value: UserRole;
  icon: keyof typeof MaterialCommunityIcons.glyphMap;
}[] = [
  { label: 'Farmer',   value: 'FARMER',   icon: 'sprout' },
  { label: 'FPO',      value: 'FPO',      icon: 'domain' },
  { label: 'Verifier', value: 'VERIFIER', icon: 'shield-search' },
  { label: 'Admin',    value: 'ADMIN',    icon: 'shield-crown-outline' },
];

/** Extract a human-readable message from a backend error response. */
function getErrorMessage(err: any): string {
  const status: number | undefined = err?.response?.status;
  const detail = err?.response?.data?.detail;

  if (status === 422) {
    // Pydantic v2 validation error — detail is an array
    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((e: any) => {
          const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : 'field';
          return `${field}: ${e.msg}`;
        })
        .join('\n');
    }
    if (typeof detail === 'string') return detail;
    return 'Validation failed. Please check your inputs.';
  }

  if (status === 400 || status === 409) {
    if (typeof detail === 'string') {
      const low = detail.toLowerCase();
      if (low.includes('email') || low.includes('already') || low.includes('exist')) {
        return 'This email is already registered. Please sign in instead.';
      }
      return detail;
    }
  }

  if (!err?.response) {
    return 'Cannot reach the server. Check your network.';
  }

  return 'Registration failed. Please try again.';
}

interface PasswordChecks {
  minLength: boolean;
  hasUppercase: boolean;
  hasLowercase: boolean;
  hasNumber: boolean;
  passwordsMatch: boolean;
}

function CheckRow({ passed, label }: { passed: boolean; label: string }) {
  return (
    <View style={styles.checkItem}>
      <MaterialCommunityIcons
        name={passed ? 'check-circle' : 'circle-outline'}
        size={15}
        color={passed ? '#2e7d32' : '#bbb'}
      />
      <Text style={[styles.checkText, passed && styles.checkTextPassed]}>{label}</Text>
    </View>
  );
}

export function CreateAccountScreen() {
  const navigation = useNavigation();
  // Optional Google prefill params — sent from LoginScreen when Google user needs registration
  const route = useRoute();
  const routeParams = (route.params ?? {}) as {
    prefillName?: string;
    prefillEmail?: string;
    googleSub?: string;
  };

  const [name, setName]                 = useState(routeParams.prefillName ?? '');
  const [email, setEmail]               = useState(routeParams.prefillEmail ?? '');
  const [password, setPassword]         = useState('');
  const [confirm, setConfirm]           = useState('');
  const [role, setRole]                 = useState<UserRole | null>(null);
  const [showPwd, setShowPwd]           = useState(false);
  const [showConfirm, setShowConfirm]   = useState(false);
  const [loading, setLoading]           = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError]               = useState('');
  const [success, setSuccess]           = useState(false);
  const [pwdFocused, setPwdFocused]     = useState(false);

  // Google OAuth for prefilling name/email
  const { request: googleRequest, response: googleResponse, promptAsync: googlePromptAsync } = useGoogleAuth();

  useEffect(() => {
    if (!googleResponse) return;
    (async () => {
      setGoogleLoading(true);
      setError('');
      try {
        const result = await handleGoogleAuthResponse(googleResponse);
        if (result.type === 'needs_registration') {
          // Prefill form — user still must choose role and set a password
          setName(result.data.name || name);
          setEmail(result.data.email || email);
        } else if (result.type === 'success') {
          // Already registered — direct to login
          setError('This Google account is already registered. Please sign in instead.');
        } else if (result.type === 'error') {
          setError(result.message);
        }
        // 'cancelled' → do nothing
      } finally {
        setGoogleLoading(false);
      }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [googleResponse]);

  // Live password strength checks — matches backend rules exactly
  const checks: PasswordChecks = useMemo(() => ({
    minLength:      password.length >= 8,
    hasUppercase:   /[A-Z]/.test(password),
    hasLowercase:   /[a-z]/.test(password),
    hasNumber:      /[0-9]/.test(password),
    passwordsMatch: password === confirm && password.length > 0,
  }), [password, confirm]);

  const allChecksPassed = Object.values(checks).every(Boolean);

  const isSubmittable =
    name.trim().length > 0 &&
    email.trim().length > 0 &&
    role !== null &&
    allChecksPassed;

  const handleRegister = async () => {
    if (!isSubmittable) return;
    setError('');
    setLoading(true);

    // Only send fields that backend schema expects
    const payload = {
      name: name.trim(),
      email: email.trim().toLowerCase(),
      password,          // ← never send confirmPassword to backend
      role: role!,       // ← guaranteed non-null by isSubmittable check
    };

    if (__DEV__) {
      // Development only — log payload structure without password value
      console.log('[Register] payload:', { ...payload, password: '[REDACTED]' });
    }

    try {
      await registerApi(payload);
      setSuccess(true);
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <ImageBackground source={BG_IMAGE} style={styles.bg} resizeMode="cover">
      <View style={styles.overlay} />
      <SafeAreaView style={styles.safe}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.flex}
        >
          <ScrollView
            contentContainerStyle={styles.scroll}
            keyboardShouldPersistTaps="handled"
          >
            {/* Brand */}
            <View style={styles.brandBlock}>
              <Image source={LOGO} style={styles.logoImg} resizeMode="contain" />
              <Text variant="headlineMedium" style={styles.brandTitle}>
                Create Account
              </Text>
              <Text variant="bodySmall" style={styles.brandSub}>
                Join GreenChain — Carbon Credit MRV Platform
              </Text>
            </View>

            {success ? (
              /* ── Success ─────────────────────────────────── */
              <View style={styles.card}>
                <View style={styles.successBox}>
                  <MaterialCommunityIcons name="check-circle" size={56} color="#2e7d32" />
                  <Text variant="titleLarge" style={styles.successTitle}>
                    Account Created!
                  </Text>
                  <Text variant="bodyMedium" style={styles.successSub}>
                    Your <Text style={{ fontWeight: '700' }}>{role}</Text> account has been
                    registered.{'\n'}Sign in with your credentials to access your dashboard.
                  </Text>
                </View>
                <AppButton
                  label="Go to Sign In"
                  onPress={() => navigation.goBack()}
                  style={styles.submitBtn}
                />
              </View>
            ) : (
              /* ── Form ────────────────────────────────────── */
              <View style={styles.card}>
                <Text variant="titleMedium" style={styles.cardTitle}>Your Details</Text>

                {/* Google prefill notice — only shown when arriving from Google OAuth */}
                {routeParams.googleSub ? (
                  <View style={styles.googlePrefillBanner}>
                    <MaterialCommunityIcons name="google" size={16} color="#1565c0" />
                    <Text variant="bodySmall" style={styles.googlePrefillText}>
                      Name and email prefilled from Google. Select a role and create a password to complete registration.
                    </Text>
                  </View>
                ) : null}

                <TextInput
                  label="Full Name"
                  value={name}
                  onChangeText={setName}
                  autoCapitalize="words"
                  autoComplete="name"
                  mode="outlined"
                  style={styles.input}
                  outlineStyle={styles.inputOutline}
                  left={<TextInput.Icon icon="account-outline" />}
                />

                <TextInput
                  label="Email Address"
                  value={email}
                  onChangeText={setEmail}
                  autoCapitalize="none"
                  keyboardType="email-address"
                  autoComplete="email"
                  mode="outlined"
                  style={styles.input}
                  outlineStyle={styles.inputOutline}
                  left={<TextInput.Icon icon="email-outline" />}
                />

                <TextInput
                  label="Password"
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry={!showPwd}
                  mode="outlined"
                  style={styles.input}
                  outlineStyle={styles.inputOutline}
                  onFocus={() => setPwdFocused(true)}
                  left={<TextInput.Icon icon="lock-outline" />}
                  right={
                    <TextInput.Icon
                      icon={showPwd ? 'eye-off-outline' : 'eye-outline'}
                      onPress={() => setShowPwd((v) => !v)}
                    />
                  }
                />

                <TextInput
                  label="Confirm Password"
                  value={confirm}
                  onChangeText={setConfirm}
                  secureTextEntry={!showConfirm}
                  mode="outlined"
                  style={styles.input}
                  outlineStyle={styles.inputOutline}
                  left={<TextInput.Icon icon="lock-check-outline" />}
                  right={
                    <TextInput.Icon
                      icon={showConfirm ? 'eye-off-outline' : 'eye-outline'}
                      onPress={() => setShowConfirm((v) => !v)}
                    />
                  }
                />

                {/* Live password checklist — shown after first password interaction */}
                {pwdFocused && (
                  <View style={styles.checkList}>
                    <CheckRow passed={checks.minLength}     label="Minimum 8 characters" />
                    <CheckRow passed={checks.hasUppercase}  label="Uppercase letter (A–Z)" />
                    <CheckRow passed={checks.hasLowercase}  label="Lowercase letter (a–z)" />
                    <CheckRow passed={checks.hasNumber}     label="At least one number (0–9)" />
                    <CheckRow passed={checks.passwordsMatch} label="Passwords match" />
                  </View>
                )}

                {/* Role picker */}
                <Text variant="labelMedium" style={styles.roleLabel}>Select Role</Text>
                <View style={styles.roleGrid}>
                  {ROLES.map((r) => {
                    const selected = role === r.value;
                    return (
                      <TouchableOpacity
                        key={r.value}
                        style={[styles.roleTile, selected && styles.roleTileSelected]}
                        onPress={() => setRole(r.value)}
                        activeOpacity={0.75}
                      >
                        <MaterialCommunityIcons
                          name={r.icon}
                          size={20}
                          color={selected ? '#2e7d32' : '#bbb'}
                        />
                        <Text
                          variant="labelMedium"
                          style={[styles.roleTileText, selected && styles.roleTileTextSelected]}
                        >
                          {r.label}
                        </Text>
                        {selected && (
                          <MaterialCommunityIcons
                            name="check-circle"
                            size={13}
                            color="#2e7d32"
                            style={styles.roleCheck}
                          />
                        )}
                      </TouchableOpacity>
                    );
                  })}
                </View>

                {error !== '' && (
                  <HelperText type="error" visible style={styles.errorText}>
                    {error}
                  </HelperText>
                )}

                <AppButton
                  label="Create Account"
                  onPress={handleRegister}
                  loading={loading}
                  disabled={!isSubmittable}
                  style={styles.submitBtn}
                />

                {/* Google prefill divider */}
                <View style={styles.dividerRow}>
                  <View style={styles.dividerLine} />
                  {GOOGLE_AUTH_ENABLED && <Text variant="bodySmall" style={styles.dividerText}>or</Text>}
                  {GOOGLE_AUTH_ENABLED && <View style={styles.dividerLine} />}
                </View>

                {/* Continue with Google — hidden behind GOOGLE_AUTH_ENABLED flag */}
                {GOOGLE_AUTH_ENABLED && (
                  <TouchableOpacity
                    style={[styles.googleBtn, (!googleRequest || googleLoading) && styles.googleBtnDisabled]}
                    onPress={() => googlePromptAsync()}
                    disabled={!googleRequest || googleLoading}
                    activeOpacity={0.8}
                  >
                    <MaterialCommunityIcons name="google" size={20} color="#1565c0" />
                    <Text style={styles.googleBtnText}>
                      {googleLoading ? 'Connecting to Google…' : 'Prefill with Google'}
                    </Text>
                  </TouchableOpacity>
                )}

                <TouchableOpacity
                  style={styles.backRow}
                  onPress={() => navigation.goBack()}
                  activeOpacity={0.7}
                >
                  <Text variant="bodyMedium" style={styles.backText}>
                    Already have an account?{' '}
                    <Text style={styles.backLink}>Sign In</Text>
                  </Text>
                </TouchableOpacity>
              </View>
            )}

            <Text variant="bodySmall" style={styles.footer}>
              ©️2026 developed by Akshi👩‍💻
            </Text>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </ImageBackground>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1 },
  overlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(10,40,15,0.68)' },
  safe: { flex: 1 },
  flex: { flex: 1 },
  scroll: { flexGrow: 1, justifyContent: 'center', padding: 24, paddingTop: 32 },

  brandBlock: { alignItems: 'center', marginBottom: 24 },
  logoImg: { width: 90, height: 90, marginBottom: 10, backgroundColor: 'transparent' },
  brandTitle: { fontWeight: '900', color: '#fff', letterSpacing: 0.5 },
  brandSub: { color: 'rgba(255,255,255,0.72)', marginTop: 4, textAlign: 'center' },

  card: {
    backgroundColor: 'rgba(255,255,255,0.97)',
    borderRadius: 24,
    padding: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.25,
    shadowRadius: 16,
    elevation: 10,
  },
  cardTitle: { fontWeight: '800', color: '#1b5e20', marginBottom: 14 },
  input: { marginBottom: 10, backgroundColor: '#fafafa' },
  inputOutline: { borderRadius: 12 },

  // Password checklist
  checkList: {
    backgroundColor: '#f9fafb',
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    gap: 6,
  },
  checkItem: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  checkText: { fontSize: 13, color: '#aaa' },
  checkTextPassed: { color: '#2e7d32', fontWeight: '600' },

  // Role tiles
  roleLabel: { color: '#555', marginBottom: 8, marginTop: 4 },
  roleGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 14 },
  roleTile: {
    flex: 1,
    minWidth: '44%',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: '#e0e0e0',
    backgroundColor: '#fafafa',
    position: 'relative',
  },
  roleTileSelected: { borderColor: '#2e7d32', backgroundColor: '#e8f5e9' },
  roleTileText: { color: '#bbb', fontWeight: '600', fontSize: 13 },
  roleTileTextSelected: { color: '#2e7d32' },
  roleCheck: { position: 'absolute', top: 4, right: 4 },

  errorText: { marginTop: -4, marginBottom: 8 },
  submitBtn: { marginTop: 4, borderRadius: 12 },

  dividerRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginVertical: 14 },
  dividerLine: { flex: 1, height: 1, backgroundColor: '#e0e0e0' },
  dividerText: { color: '#aaa' },

  googleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    borderWidth: 1.5,
    borderColor: '#1565c0',
    borderRadius: 12,
    paddingVertical: 12,
    backgroundColor: '#fff',
    marginBottom: 4,
  },
  googleBtnDisabled: { opacity: 0.5 },
  googleBtnText: { color: '#1565c0', fontWeight: '700', fontSize: 15 },

  backRow: { alignItems: 'center', marginTop: 16 },
  backText: { color: '#666' },
  backLink: { color: '#2e7d32', fontWeight: '800' },

  successBox: { alignItems: 'center', paddingVertical: 16, gap: 12 },
  successTitle: { fontWeight: '800', color: '#1b5e20' },
  successSub: { textAlign: 'center', color: '#555', lineHeight: 22 },

  footer: { textAlign: 'center', marginTop: 24, color: 'rgba(255,255,255,0.5)' },

  googlePrefillBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: '#e3f2fd',
    borderRadius: 10,
    padding: 10,
    marginBottom: 14,
  },
  googlePrefillText: { flex: 1, color: '#1565c0', lineHeight: 18 },
});
