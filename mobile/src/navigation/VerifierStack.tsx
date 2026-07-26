/**
 * VerifierStack — nested stack navigator for the Pending Reviews tab.
 * PendingReviews → VerificationDetail
 */
import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { PendingReviewsScreen } from '../screens/verifier/PendingReviewsScreen';
import { VerificationDetailScreen } from '../screens/verifier/VerificationDetailScreen';

export type VerifierStackParamList = {
  PendingReviews: undefined;
  VerificationDetail: { verificationId: number };
};

const Stack = createNativeStackNavigator<VerifierStackParamList>();

export function VerifierStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#6a1b9a' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: 'bold' },
        headerBackTitle: 'Back',
      }}
    >
      <Stack.Screen
        name="PendingReviews"
        component={PendingReviewsScreen}
        options={{ title: 'Pending Reviews' }}
      />
      <Stack.Screen
        name="VerificationDetail"
        component={VerificationDetailScreen}
        options={{ title: 'Verification Detail' }}
      />
    </Stack.Navigator>
  );
}
