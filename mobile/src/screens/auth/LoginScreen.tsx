import React, { useEffect, useState } from 'react';
import {
  Alert,
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
import { useNavigation } from '@react-navigation/native';

import { loginApi } from '../../api/authApi';
import { useAuthStore } from '../../store/authStore';
import { AppButton } from '../../components/AppButton';
import { GOOGLE_AUTH_ENABLED } from '../../utils/featureFlags';
import {
  useGoogleAuth,
  handleGoogleAuthResponse,
} from '../../services/googleAuthService';

const BG_IMAGE = require('../../../assets/images/bg_login.jpg');
const LOGO = require('../../../assets/logo-transparent.png');

export function LoginScreen() {
  const login = useAuthStore((s) => s.login);
  const navigation = useNavigation();

  const [email, setEmail]           = useState('');
  const [password, setPassword]     = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading]       = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError]           = useState('');

  // ── Google OAuth (expo-auth-session) ─────────────────────────────────────
  const { request, response: googleResponse, promptAsync } = useGoogleAuth();

  useEffect(() => {
    if (!googleResponse) return;
    (async () => {
      setGoogleLoading(true);
      try {
        const result = await handleGoogleAuthResponse(googleResponse);
        if (result.type === 'success') {
          await login(result.data.access_token);
        } else if (result.type === 'needs_registration') {
          (navigation as any).navigate('CreateAccount', {
            googleAccessToken: null, // token not kept; name/email prefilled only
            prefillName: result.data.name,
            prefillEmail: result.data.email,
            googleSub: result.data.google_sub,
          });
        } else if (result.type === 'error') {
          Alert.alert('Google Sign-In Failed', result.message);
        }
        // 'cancelled' — do nothing
      } finally {
        setGoogleLoading(false);
      }
    })();
  }, [googleResponse]);

  const handleLogin = async () => {
    if (!email.trim() || !password) {
      setError('Please enter your email and password.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const { access_token } = await loginApi({ email: email.trim(), password });
      await login(access_token); // fetches GET /users/me → sets user.role → RootNavigator redirects
    } catch (err: any) {
      const status = err?.response?.status;
      if (status === 401 || status === 400) {
        setError('Invalid email or password.');
      } else if (!err?.response) {
        setError('Cannot reach the server. Check your network and API_BASE_URL in .env.');
      } else {
        setError('Login failed. Please try again.');
      }
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
            {/* Branding */}
            <View style={styles.brandBlock}>
              <Image source={LOGO} style={styles.logoImg} resizeMode="contain" />
              <Text variant="headlineLarge" style={styles.brandTitle}>
                GreenChain
              </Text>
              <Text variant="bodyMedium" style={styles.brandSub}>
                Blockchain Carbon Credit MRV Platform
              </Text>
            </View>

            {/* Glass card */}
            <View style={styles.card}>
              <Text variant="titleLarge" style={styles.cardTitle}>
                Sign In
              </Text>
              <Text variant="bodySmall" style={styles.cardSub}>
                Access your carbon credit dashboard
              </Text>

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
                secureTextEntry={!showPassword}
                autoComplete="password"
                mode="outlined"
                style={styles.input}
                outlineStyle={styles.inputOutline}
                left={<TextInput.Icon icon="lock-outline" />}
                right={
                  <TextInput.Icon
                    icon={showPassword ? 'eye-off-outline' : 'eye-outline'}
                    onPress={() => setShowPassword((v) => !v)}
                  />
                }
              />

              {/* ── Create Account link — visible directly below password ── */}
              <TouchableOpacity
                style={styles.createAccountRow}
                onPress={() => navigation.navigate('CreateAccount' as never)}
                activeOpacity={0.7}
              >
                <Text variant="bodySmall" style={styles.createAccountText}>
                  Don't have an account?{' '}
                  <Text style={styles.createAccountLink}>Create New Account</Text>
                </Text>
              </TouchableOpacity>

              {error !== '' && (
                <HelperText type="error" visible style={styles.errorText}>
                  {error}
                </HelperText>
              )}

              <AppButton
                label="Sign In"
                onPress={handleLogin}
                loading={loading}
                style={styles.loginButton}
              />

              {/* Divider */}
              <View style={styles.dividerRow}>
                <View style={styles.dividerLine} />
                {GOOGLE_AUTH_ENABLED && <Text variant="bodySmall" style={styles.dividerText}>or</Text>}
                {GOOGLE_AUTH_ENABLED && <View style={styles.dividerLine} />}
              </View>

              {/* Continue with Google — hidden behind GOOGLE_AUTH_ENABLED flag */}
              {GOOGLE_AUTH_ENABLED && (
                <TouchableOpacity
                  style={[styles.googleButton, (!request || googleLoading) && styles.googleButtonDisabled]}
                  onPress={() => {
                    if (request && !googleLoading) {
                      promptAsync();
                    }
                  }}
                  activeOpacity={0.8}
                  disabled={!request || googleLoading}
                >
                  <Text style={styles.googleButtonText}>
                    {googleLoading ? 'Signing in with Google…' : 'Continue with Google'}
                  </Text>
                </TouchableOpacity>
              )}
            </View>

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
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(10,40,15,0.68)',
  },
  safe: { flex: 1 },
  flex: { flex: 1 },
  scroll: { flexGrow: 1, justifyContent: 'center', padding: 24 },

  brandBlock: { alignItems: 'center', marginBottom: 36 },
  logoImg: { width: 110, height: 110, marginBottom: 12, backgroundColor: 'transparent' },
  brandTitle: { fontWeight: '900', color: '#ffffff', letterSpacing: 1 },
  brandSub: { color: 'rgba(255,255,255,0.75)', marginTop: 6, textAlign: 'center', letterSpacing: 0.3 },

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
  cardTitle: { fontWeight: '800', color: '#1b5e20', marginBottom: 4 },
  cardSub: { color: '#888', marginBottom: 20 },

  input: { marginBottom: 12, backgroundColor: '#fafafa' },
  inputOutline: { borderRadius: 12 },

  createAccountRow: { alignItems: 'flex-start', marginBottom: 4, marginTop: -4 },
  createAccountText: { color: '#666' },
  createAccountLink: { color: '#2e7d32', fontWeight: '800' },

  errorText: { marginTop: 4, marginBottom: 4 },
  loginButton: { marginTop: 12, borderRadius: 12 },

  dividerRow: { flexDirection: 'row', alignItems: 'center', marginTop: 20, marginBottom: 4 },
  dividerLine: { flex: 1, height: 1, backgroundColor: '#e0e0e0' },
  dividerText: { marginHorizontal: 10, color: '#999' },

  googleButton: {
    marginTop: 12,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: '#d0d0d0',
    paddingVertical: 13,
    alignItems: 'center',
    backgroundColor: '#fff',
  },
  googleButtonDisabled: { opacity: 0.5 },
  googleButtonText: { color: '#333', fontWeight: '700', fontSize: 15 },

  footer: {
    textAlign: 'center',
    marginTop: 28,
    color: 'rgba(255,255,255,0.5)',
  },
});
