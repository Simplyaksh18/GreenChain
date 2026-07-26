/**
 * app.config.js — dynamic Expo config overlay
 *
 * Expo merges app.json (static) with this file (dynamic).
 * Use the function form so Expo passes the already-merged static config —
 * we only add what app.json cannot express: env-var injection at build time.
 *
 * Why this file is needed:
 *   expo.android.config.googleMaps.apiKey must be embedded in AndroidManifest.xml
 *   at EAS build time. A static app.json cannot read environment variables.
 *   This function runs during `expo prebuild` / `eas build` and injects the key.
 *
 * Google Maps SDK for Android setup (required before rebuilding the APK):
 *   1. Google Cloud Console → APIs & Services → Library
 *      Enable "Maps SDK for Android"
 *   2. APIs & Services → Credentials → Create API key
 *   3. Restrict key:
 *        Application restrictions → Android apps
 *        Add: package name  com.greenchain.app
 *             SHA-1 fingerprint  (run `eas credentials -p android` to get it)
 *        API restrictions → Maps SDK for Android
 *   4. Paste the key into mobile/.env:
 *        EXPO_PUBLIC_GOOGLE_MAPS_ANDROID_API_KEY=AIza...
 *   5. Rebuild APK:  eas build -p android --profile development
 *
 * Without a valid key, Google Maps tiles fail and GMS throws a fatal exception.
 * With a missing/blank key the JS bundle detects it and shows a friendly message
 * instead of crashing (see FarmMapScreen.tsx).
 */

module.exports = ({ config }) => ({
  ...config,
  android: {
    ...config.android,
    config: {
      ...(config.android?.config ?? {}),
      googleMaps: {
        // Read at EAS build time from the local or CI environment.
        // Empty string → build succeeds; FarmMapScreen shows a graceful error on device.
        apiKey: process.env.EXPO_PUBLIC_GOOGLE_MAPS_ANDROID_API_KEY || '',
      },
    },
  },
});
