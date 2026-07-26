/**
 * Feature flags — controlled via EXPO_PUBLIC_* env vars.
 *
 * Google OAuth is temporarily disabled while SHA-1 / Google Console
 * redirect URI configuration is being resolved.
 * Set EXPO_PUBLIC_GOOGLE_AUTH_ENABLED=true to re-enable.
 *
 * Do NOT delete OAuth code — only hide UI behind this flag.
 */

export const GOOGLE_AUTH_ENABLED =
  process.env.EXPO_PUBLIC_GOOGLE_AUTH_ENABLED === 'true';
