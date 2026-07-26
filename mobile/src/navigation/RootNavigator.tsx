/**
 * RootNavigator — Phase 9A++
 *
 * Unauthenticated stack: Login + CreateAccount
 * Authenticated: role-based tab navigators
 *
 * Role is ALWAYS determined from GET /users/me — never inferred from email.
 *   isLoading      → full-screen spinner
 *   !user          → Login / CreateAccount stack
 *   user.role=FARMER   → FarmerTabs
 *   user.role=FPO      → FPOTabs
 *   user.role=VERIFIER → VerifierTabs
 *   user.role=ADMIN    → AdminTabs
 */
import React, { useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { View, StyleSheet } from 'react-native';
import { ActivityIndicator } from 'react-native-paper';

import { useAuthStore } from '../store/authStore';
import { LoginScreen } from '../screens/auth/LoginScreen';
import { CreateAccountScreen } from '../screens/auth/CreateAccountScreen';
import { FarmerTabs } from './FarmerTabs';
import { FPOTabs } from './FPOTabs';
import { VerifierTabs } from './VerifierTabs';
import { AdminTabs } from './AdminTabs';

const Stack = createNativeStackNavigator();

export function RootNavigator() {
  const { user, isLoading, loadSession } = useAuthStore();

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  if (isLoading) {
    return (
      <View style={styles.splash}>
        <ActivityIndicator size="large" color="#2e7d32" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {!user ? (
          // ── Unauthenticated stack ──────────────────────────────────────────
          <>
            <Stack.Screen name="Login" component={LoginScreen} />
            <Stack.Screen
              name="CreateAccount"
              component={CreateAccountScreen}
              options={{ animation: 'slide_from_right' }}
            />
          </>
        ) : user.role === 'FARMER' ? (
          <Stack.Screen name="FarmerTabs" component={FarmerTabs} />
        ) : user.role === 'FPO' ? (
          <Stack.Screen name="FPOTabs" component={FPOTabs} />
        ) : user.role === 'VERIFIER' ? (
          <Stack.Screen name="VerifierTabs" component={VerifierTabs} />
        ) : (
          // ADMIN
          <Stack.Screen name="AdminTabs" component={AdminTabs} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  splash: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f5f9f5',
  },
});
