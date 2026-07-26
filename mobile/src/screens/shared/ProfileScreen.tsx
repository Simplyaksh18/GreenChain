import React, { useEffect } from 'react';
import { ScrollView, StyleSheet, View, Alert, Image } from 'react-native';
import { Text, Divider, List, Button } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAuthStore } from '../../store/authStore';
import { StatusBadge } from '../../components/StatusBadge';
import { GlassCard } from '../../components/GlassCard';
import { RoleBackground } from '../../components/RoleBackground';

const LOGO = require('../../../assets/logo-transparent.png');

const ROLE_COLORS: Record<string, string> = {
  FARMER:   '#2e7d32',
  FPO:      '#1565c0',
  VERIFIER: '#6a1b9a',
  ADMIN:    '#bf360c',
};

const ROLE_LABELS: Record<string, string> = {
  FARMER:   'Farmer',
  FPO:      'FPO Manager',
  VERIFIER: 'Carbon Verifier',
  ADMIN:    'Platform Admin',
};

export function ProfileScreen() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const refreshUser = useAuthStore((s) => s.refreshUser);

  // Re-fetch /users/me on mount — ensures name always reflects latest backend value
  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const handleLogout = () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign Out', style: 'destructive', onPress: () => logout() },
    ]);
  };

  if (!user) return null;

  const roleColor = ROLE_COLORS[user.role] ?? '#333';
  const roleLabel = ROLE_LABELS[user.role] ?? user.role;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <ScrollView contentContainerStyle={styles.scroll}>

          {/* ── Hero / Avatar ─────────────────────────────── */}
          <GlassCard style={styles.heroCard} opacity={0.93}>
            {/* Logo watermark */}
            <Image source={LOGO} style={styles.logoWatermark} resizeMode="contain" />

            <View style={styles.heroInner}>
              <View style={[styles.avatar, { backgroundColor: roleColor }]}>
                <Text style={styles.avatarText}>
                  {user.name.charAt(0).toUpperCase()}
                </Text>
              </View>

              {/* Name — exactly as returned by GET /users/me */}
              <Text variant="headlineSmall" style={styles.name}>{user.name}</Text>
              <Text variant="bodyMedium" style={styles.email}>{user.email}</Text>

              <View style={styles.badgeRow}>
                <View style={[styles.rolePill, { backgroundColor: roleColor }]}>
                  <Text style={styles.rolePillText}>{roleLabel}</Text>
                </View>
                {user.is_approved && (
                  <View style={styles.approvedBadge}>
                    <MaterialCommunityIcons name="check-circle" size={14} color="#2e7d32" />
                    <Text style={styles.approvedText}>Approved</Text>
                  </View>
                )}
              </View>
            </View>
          </GlassCard>

          {/* ── Account Details ──────────────────────────── */}
          <GlassCard style={styles.detailCard} opacity={0.88}>
            <Text variant="titleSmall" style={styles.sectionTitle}>Account Details</Text>
            <Divider style={styles.divider} />

            <List.Item
              title="Account Status"
              description={user.is_active ? 'Active' : 'Inactive'}
              titleStyle={styles.listTitle}
              descriptionStyle={[
                styles.listDesc,
                { color: user.is_active ? '#2e7d32' : '#9e9e9e', fontWeight: '600' },
              ]}
              left={(props) => (
                <List.Icon {...props} icon="account-check-outline"
                  color={user.is_active ? '#2e7d32' : '#9e9e9e'} />
              )}
            />

            <List.Item
              title="Role"
              description={roleLabel}
              titleStyle={styles.listTitle}
              descriptionStyle={styles.listDesc}
              left={(props) => (
                <List.Icon {...props} icon="shield-account-outline" color={roleColor} />
              )}
            />

            <List.Item
              title="Member Since"
              description={new Date(user.created_at).toLocaleDateString('en-IN', {
                day: 'numeric', month: 'long', year: 'numeric',
              })}
              titleStyle={styles.listTitle}
              descriptionStyle={styles.listDesc}
              left={(props) => <List.Icon {...props} icon="calendar-outline" />}
            />
          </GlassCard>

          {/* ── Status Summary ───────────────────────────── */}
          <GlassCard style={styles.statusCard} opacity={0.88}>
            <Text variant="titleSmall" style={styles.sectionTitle}>Status Summary</Text>
            <Divider style={styles.divider} />
            <View style={styles.statusRow}>
              <View style={styles.statusItem}>
                <StatusBadge status={user.role} />
                <Text variant="labelSmall" style={styles.statusItemLabel}>Role</Text>
              </View>
              <View style={styles.statusItem}>
                <StatusBadge status={user.is_active ? 'ACTIVE' : 'INACTIVE'} />
                <Text variant="labelSmall" style={styles.statusItemLabel}>Account</Text>
              </View>
              <View style={styles.statusItem}>
                <StatusBadge status={user.is_approved ? 'APPROVED' : 'PENDING'} />
                <Text variant="labelSmall" style={styles.statusItemLabel}>Approval</Text>
              </View>
            </View>
          </GlassCard>

          {/* ── Sign Out ─────────────────────────────────── */}
          <GlassCard style={styles.logoutCard} opacity={0.90}>
            <Button
              mode="contained"
              onPress={handleLogout}
              icon="logout"
              buttonColor="#D32F2F"
              textColor="#ffffff"
              style={styles.logoutButton}
              contentStyle={styles.logoutContent}
              labelStyle={styles.logoutLabel}
            >
              Sign Out
            </Button>
            <Text variant="labelSmall" style={styles.logoutHint}>
              You will be returned to the login screen
            </Text>
          </GlassCard>

          <Text variant="bodySmall" style={styles.footer}>
            ©️2026 developed by Akshi👩‍💻
          </Text>
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { paddingBottom: 40, paddingTop: 8 },

  // Hero
  heroCard: { marginTop: 8, position: 'relative', overflow: 'hidden' },
  logoWatermark: {
    width: 44, height: 44,
    position: 'absolute', top: 12, right: 12, opacity: 0.18,
    backgroundColor: 'transparent',
  },
  heroInner: { alignItems: 'center', paddingVertical: 8 },
  avatar: {
    width: 84, height: 84, borderRadius: 42,
    alignItems: 'center', justifyContent: 'center',
    marginBottom: 14,
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.18, shadowRadius: 8, elevation: 5,
  },
  avatarText: { fontSize: 38, color: '#fff', fontWeight: '900' },
  name: { fontWeight: '800', marginBottom: 4, color: '#1a1a1a' },
  email: { color: '#555', marginBottom: 14 },
  badgeRow: {
    flexDirection: 'row', gap: 8, alignItems: 'center',
    flexWrap: 'wrap', justifyContent: 'center',
  },
  rolePill: { paddingHorizontal: 14, paddingVertical: 5, borderRadius: 20 },
  rolePillText: { color: '#fff', fontWeight: '700', fontSize: 12 },
  approvedBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: '#e8f5e9', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20,
  },
  approvedText: { fontSize: 12, color: '#2e7d32', fontWeight: '700' },

  // Cards
  detailCard: { marginTop: 8 },
  statusCard: { marginTop: 0 },
  sectionTitle: { fontWeight: '800', color: '#1b5e20', marginBottom: 6 },
  divider: { marginBottom: 4 },
  listTitle: { color: '#333', fontWeight: '600' },
  listDesc: { color: '#666' },

  // Status row
  statusRow: { flexDirection: 'row', justifyContent: 'space-around', paddingVertical: 8 },
  statusItem: { alignItems: 'center', gap: 6 },
  statusItemLabel: { color: '#777' },

  // Logout
  logoutCard: { marginTop: 8, alignItems: 'center' },
  logoutButton: { borderRadius: 12, width: '100%' },
  logoutContent: { height: 52 },
  logoutLabel: { fontSize: 16, fontWeight: '700', letterSpacing: 0.5 },
  logoutHint: { color: '#888', marginTop: 8 },

  footer: { textAlign: 'center', marginTop: 20, color: 'rgba(255,255,255,0.6)' },
});
