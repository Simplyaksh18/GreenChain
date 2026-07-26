/**
 * FPOFarmsStack — nested stack for Farmers tab in FPO.
 * FPOFarmers (root) → FPOFarmerRegistry → FPOFarmerDetail
 *                   → FPOFarmRegistry  (all farms with lifecycle actions)
 *                   → FPOMint
 *
 * Phase 13/14 additions:
 *   FPOEvidence    — evidence list for a farm (FPO view)
 *   AddEvidence    — upload evidence (camera / gallery / file)
 *   FPOMrvImport   — MRV Import Center (CSV + GeoJSON)
 */
import React from 'react';
import { TouchableOpacity } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { FPOFarmersScreen } from '../screens/fpo/FPOFarmersScreen';
import { FPOFarmsScreen } from '../screens/fpo/FPOFarmsScreen';
import { FPOFarmRegistryScreen } from '../screens/fpo/FPOFarmRegistryScreen';
import { FPOFarmerRegistryScreen } from '../screens/fpo/FPOFarmerRegistryScreen';
import { FPOFarmerDetailScreen } from '../screens/fpo/FPOFarmerDetailScreen';
// Phase 13 — Evidence (re-used from farmer screens)
import { EvidenceListScreen } from '../screens/farmer/EvidenceListScreen';
// Phase 14 — Add Evidence + MRV Import (shared screens)
import { AddEvidenceScreen } from '../screens/shared/AddEvidenceScreen';
import { MrvImportScreen } from '../screens/shared/MrvImportScreen';
import type { FPOFarmerSummary } from '../api/fpoApi';

export type FPOFarmsStackParamList = {
  FPOFarmers: undefined;
  FPOFarms: undefined;
  FPOFarmRegistry: undefined;
  FPOFarmerRegistry: undefined;
  FPOFarmerDetail: { farmer: FPOFarmerSummary };
  // Phase 13/14 — Evidence & MRV Import
  FPOEvidenceList: { farmId: number; farmName: string };
  FPOAddEvidence:  { farmId: number; farmName: string; cropCycleId?: number };
  FPOMrvImport:    { farmId: number; farmName: string; cropCycleId?: number };
};

const Stack = createNativeStackNavigator<FPOFarmsStackParamList>();

export function FPOFarmsStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#1565c0' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: 'bold' },
        headerBackTitle: 'Back',
      }}
    >
      <Stack.Screen
        name="FPOFarmers"
        component={FPOFarmersScreen}
        options={({ navigation }) => ({
          title: 'Farmers & Farms',
          headerRight: () => (
            <TouchableOpacity
              onPress={() => navigation.navigate('FPOFarmRegistry')}
              style={{ marginRight: 4, padding: 4 }}
            >
              <MaterialCommunityIcons name="home-group" size={24} color="#fff" />
            </TouchableOpacity>
          ),
        })}
      />
      <Stack.Screen
        name="FPOFarms"
        component={FPOFarmsScreen}
        options={{ title: 'Linked Farms' }}
      />
      <Stack.Screen
        name="FPOFarmRegistry"
        component={FPOFarmRegistryScreen}
        options={{ title: 'Farm Registry' }}
      />
      <Stack.Screen
        name="FPOFarmerRegistry"
        component={FPOFarmerRegistryScreen}
        options={{ title: 'Farmer Registry' }}
      />
      <Stack.Screen
        name="FPOFarmerDetail"
        component={FPOFarmerDetailScreen}
        options={({ route }) => ({ title: route.params.farmer.name })}
      />

      {/* Phase 13 — Evidence list (read-only FPO view) */}
      <Stack.Screen
        name="FPOEvidenceList"
        component={EvidenceListScreen}
        options={({ route }) => ({ title: `Evidence — ${route.params.farmName}` })}
      />

      {/* Phase 14 — Add Evidence (camera / gallery / file) */}
      <Stack.Screen
        name="FPOAddEvidence"
        component={AddEvidenceScreen}
        options={{ title: 'Add Evidence' }}
      />

      {/* Phase 14 — MRV Import Center */}
      <Stack.Screen
        name="FPOMrvImport"
        component={MrvImportScreen}
        options={{ title: 'MRV Import Center' }}
      />
    </Stack.Navigator>
  );
}
