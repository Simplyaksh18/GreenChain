/**
 * FarmerFarmsStack — nested stack navigator for the Farms tab.
 * Manages: MyFarms → AddFarm
 *          MyFarms → FarmDetail → SensorReadings / SatelliteDrone
 *                               → CreateCropCycle
 *                               → CropCycleDetail (new Phase 9C)
 */
import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { MyFarmsScreen } from '../screens/farmer/MyFarmsScreen';
import { AddFarmScreen } from '../screens/farmer/AddFarmScreen';
import { FarmDetailScreen } from '../screens/farmer/FarmDetailScreen';
import { SensorReadingsScreen } from '../screens/farmer/SensorReadingsScreen';
import { SatelliteDroneScreen } from '../screens/farmer/SatelliteDroneScreen';
import { CreateCropCycleScreen } from '../screens/farmer/CreateCropCycleScreen';
import { CropCycleDetailScreen } from '../screens/farmer/CropCycleDetailScreen';
import { EditCropCycleScreen } from '../screens/farmer/EditCropCycleScreen';
import { ManualSensorReadingScreen } from '../screens/farmer/ManualSensorReadingScreen';
import { ManualSatelliteObservationScreen } from '../screens/farmer/ManualSatelliteObservationScreen';
import { ManualDroneObservationScreen } from '../screens/farmer/ManualDroneObservationScreen';
// Phase 12 — GIS screens
import { FarmMapScreen } from '../screens/farmer/FarmMapScreen';
import { BoundaryEditorScreen } from '../screens/farmer/BoundaryEditorScreen';
import { SatelliteInsightsScreen } from '../screens/farmer/SatelliteInsightsScreen';
// Phase 13 — Audit & Evidence
import { EvidenceListScreen } from '../screens/farmer/EvidenceListScreen';
import { FarmAuditScreen } from '../screens/farmer/FarmAuditScreen';
// Phase 14 — Add Evidence + MRV Import (shared screens)
import { AddEvidenceScreen } from '../screens/shared/AddEvidenceScreen';
import { MrvImportScreen } from '../screens/shared/MrvImportScreen';

export type FarmerFarmsParamList = {
  MyFarms: undefined;
  AddFarm: undefined;
  FarmDetail: { farmId: number; farmName: string };
  SensorReadings: { farmId: number; farmName: string };
  SatelliteDrone: { farmId: number; farmName: string };
  CreateCropCycle: { farmId: number; farmName: string };
  CropCycleDetail: { cycleId: number; farmId: number; farmName: string; farmStatus?: string };
  EditCropCycle: { cycleId: number; farmId: number; farmName: string };
  ManualSensorReading: { cycleId: number; farmId: number; farmName: string };
  ManualSatelliteObservation: { cycleId: number; farmId: number; farmName: string };
  ManualDroneObservation: { cycleId: number; farmId: number; farmName: string };
  // Phase 12 — GIS
  FarmMap: { farmId: number; farmName: string };
  BoundaryEditor: { farmId: number; farmName: string };
  SatelliteInsights: { farmId: number; farmName: string };
  // Phase 13 — Audit & Evidence
  EvidenceList: { farmId: number; farmName: string };
  FarmAudit: { farmId: number; farmName: string };
  // Phase 14 — Upload + Import
  AddEvidence: { farmId: number; farmName: string; cropCycleId?: number };
  MrvImport:   { farmId: number; farmName: string; cropCycleId?: number };
};

const Stack = createNativeStackNavigator<FarmerFarmsParamList>();

export function FarmerFarmsStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#2e7d32' },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: 'bold' },
        headerBackTitle: 'Back',
      }}
    >
      <Stack.Screen
        name="MyFarms"
        component={MyFarmsScreen}
        options={{ title: 'My Farms' }}
      />
      <Stack.Screen
        name="AddFarm"
        component={AddFarmScreen}
        options={{ title: 'Register New Farm' }}
      />
      <Stack.Screen
        name="FarmDetail"
        component={FarmDetailScreen}
        options={({ route }) => ({ title: route.params.farmName })}
      />
      <Stack.Screen
        name="SensorReadings"
        component={SensorReadingsScreen}
        options={{ title: 'Sensor Readings' }}
      />
      <Stack.Screen
        name="SatelliteDrone"
        component={SatelliteDroneScreen}
        options={{ title: 'Satellite & Drone' }}
      />
      <Stack.Screen
        name="CreateCropCycle"
        component={CreateCropCycleScreen}
        options={{ title: 'New Crop Cycle' }}
      />
      <Stack.Screen
        name="CropCycleDetail"
        component={CropCycleDetailScreen}
        options={{ title: 'Crop Cycle Detail' }}
      />
      <Stack.Screen
        name="EditCropCycle"
        component={EditCropCycleScreen}
        options={{ title: 'Edit Crop Cycle' }}
      />
      <Stack.Screen
        name="ManualSensorReading"
        component={ManualSensorReadingScreen}
        options={{ title: 'Add Sensor Reading' }}
      />
      <Stack.Screen
        name="ManualSatelliteObservation"
        component={ManualSatelliteObservationScreen}
        options={{ title: 'Add Satellite Observation' }}
      />
      <Stack.Screen
        name="ManualDroneObservation"
        component={ManualDroneObservationScreen}
        options={{ title: 'Add Drone Observation' }}
      />
      {/* Phase 12 — GIS */}
      <Stack.Screen
        name="FarmMap"
        component={FarmMapScreen}
        options={({ route }) => ({ title: route.params.farmName, headerTransparent: false })}
      />
      <Stack.Screen
        name="BoundaryEditor"
        component={BoundaryEditorScreen}
        options={{ title: 'Draw Boundary' }}
      />
      <Stack.Screen
        name="SatelliteInsights"
        component={SatelliteInsightsScreen}
        options={{ title: 'Satellite Insights' }}
      />
      {/* Phase 13 — Audit & Evidence */}
      <Stack.Screen
        name="EvidenceList"
        component={EvidenceListScreen}
        options={({ route }) => ({ title: `Evidence — ${route.params.farmName}` })}
      />
      <Stack.Screen
        name="FarmAudit"
        component={FarmAuditScreen}
        options={{ title: 'Audit Package' }}
      />
      {/* Phase 14 — Evidence upload + MRV Import */}
      <Stack.Screen
        name="AddEvidence"
        component={AddEvidenceScreen}
        options={{ title: 'Add Evidence' }}
      />
      <Stack.Screen
        name="MrvImport"
        component={MrvImportScreen}
        options={{ title: 'MRV Import Center' }}
      />
    </Stack.Navigator>
  );
}
