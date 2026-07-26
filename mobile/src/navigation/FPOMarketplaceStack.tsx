/**
 * FPOMarketplaceStack — Phase 16
 * Navigator for the FPO Marketplace tab.
 *
 * FPOListings (root) — all listings for this FPO
 *   → FPOCreateListing       — create new listing from tokenized balance
 *   → FPOListingDetail        — manage orders for a listing
 *     → FPOBuyerOrders        — all orders (shortcut to retire flow)
 *     → FPORetirementCertificate — view/share certificate
 */
import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { FPOListingsScreen } from '../screens/fpo/FPOListingsScreen';
import { CreateListingScreen } from '../screens/fpo/CreateListingScreen';
import { ListingDetailScreen } from '../screens/fpo/ListingDetailScreen';
import { BuyerOrdersScreen } from '../screens/fpo/BuyerOrdersScreen';
import { RetirementCertificateScreen } from '../screens/fpo/RetirementCertificateScreen';

export type FPOMarketplaceStackParamList = {
  FPOListings: undefined;
  FPOCreateListing: undefined;
  FPOListingDetail: { listingId: number };
  FPOBuyerOrders: { listingId: number; listingCredits: number };
  FPORetirementCertificate: { orderId: number };
};

const Stack = createNativeStackNavigator<FPOMarketplaceStackParamList>();

export function FPOMarketplaceStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#1b5e20' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: 'bold' },
        headerBackTitle: 'Back',
      }}
    >
      <Stack.Screen
        name="FPOListings"
        component={FPOListingsScreen}
        options={{ title: 'Marketplace' }}
      />
      <Stack.Screen
        name="FPOCreateListing"
        component={CreateListingScreen}
        options={{ title: 'Create Listing' }}
      />
      <Stack.Screen
        name="FPOListingDetail"
        component={ListingDetailScreen}
        options={{ title: 'Listing Detail' }}
      />
      <Stack.Screen
        name="FPOBuyerOrders"
        component={BuyerOrdersScreen}
        options={{ title: 'Buyer Orders' }}
      />
      <Stack.Screen
        name="FPORetirementCertificate"
        component={RetirementCertificateScreen}
        options={{ title: 'Retirement Certificate' }}
      />
    </Stack.Navigator>
  );
}
