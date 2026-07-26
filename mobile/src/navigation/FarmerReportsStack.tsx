/**
 * FarmerReportsStack — nested stack for Carbon Reports tab.
 * CarbonReports → CarbonReportDetail
 */
import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { CarbonReportsScreen } from '../screens/farmer/CarbonReportsScreen';
import { CarbonReportDetailScreen } from '../screens/farmer/CarbonReportDetailScreen';

export type FarmerReportsParamList = {
  CarbonReports: undefined;
  CarbonReportDetail: { reportId: number };
};

const Stack = createNativeStackNavigator<FarmerReportsParamList>();

export function FarmerReportsStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#2e7d32' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: 'bold' },
        headerBackTitle: 'Reports',
      }}
    >
      <Stack.Screen
        name="CarbonReports"
        component={CarbonReportsScreen}
        options={{ title: 'Carbon Reports' }}
      />
      <Stack.Screen
        name="CarbonReportDetail"
        component={CarbonReportDetailScreen}
        options={{ title: 'Report Detail' }}
      />
    </Stack.Navigator>
  );
}
