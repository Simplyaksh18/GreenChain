import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { AdminDashboardScreen } from '../screens/admin/AdminDashboardScreen';
import { RiskReportsScreen } from '../screens/admin/RiskReportsScreen';
import { TokenSummaryScreen } from '../screens/admin/TokenSummaryScreen';
import { SystemStatusScreen } from '../screens/admin/SystemStatusScreen';
import { ProfileScreen } from '../screens/shared/ProfileScreen';

export type AdminTabParamList = {
  Dashboard: undefined;
  RiskReports: undefined;
  Tokens: undefined;
  System: undefined;
  Profile: undefined;
};

const Tab = createBottomTabNavigator<AdminTabParamList>();

export function AdminTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ color, size }) => {
          const icons: Record<string, keyof typeof MaterialCommunityIcons.glyphMap> = {
            Dashboard: 'view-dashboard-outline',
            RiskReports: 'alert-circle-outline',
            Tokens: 'certificate-outline',
            System: 'cog-outline',
            Profile: 'account-outline',
          };
          return <MaterialCommunityIcons name={icons[route.name]} size={size} color={color} />;
        },
        tabBarActiveTintColor: '#bf360c',
        tabBarInactiveTintColor: '#9e9e9e',
        headerShown: true,
        headerStyle: { backgroundColor: '#bf360c' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: 'bold' },
      })}
    >
      <Tab.Screen name="Dashboard" component={AdminDashboardScreen} options={{ title: 'Admin Dashboard' }} />
      <Tab.Screen name="RiskReports" component={RiskReportsScreen} options={{ title: 'Risk Reports' }} />
      <Tab.Screen name="Tokens" component={TokenSummaryScreen} options={{ title: 'Token Summary' }} />
      <Tab.Screen name="System" component={SystemStatusScreen} options={{ title: 'System Status' }} />
      <Tab.Screen name="Profile" component={ProfileScreen} options={{ title: 'Profile' }} />
    </Tab.Navigator>
  );
}
