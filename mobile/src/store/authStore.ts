/**
 * Auth store — Phase 9A
 *
 * Persists the JWT to expo-secure-store so the session survives app restarts.
 * The store exposes:
 *   token         — raw JWT string
 *   user          — User object from /users/me
 *   isLoading     — true while loadSession() is running
 *   login()       — store token, fetch user profile
 *   logout()      — wipe token + user
 *   loadSession() — on app boot, try to restore session from SecureStore
 *   refreshUser() — re-fetch /users/me and update user in store (for profile freshness)
 */
import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';

import { TOKEN_KEY } from '../api/client';
import { getMeApi } from '../api/authApi';
import type { User } from '../types';

interface AuthState {
  token: string | null;
  user: User | null;
  isLoading: boolean;

  login: (token: string) => Promise<void>;
  logout: () => Promise<void>;
  loadSession: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  isLoading: true,

  login: async (token: string) => {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
    const user = await getMeApi();
    set({ token, user, isLoading: false });
  },

  logout: async () => {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    set({ token: null, user: null, isLoading: false });
  },

  loadSession: async () => {
    set({ isLoading: true });
    try {
      const stored = await SecureStore.getItemAsync(TOKEN_KEY);
      if (stored) {
        const user = await getMeApi();
        set({ token: stored, user, isLoading: false });
      } else {
        set({ isLoading: false });
      }
    } catch {
      // Token invalid / network error → clear and show login
      await SecureStore.deleteItemAsync(TOKEN_KEY);
      set({ token: null, user: null, isLoading: false });
    }
  },

  /**
   * Re-fetch /users/me and update the stored user object.
   * Call this from ProfileScreen on mount so the name always reflects
   * the latest value from the backend (e.g. after a PATCH /users/me).
   */
  refreshUser: async () => {
    try {
      const user = await getMeApi();
      set({ user });
    } catch {
      // Silently ignore — stale cached user is still usable
    }
  },
}));
