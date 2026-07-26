/**
 * Axios HTTP client for GreenChain API.
 *
 * - Reads base URL from EXPO_PUBLIC_API_BASE_URL
 * - Automatically attaches Bearer token from the auth store
 * - On 401 response → triggers logout via authStore
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import * as SecureStore from 'expo-secure-store';

const RAW_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://192.168.1.10:8000';

/**
 * Validate the configured API base URL against the current build channel.
 *
 * Rules:
 *   - dev builds may use any URL (including http://LAN-IP:port for local backend)
 *   - preview / production builds must use HTTPS (Play Store / OTA installs
 *     cannot reach a LAN IP, and cleartext HTTP is blocked by default on
 *     modern Android network security config)
 *
 * Bad values in dev only log a warning; bad values in preview/production
 * still return the URL (so the app boots), but log a loud error and expose
 * `apiBaseUrlWarning` so a developer surface can display the mistake.
 */
function validateBaseUrl(url: string): { url: string; warning: string | null } {
  const isDev = __DEV__;
  if (!url) {
    return {
      url,
      warning: 'EXPO_PUBLIC_API_BASE_URL is not set — API calls will fail.',
    };
  }
  if (isDev) return { url, warning: null };

  const lower = url.toLowerCase();
  const isHttps = lower.startsWith('https://');
  const looksLan =
    /\/\/(localhost|127\.0\.0\.1|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(lower);

  if (!isHttps) {
    const msg = 'API base URL must use HTTPS in preview/production builds.';
    // eslint-disable-next-line no-console
    console.error(`[apiClient] ${msg} Got: ${url}`);
    return { url, warning: msg };
  }
  if (looksLan) {
    const msg = 'API base URL points to a LAN/localhost address — not reachable outside dev.';
    // eslint-disable-next-line no-console
    console.error(`[apiClient] ${msg} Got: ${url}`);
    return { url, warning: msg };
  }
  return { url, warning: null };
}

const { url: BASE_URL, warning: apiBaseUrlWarning } = validateBaseUrl(RAW_BASE_URL);

export { BASE_URL, apiBaseUrlWarning };
export const TOKEN_KEY = 'greenchain_jwt';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 15_000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Request interceptor: attach stored JWT ──────────────────────────────────
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const token = await SecureStore.getItemAsync(TOKEN_KEY);
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// ── Response interceptor: handle 401 ───────────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Clear the stored token so next app launch forces re-login
      await SecureStore.deleteItemAsync(TOKEN_KEY);
      // The navigator will redirect to Login once the auth store reflects unauthenticated
      // (handled in RootNavigator via the store's user becoming null)
    }
    return Promise.reject(error);
  },
);

export default apiClient;
