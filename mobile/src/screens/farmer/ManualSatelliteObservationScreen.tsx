/**
 * ManualSatelliteObservationScreen — Phase 9C
 * POST /satellite/observations
 */
import React, { useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { Text, TextInput } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { createManualSatelliteObservationApi } from '../../api/observationApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { AppButton } from '../../components/AppButton';
import { DatePickerField } from '../../components/DatePickerField';
import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'ManualSatelliteObservation'>;

type VegHealth = 'POOR' | 'FAIR' | 'GOOD' | 'EXCELLENT';
type FloodRisk = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH';

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export function ManualSatelliteObservationScreen({ navigation, route }: Props) {
  const { cycleId, farmId } = route.params;

  const [obsDate, setObsDate]             = useState(todayISO());
  const [ndvi, setNdvi]                   = useState('');
  const [ndwi, setNdwi]                   = useState('');
  const [vegHealth, setVegHealth]         = useState<VegHealth>('GOOD');
  const [floodRisk, setFloodRisk]         = useState<FloodRisk>('NONE');
  const [cloudCover, setCloudCover]       = useState('');
  const [submitting, setSubmitting]       = useState(false);

  const handleSubmit = async () => {
    const ndviVal = parseFloat(ndvi);
    const ndwiVal = parseFloat(ndwi);
    const cloudVal = cloudCover.trim() ? parseFloat(cloudCover) : 0;

    if (!obsDate) { Alert.alert('Validation', 'Please select an observation date.'); return; }
    if (obsDate > new Date().toISOString().slice(0, 10)) { Alert.alert('Validation', 'Observation date cannot be in the future.'); return; }
    if (isNaN(ndviVal) || ndviVal < -1 || ndviVal > 1) { Alert.alert('Validation', 'NDVI must be between -1 and 1'); return; }
    if (isNaN(ndwiVal) || ndwiVal < -1 || ndwiVal > 1) { Alert.alert('Validation', 'NDWI must be between -1 and 1'); return; }
    if (isNaN(cloudVal) || cloudVal < 0 || cloudVal > 100) { Alert.alert('Validation', 'Cloud cover must be 0–100%'); return; }

    try {
      setSubmitting(true);
      await createManualSatelliteObservationApi({
        farm_id: farmId,
        crop_cycle_id: cycleId,
        observation_date: obsDate,
        ndvi: ndviVal,
        ndwi: ndwiVal,
        vegetation_health: vegHealth,
        flood_risk: floodRisk,
        cloud_cover_percent: cloudVal,
      });
      Alert.alert('Saved', 'Satellite observation recorded.', [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? 'Failed to save observation.';
      Alert.alert('Error', msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <KeyboardAvoidingView
          style={styles.flex}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <ScrollView contentContainerStyle={styles.scroll}>
            <SectionHeader icon="satellite-variant" title="Satellite Observation" light />

            <GlassCard opacity={0.92}>
              <DatePickerField
                label="Observation Date *"
                value={obsDate}
                onChange={setObsDate}
                maxDate={new Date()}
                accentColor="#6a1b9a"
              />
            </GlassCard>

            <SectionHeader icon="leaf-circle-outline" title="Vegetation Indices" light />
            <GlassCard opacity={0.92}>
              <TextInput
                mode="outlined"
                label="NDVI (-1 to 1)"
                value={ndvi}
                onChangeText={setNdvi}
                keyboardType="numeric"
                style={styles.input}
                outlineColor="#9e9e9e"
                activeOutlineColor="#6a1b9a"
              />
              <TextInput
                mode="outlined"
                label="NDWI (-1 to 1)"
                value={ndwi}
                onChangeText={setNdwi}
                keyboardType="numeric"
                style={styles.input}
                outlineColor="#9e9e9e"
                activeOutlineColor="#6a1b9a"
              />
              <TextInput
                mode="outlined"
                label="Cloud Cover % (0–100, optional)"
                value={cloudCover}
                onChangeText={setCloudCover}
                keyboardType="numeric"
                style={styles.input}
                outlineColor="#9e9e9e"
                activeOutlineColor="#6a1b9a"
              />
            </GlassCard>

            <SectionHeader icon="flower-outline" title="Vegetation Health" light />
            <GlassCard opacity={0.92}>
              <ChipGroup
                options={['POOR', 'FAIR', 'GOOD', 'EXCELLENT']}
                selected={vegHealth}
                onSelect={(v) => setVegHealth(v as VegHealth)}
                activeColor="#6a1b9a"
              />
            </GlassCard>

            <SectionHeader icon="water-alert-outline" title="Flood Risk" light />
            <GlassCard opacity={0.92}>
              <ChipGroup
                options={['NONE', 'LOW', 'MEDIUM', 'HIGH']}
                selected={floodRisk}
                onSelect={(v) => setFloodRisk(v as FloodRisk)}
                activeColor="#e65100"
              />
            </GlassCard>

            <View style={styles.btnRow}>
              <AppButton
                mode="contained"
                onPress={handleSubmit}
                loading={submitting}
                disabled={submitting}
                buttonColor="#6a1b9a"
                icon="content-save-outline"
              >
                Save Observation
              </AppButton>
            </View>
            <View style={{ height: 16 }} />
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </RoleBackground>
  );
}

function ChipGroup({
  options, selected, onSelect, activeColor = '#2e7d32',
}: { options: string[]; selected: string; onSelect: (v: string) => void; activeColor?: string }) {
  return (
    <View style={styles.chipRow}>
      {options.map((o) => (
        <Text
          key={o}
          style={[styles.chip, selected === o && { borderColor: activeColor, color: activeColor, backgroundColor: `${activeColor}18` }]}
          onPress={() => onSelect(o)}
        >
          {o}
        </Text>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  flex: { flex: 1 },
  scroll: { paddingTop: 8, paddingBottom: 32 },
  input: { marginBottom: 8, backgroundColor: 'rgba(255,255,255,0.9)' },
  btnRow: { marginHorizontal: 16, marginTop: 16 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 16, borderWidth: 1, borderColor: '#bbb',
    backgroundColor: 'rgba(255,255,255,0.6)',
    fontSize: 13, color: '#555',
    overflow: 'hidden',
    fontWeight: '500',
  } as any,
});
