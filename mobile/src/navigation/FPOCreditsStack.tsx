/**
 * FPOCreditsStack — Phase 10A
 *
 * Stack navigator for FPO Credit Balance screens:
 *   FarmerCreditBalancesScreen (list) → CreditBalanceDetailScreen (detail)
 */
import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import type { EnrichedFarmerCreditBalance } from '../types';

import { FarmerCreditBalancesScreen } from '../screens/fpo/FarmerCreditBalancesScreen';
import { CreditBalanceDetailScreen } from '../screens/fpo/CreditBalanceDetailScreen';
import { InitiatePayoutScreen } from '../screens/fpo/InitiatePayoutScreen';

export type FPOCreditsStackParamList = {
  FarmerCreditBalances: undefined;
  CreditBalanceDetail: { balance: EnrichedFarmerCreditBalance };
  InitiatePayout: {
    farmer_id: number;
    balance_id: number;
    credits_available: number;
    farmer_name: string;
  };
};

const Stack = createNativeStackNavigator<FPOCreditsStackParamList>();

export function FPOCreditsStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: true,
        headerStyle: { backgroundColor: '#1565c0' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: 'bold' },
      }}
    >
      <Stack.Screen
        name="FarmerCreditBalances"
        component={FarmerCreditBalancesScreen}
        options={{ title: 'Farmer Credits' }}
      />
      <Stack.Screen
        name="CreditBalanceDetail"
        component={CreditBalanceDetailScreen}
        options={{ title: 'Credit Balance Detail' }}
      />
      <Stack.Screen
        name="InitiatePayout"
        component={InitiatePayoutScreen}
        options={{ title: 'Initiate Payout' }}
      />
    </Stack.Navigator>
  );
}
