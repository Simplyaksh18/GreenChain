import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { FPODashboardScreen } from '../screens/fpo/FPODashboardScreen';
import { ProfileScreen } from '../screens/shared/ProfileScreen';
import { FPOWalletScreen } from '../screens/fpo/FPOWalletScreen';
import { FPOFarmsStack } from './FPOFarmsStack';
import { FPOCreditsStack } from './FPOCreditsStack';
import { FPOMintStack } from './FPOMintStack';
import { FPOMarketplaceStack } from './FPOMarketplaceStack';

export type FPOTabParamList = {
  Dashboard: undefined;
  Farmers: undefined;
  Mint: undefined;
  Credits: undefined;
  Marketplace: undefined;
  Wallet: undefined;
  Profile: undefined;
};

const Tab = createBottomTabNavigator<FPOTabParamList>();

export function FPOTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ color, size }) => {
          const icons: Record<string, keyof typeof MaterialCommunityIcons.glyphMap> = {
            Dashboard: 'view-dashboard-outline',
            Farmers: 'account-group-outline',
            Mint: 'certificate-outline',
            Credits: 'account-cash-outline',
            Marketplace: 'tag-outline',
            Wallet: 'wallet-outline',
            Profile: 'account-outline',
          };
          return <MaterialCommunityIcons name={icons[route.name]} size={size} color={color} />;
        },
        tabBarActiveTintColor: '#1565c0',
        tabBarInactiveTintColor: '#9e9e9e',
        headerShown: true,
        headerStyle: { backgroundColor: '#1565c0' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: 'bold' },
      })}
    >
      <Tab.Screen name="Dashboard" component={FPODashboardScreen} options={{ title: 'FPO Dashboard' }} />
      <Tab.Screen name="Farmers" component={FPOFarmsStack} options={{ title: 'Farmers & Farms', headerShown: false }} />
      <Tab.Screen name="Mint" component={FPOMintStack} options={{ title: 'Mint Credits', headerShown: false }} />
      <Tab.Screen name="Credits" component={FPOCreditsStack} options={{ title: 'Farmer Credits', headerShown: false }} />
      <Tab.Screen name="Marketplace" component={FPOMarketplaceStack} options={{ title: 'Marketplace', headerShown: false }} />
      <Tab.Screen name="Wallet" component={FPOWalletScreen} options={{ title: 'Vault Wallet' }} />
      <Tab.Screen name="Profile" component={ProfileScreen} options={{ title: 'Profile' }} />
    </Tab.Navigator>
  );
}
