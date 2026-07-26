/**
 * FarmerCreditsStack — Phase 9
 *
 * Wraps the credit balance and payout details screens for farmers.
 * Bottom tab shows "My Carbon Credits".
 * Within this stack: CreditBalanceScreen (root) → PayoutDetailsScreen (nested)
 */
import React from "react";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { TouchableOpacity } from "react-native";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";

import { CreditBalanceScreen } from "../screens/farmer/CreditBalanceScreen";
import { PayoutDetailsScreen } from "../screens/farmer/PayoutDetailsScreen";
import { CreditDetailScreen } from "../screens/farmer/CreditDetailScreen";
import type { FarmerCreditBalance } from "../types";

export type FarmerCreditsStackParamList = {
  CreditBalance: undefined;
  PayoutDetails: undefined;
  CreditDetail: { balance: FarmerCreditBalance };
};

const Stack = createNativeStackNavigator<FarmerCreditsStackParamList>();

export function FarmerCreditsStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: true,
        headerStyle: { backgroundColor: "#2e7d32" },
        headerTintColor: "#fff",
        headerTitleStyle: { fontWeight: "bold" },
      }}
    >
      <Stack.Screen
        name="CreditBalance"
        component={CreditBalanceScreen}
        options={({ navigation }) => ({
          title: "My Carbon Credits",
          headerRight: () => (
            <TouchableOpacity
              onPress={() => navigation.navigate("PayoutDetails")}
              style={{ marginRight: 4 }}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <MaterialCommunityIcons
                name="bank-outline"
                size={22}
                color="#fff"
              />
            </TouchableOpacity>
          ),
        })}
      />
      <Stack.Screen
        name="PayoutDetails"
        component={PayoutDetailsScreen}
        options={{ title: "Payout Details" }}
      />
      <Stack.Screen
        name="CreditDetail"
        component={CreditDetailScreen}
        options={{ title: "Credit Detail" }}
      />
    </Stack.Navigator>
  );
}
