/**
 * FPOMintStack — dedicated navigator for the FPO Mint tab.
 *
 * MintQueue   (root) — VERIFIED reports ready to mint
 *   header-right: cash-fast icon → Payouts  (mirrors Farm Registry pattern)
 * MintHistory         — audit trail of all minted tokens
 * Payouts             — initiate and review payouts (InitiatePayoutScreen reused)
 */
import React from 'react';
import { TouchableOpacity } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { FPOMintScreen } from '../screens/fpo/FPOMintScreen';
import { FPOMintHistoryScreen } from '../screens/fpo/FPOMintHistoryScreen';
import { InitiatePayoutScreen } from '../screens/fpo/InitiatePayoutScreen';

export type FPOMintStackParamList = {
  MintQueue: undefined;
  MintHistory: undefined;
  Payouts: undefined;
};

const Stack = createNativeStackNavigator<FPOMintStackParamList>();

export function FPOMintStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#1565c0' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: 'bold' },
        headerBackTitle: 'Back',
      }}
    >
      <Stack.Screen
        name="MintQueue"
        component={FPOMintScreen}
        options={({ navigation }) => ({
          title: 'Mint Carbon Credits',
          headerRight: () => (
            <TouchableOpacity
              onPress={() => navigation.navigate('Payouts')}
              style={{ marginRight: 4, padding: 4 }}
            >
              <MaterialCommunityIcons name="cash-fast" size={24} color="#fff" />
            </TouchableOpacity>
          ),
        })}
      />
      <Stack.Screen
        name="MintHistory"
        component={FPOMintHistoryScreen}
        options={{ title: 'Mint History' }}
      />
      <Stack.Screen
        name="Payouts"
        component={InitiatePayoutScreen}
        options={{ title: 'Payouts' }}
      />
    </Stack.Navigator>
  );
}
