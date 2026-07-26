/**
 * BuyerMarketplaceStack — Phase 22B buyer navigation.
 *
 * Not a role — this stack is exposed to any authenticated user through the
 * Farmer tab bar (farmers currently double as buyers in the MVP model).
 */
import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { MarketplaceBrowseScreen } from '../screens/buyer/MarketplaceBrowseScreen';
import { MarketplaceListingDetailScreen } from '../screens/buyer/MarketplaceListingDetailScreen';
import { MyMarketplaceOrdersScreen } from '../screens/buyer/MyMarketplaceOrdersScreen';
import { BuyerRetirementCertificateScreen } from '../screens/buyer/BuyerRetirementCertificateScreen';

export type BuyerMarketplaceStackParamList = {
  BuyerMarketplaceBrowse: undefined;
  BuyerMarketplaceListingDetail: { listingId: number };
  BuyerMyOrders: undefined;
  BuyerRetirementCertificate: { orderId: number };
};

const Stack = createNativeStackNavigator<BuyerMarketplaceStackParamList>();

export function BuyerMarketplaceStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#2e7d32' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: 'bold' },
      }}
    >
      <Stack.Screen
        name="BuyerMarketplaceBrowse"
        component={MarketplaceBrowseScreen}
        options={({ navigation }) => ({
          title: 'Marketplace',
          headerRight: () => (
            <HeaderMyOrdersButton onPress={() => navigation.navigate('BuyerMyOrders')} />
          ),
        })}
      />
      <Stack.Screen
        name="BuyerMarketplaceListingDetail"
        component={MarketplaceListingDetailScreen}
        options={{ title: 'Listing Details' }}
      />
      <Stack.Screen
        name="BuyerMyOrders"
        component={MyMarketplaceOrdersScreen}
        options={{ title: 'My Purchases' }}
      />
      <Stack.Screen
        name="BuyerRetirementCertificate"
        component={BuyerRetirementCertificateScreen}
        options={{ title: 'Certificate' }}
      />
    </Stack.Navigator>
  );
}

// Small header button — kept in this file to avoid inflating shared components.
import { TouchableOpacity } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';

function HeaderMyOrdersButton({ onPress }: { onPress: () => void }) {
  return (
    <TouchableOpacity
      onPress={onPress}
      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      style={{ marginRight: 4 }}
    >
      <MaterialCommunityIcons name="cart-outline" size={22} color="#fff" />
    </TouchableOpacity>
  );
}
