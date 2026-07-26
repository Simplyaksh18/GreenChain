import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { FarmerDashboardScreen } from '../screens/farmer/FarmerDashboardScreen';
import { ProfileScreen } from '../screens/shared/ProfileScreen';
import { FarmerFarmsStack } from './FarmerFarmsStack';
import { FarmerReportsStack } from './FarmerReportsStack';
import { FarmerCreditsStack } from './FarmerCreditsStack';
import { BuyerMarketplaceStack } from './BuyerMarketplaceStack';

export type FarmerTabParamList = {
  Dashboard: undefined;
  Farms: undefined;
  Reports: undefined;
  Credits: undefined;
  Market: undefined;
  Profile: undefined;
};

const Tab = createBottomTabNavigator<FarmerTabParamList>();

export function FarmerTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ color, size }) => {
          const icons: Record<string, keyof typeof MaterialCommunityIcons.glyphMap> = {
            Dashboard: 'view-dashboard-outline',
            Farms: 'home-outline',
            Reports: 'file-chart-outline',
            Credits: 'leaf-circle-outline',
            Market: 'storefront-outline',
            Profile: 'account-outline',
          };
          return <MaterialCommunityIcons name={icons[route.name]} size={size} color={color} />;
        },
        tabBarActiveTintColor: '#2e7d32',
        tabBarInactiveTintColor: '#9e9e9e',
        headerShown: true,
        headerStyle: { backgroundColor: '#2e7d32' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: 'bold' },
      })}
    >
      <Tab.Screen name="Dashboard" component={FarmerDashboardScreen} options={{ title: 'Dashboard' }} />
      <Tab.Screen name="Farms" component={FarmerFarmsStack} options={{ title: 'My Farms', headerShown: false }} />
      <Tab.Screen name="Reports" component={FarmerReportsStack} options={{ title: 'Carbon Reports', headerShown: false }} />
      <Tab.Screen name="Credits" component={FarmerCreditsStack} options={{ title: 'My Carbon Credits', headerShown: false }} />
      <Tab.Screen name="Market" component={BuyerMarketplaceStack} options={{ title: 'Marketplace', headerShown: false }} />
      <Tab.Screen name="Profile" component={ProfileScreen} options={{ title: 'Profile' }} />
    </Tab.Navigator>
  );
}
