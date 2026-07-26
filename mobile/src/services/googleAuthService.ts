/**
 * googleAuthService.ts — Phase 15: Google OAuth
 *
 * ┌──────────────────────────────────────────────────────────────────────────────┐
 * │ How redirect URIs work (do not override them manually):                      │
 * │                                                                              │
 * │ Google.useAuthRequest computes redirectUri automatically:                    │
 * │   Android → native: `${Application.applicationId}:/oauthredirect`           │
 * │             = com.greenchain.app:/oauthredirect                              │
 * │   This matches the Android OAuth client in Google Cloud Console by           │
 * │   package name + SHA-1 — no URL registration needed.                        │
 * │                                                                              │
 * │ DO NOT pass a custom redirectUri to Google.useAuthRequest.                  │
 * │ DO NOT use AuthSession.makeRedirectUri({ scheme: 'greenchain' }).            │
 * │ greenchain:// is the deep-link scheme, NOT the OAuth redirect URI.          │
 * │ Forcing it sends an invalid_request to Google.                               │
 * └──────────────────────────────────────────────────────────────────────────────┘
 *
 * SECURITY RULES (never relax these):
 *  - Never store the Google access token in local storage or state beyond the call.
 *  - Never log the access token value — only log auth mode and whether token was received.
 *  - Never expose the token in network response logging.
 *  - Never let Google decide the user's GreenChain role.
 *  - Do not break or alter existing email/password login.
 */

import type { AuthSessionResult } from 'expo-auth-session';
import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://192.168.1.10:8000';

// Finalize any pending OAuth browser session on Android so the tab closes cleanly.
WebBrowser.maybeCompleteAuthSession();

// ── Auth mode ─────────────────────────────────────────────────────────────────
// Set EXPO_PUBLIC_GOOGLE_AUTH_MODE=DEVELOPMENT_BUILD in mobile/.env when running
// via `npm run dev` (expo start --dev-client --clear).
const AUTH_MODE = process.env.EXPO_PUBLIC_GOOGLE_AUTH_MODE ?? 'EXPO_GO';
const IS_DEV_BUILD = AUTH_MODE === 'DEVELOPMENT_BUILD';

// ── Debug flag ────────────────────────────────────────────────────────────────
// All Google OAuth diagnostic logs are gated behind this flag.
// Default: false — no OAuth logs appear even in dev builds.
// Set EXPO_PUBLIC_GOOGLE_AUTH_DEBUG=true in mobile/.env ONLY when actively
// debugging OAuth redirect / client ID issues. Never enable in production.
const GOOGLE_AUTH_DEBUG = __DEV__ && process.env.EXPO_PUBLIC_GOOGLE_AUTH_DEBUG === 'true';

// ── OAuth Client IDs ──────────────────────────────────────────────────────────
//
// Web client:     Google Cloud Console → Create OAuth client → Web application
//                 Add  greenchain://  to "Authorized redirect URIs"
//                 No SHA-1 required.
//
// Android client: Google Cloud Console → Create OAuth client → Android
//                 Package name: com.greenchain.app
//                 SHA-1: run `eas credentials -p android` → copy fingerprint
//                 Used for native Android production builds. Optional for dev builds.
//
// Use `|| undefined` so unset vars become undefined (not '').
// expo-auth-session uses ?? which does NOT fall through on empty string.
const WEB_CLIENT_ID =
  process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID || undefined;

const ANDROID_CLIENT_ID =
  process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID || undefined;

// Scopes requested from Google:
//   openid    — ID token (sub/email/name/picture)
//   email     — email address
//   profile   — display name + picture
//   drive.readonly — for future Drive import (requested upfront so user only consents once)
const SCOPES = ['openid', 'email', 'profile', 'https://www.googleapis.com/auth/drive.readonly'];

// ── Types ─────────────────────────────────────────────────────────────────────

export interface GoogleUserInfo {
  sub: string;
  email: string;
  name: string;
  picture?: string;
}

export interface GoogleLoginSuccessResult {
  /** GreenChain JWT — ready to store in SecureStore */
  access_token: string;
  token_type: string;
  auth_provider: 'GOOGLE';
}

export interface GoogleNeedsRegistrationResult {
  needs_registration: true;
  name: string;
  email: string;
  google_sub: string;
  profile_photo_url?: string;
}

export type GoogleLoginResult =
  | { type: 'success'; data: GoogleLoginSuccessResult }
  | { type: 'needs_registration'; data: GoogleNeedsRegistrationResult }
  | { type: 'cancelled' }
  | { type: 'error'; message: string };

// ── useGoogleAuth hook ────────────────────────────────────────────────────────
//
// Use this hook inside a React component.
// Example:
//   const { request, promptAsync, loading, error } = useGoogleAuth();
//   <Button onPress={() => promptAsync()} title="Continue with Google" />

export function useGoogleAuth() {
  // ── Guard ─────────────────────────────────────────────────────────────────
  if (!WEB_CLIENT_ID) {
    throw new Error(
      '[GoogleOAuth] EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID is not set.\n' +
      'Add it to mobile/.env and restart Expo with --clear.',
    );
  }

  // ── Dev diagnostics (behind GOOGLE_AUTH_DEBUG flag) ──────────────────────
  if (GOOGLE_AUTH_DEBUG) {
    console.log('[GoogleOAuth] WEB_CLIENT_ID prefix:', WEB_CLIENT_ID ? WEB_CLIENT_ID.substring(0, 12) : 'MISSING');
    console.log('[GoogleOAuth] ANDROID_CLIENT_ID prefix:', ANDROID_CLIENT_ID ? ANDROID_CLIENT_ID.substring(0, 12) : 'MISSING');
    console.log('[GoogleOAuth] auth mode:', AUTH_MODE);
    console.log('[GoogleOAuth] clientId used on Android:', ANDROID_CLIENT_ID ? 'android' : 'web (fallback)');

    if (!ANDROID_CLIENT_ID) {
      console.warn(
        '[GoogleOAuth] ANDROID_CLIENT_ID missing → library falls back to WEB_CLIENT_ID on Android.\n' +
        'To create an Android OAuth client:\n' +
        '  Google Cloud Console → APIs & Services → Credentials →\n' +
        '  Create credentials → OAuth client ID → Android\n' +
        '  Package name: com.greenchain.app\n' +
        '  SHA-1: run `eas credentials -p android` → copy the fingerprint.',
      );
    }
  }

  // ── Auth request config ───────────────────────────────────────────────────
  // DO NOT add redirectUri here.
  // The library computes it automatically per platform:
  //   Android native → com.greenchain.app:/oauthredirect  (matches Android OAuth client)
  // Overriding with greenchain:// sends an invalid_request to Google.
  const authConfig = {
    androidClientId: ANDROID_CLIENT_ID,   // undefined if unset → library falls back to clientId
    webClientId:     WEB_CLIENT_ID,
    scopes:          SCOPES,
  };

  const [request, response, _promptAsync] = Google.useAuthRequest(authConfig);

  if (GOOGLE_AUTH_DEBUG) {
    if (request?.redirectUri) {
      // For Android native builds this should be: com.greenchain.app:/oauthredirect
      console.log('[GoogleOAuth] redirectUri:', request.redirectUri);
    }
    if (request?.url) {
      // Full authorization URL — never contains secrets.
      console.log('[GoogleOAuth] request.url:', request.url);
    }
  }

  // ── In-app config error ───────────────────────────────────────────────────
  // Populated when the OAuth request cannot be built (e.g. clientId resolved to empty).
  // Callers should display this string in the UI BEFORE invoking promptAsync,
  // so the user sees a clear message rather than a Google "missing client_id" page.
  //
  // Possible causes:
  //   - EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID not set in .env (caught by the guard above)
  //   - EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID blank AND WEB_CLIENT_ID also blank
  //   - expo start was not restarted with --clear after .env change
  const configError: string | null = (() => {
    // request is null while the hook is still loading — not an error yet.
    // request === null after loading means clientId / redirect could not be resolved.
    if (request === null && !WEB_CLIENT_ID) {
      return 'Google OAuth is not configured. EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID is missing.';
    }
    return null;
  })();

  // ── Wrapped promptAsync with lifecycle logs ───────────────────────────────
  const promptAsync: typeof _promptAsync = async (options) => {
    // Surface config error before opening the browser — avoids the "missing client_id" page.
    if (configError) {
      if (GOOGLE_AUTH_DEBUG) console.log(`[GoogleOAuth] promptAsync blocked — configError: ${configError}`);
      // Return a structured error so callers can handle it uniformly.
      return { type: 'error', error: { code: 'config_error', message: configError } } as any;
    }

    if (GOOGLE_AUTH_DEBUG) {
      console.log('[GoogleOAuth] authorizationRequestStarted');
    }
    try {
      const result = await _promptAsync(options ?? {});
      if (GOOGLE_AUTH_DEBUG) {
        if (result.type === 'success') {
          console.log('[GoogleOAuth] authorizationResponseReceived — type: success (token hidden)');
        } else {
          console.log(`[GoogleOAuth] authorizationResponseReceived — type: ${result.type}`);
        }
        if (result.type === 'error') {
          console.log(`[GoogleOAuth] authorizationError: ${JSON.stringify((result as any).error ?? result)}`);
        }
      }
      return result;
    } catch (err) {
      if (GOOGLE_AUTH_DEBUG) {
        console.log(`[GoogleOAuth] authorizationError (exception): ${String(err)}`);
      }
      throw err;
    }
  };

  return { request, response, promptAsync, configError };
}

// ── Helper: exchange AuthSession response for GreenChain session ──────────────
//
// Call this inside a useEffect watching `response` from useGoogleAuth().
//
// Returns a GoogleLoginResult — never throws.

export async function handleGoogleAuthResponse(
  response: AuthSessionResult | null,
): Promise<GoogleLoginResult> {
  if (!response) return { type: 'cancelled' };

  if (response.type === 'cancel' || response.type === 'dismiss') {
    return { type: 'cancelled' };
  }

  if (response.type !== 'success') {
    if (GOOGLE_AUTH_DEBUG) {
      console.log('[GoogleOAuth] handleResponse — type:', response.type);
    }
    return { type: 'error', message: 'Google sign-in was not successful. Please try again.' };
  }

  const { authentication } = response;
  if (!authentication?.accessToken) {
    if (GOOGLE_AUTH_DEBUG) {
      console.log('[GoogleOAuth] handleResponse — no access token in response');
    }
    return { type: 'error', message: 'No access token received from Google.' };
  }

  if (GOOGLE_AUTH_DEBUG) {
    // Log that a token was received — NEVER log the token value
    console.log('[GoogleOAuth] Access token received (value hidden). Calling backend.');
  }

  return callGoogleLogin(authentication.accessToken);
}

// ── Backend call: POST /auth/google/login ─────────────────────────────────────
//
// Sends the access token to the backend for verification.
// Backend calls Google userinfo API — we never store the token.

export async function callGoogleLogin(accessToken: string): Promise<GoogleLoginResult> {
  try {
    const resp = await fetch(`${API_BASE_URL}/auth/google/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ google_access_token: accessToken }),
    });

    if (resp.ok) {
      const data: GoogleLoginSuccessResult = await resp.json();
      return { type: 'success', data };
    }

    if (resp.status === 404) {
      const body = await resp.json();
      const detail = body?.detail ?? {};
      if (detail.needs_registration) {
        return {
          type: 'needs_registration',
          data: {
            needs_registration: true,
            name: detail.name ?? '',
            email: detail.email ?? '',
            google_sub: detail.google_sub ?? '',
            profile_photo_url: detail.profile_photo_url,
          },
        };
      }
    }

    const errBody = await resp.json().catch(() => ({}));
    return {
      type: 'error',
      message: errBody?.detail ?? `Google login failed (HTTP ${resp.status})`,
    };
  } catch (err) {
    if (GOOGLE_AUTH_DEBUG) {
      console.log('[GoogleOAuth] Network error during login call');
    }
    return { type: 'error', message: 'Network error. Please check your connection.' };
  }
}

// ── Backend call: POST /auth/google/register ──────────────────────────────────

export async function callGoogleRegister(params: {
  accessToken: string;
  name: string;
  email: string;
  role: string;
}): Promise<{ success: true; user: any } | { success: false; message: string }> {
  try {
    const resp = await fetch(`${API_BASE_URL}/auth/google/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        google_access_token: params.accessToken,
        name: params.name,
        email: params.email,
        role: params.role,
      }),
    });

    if (resp.status === 201) {
      const user = await resp.json();
      return { success: true, user };
    }

    const body = await resp.json().catch(() => ({}));
    return { success: false, message: body?.detail ?? `Registration failed (HTTP ${resp.status})` };
  } catch {
    return { success: false, message: 'Network error. Please check your connection.' };
  }
}

// ── Google userinfo helper (for optional client-side use) ─────────────────────
//
// Call this ONLY if the mobile app needs to display the user's name/picture
// before calling the backend. The token is not stored by this function.

export async function getGoogleUserInfo(accessToken: string): Promise<GoogleUserInfo | null> {
  try {
    const resp = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!resp.ok) return null;
    return (await resp.json()) as GoogleUserInfo;
  } catch {
    return null;
  }
}

// ── Google Drive file listing helper ─────────────────────────────────────────
//
// Lists recent files from Drive that GreenChain can import (images, PDF, video, CSV).
// accessToken is used only for this request and must not be stored.

const DRIVE_SUPPORTED_MIMES = [
  'image/jpeg',
  'image/png',
  'image/webp',
  'application/pdf',
  'video/mp4',
  'text/csv',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
].join(' or mimeType=');

export interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  size?: string;
}

export async function fetchDriveFiles(accessToken: string): Promise<DriveFile[]> {
  try {
    const q = encodeURIComponent(
      `(mimeType='${DRIVE_SUPPORTED_MIMES}') and trashed=false`,
    );
    const resp = await fetch(
      `https://www.googleapis.com/drive/v3/files?q=${q}&orderBy=modifiedTime+desc&pageSize=30&fields=files(id,name,mimeType,size)`,
      {
        headers: { Authorization: `Bearer ${accessToken}` },
      },
    );
    if (!resp.ok) return [];
    const body = await resp.json();
    return (body.files ?? []) as DriveFile[];
  } catch {
    return [];
  }
}
