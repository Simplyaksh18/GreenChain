import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { VerifierDashboardScreen } from '../screens/verifier/VerifierDashboardScreen';
import { ProfileScreen } from '../screens/shared/ProfileScreen';
import { VerifierStack } from './VerifierStack';

export type VerifierTabParamList = {
  Dashboard: undefined;
  Pending: undefined;
  Profile: undefined;
};

const Tab = createBottomTabNavigator<VerifierTabParamList>();

export function VerifierTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ color, size }) => {
          const icons: Record<string, keyof typeof MaterialCommunityIcons.glyphMap> = {
            Dashboard: 'view-dashboard-outline',
            Pending: 'clipboard-check-outline',
            Profile: 'account-outline',
          };
          return <MaterialCommunityIcons name={icons[route.name]} size={size} color={color} />;
        },
        tabBarActiveTintColor: '#6a1b9a',
        tabBarInactiveTintColor: '#9e9e9e',
        headerShown: true,
        headerStyle: { backgroundColor: '#6a1b9a' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: 'bold' },
      })}
    >
      <Tab.Screen name="Dashboard" component={VerifierDashboardScreen} options={{ title: 'Verifier Dashboard' }} />
      <Tab.Screen name="Pending" component={VerifierStack} options={{ title: 'Pending Reviews', headerShown: false }} />
      <Tab.Screen name="Profile" component={ProfileScreen} options={{ title: 'Profile' }} />
    </Tab.Navigator>
  );
}
