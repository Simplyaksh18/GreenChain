/**
 * CreateCropCycleScreen — Phase 9C
 * POST /farms/{farm_id}/crop-cycles
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
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { createCropCycleApi } from '../../api/farmApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { AppButton } from '../../components/AppButton';
import { DatePickerField } from '../../components/DatePickerField';
import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'CreateCropCycle'>;

const CROP_TYPES = ['Rice', 'Wheat', 'Maize', 'Sugarcane', 'Cotton', 'Soybean', 'Groundnut', 'Other'];
const SEASONS = ['Kharif', 'Rabi', 'Zaid'];
const BASELINE_METHODS = ['Continuous Flooding', 'Intermittent Flooding', 'Rainfed', 'Irrigated'];
const REDUCTION_PRACTICES = ['Alternate Wetting and Drying', 'System of Rice Intensification', 'Direct Seeded Rice', 'Other'];

export function CreateCropCycleScreen({ navigation, route }: Props) {
  const { farmId, farmName } = route.params;

  const [cropType, setCropType]       = useState('Rice');
  const [season, setSeason]           = useState('Kharif');
  const [startDate, setStartDate]     = useState('');
  const [endDate, setEndDate]         = useState('');
  const [baseline, setBaseline]       = useState('Continuous Flooding');
  const [practice, setPractice]       = useState('Alternate Wetting and Drying');
  const [submitting, setSubmitting]   = useState(false);

  const handleSubmit = async () => {
    if (!startDate.trim()) { Alert.alert('Error', 'Please select a start date.'); return; }
    if (endDate && endDate < startDate) { Alert.alert('Error', 'End date cannot be before start date.'); return; }

    try {
      setSubmitting(true);
      await createCropCycleApi(farmId, {
        crop_type: cropType,
        season,
        start_date: startDate.trim(),
        end_date: endDate.trim() || null,
        baseline_method: baseline,
        reduction_practice: practice,
      });
      Alert.alert('Crop Cycle Created', 'Your crop cycle has been registered. Sensor data will now be tracked.', [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? 'Failed to create crop cycle.';
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
            <SectionHeader icon="sprout" title={`New Cycle — ${farmName}`} light />

            <GlassCard opacity={0.92}>
              <Text variant="labelMedium" style={styles.sectionLabel}>Crop Type</Text>
              <ChipGroup options={CROP_TYPES} selected={cropType} onSelect={setCropType} />

              <Text variant="labelMedium" style={styles.sectionLabel}>Season</Text>
              <ChipGroup options={SEASONS} selected={season} onSelect={setSeason} />
            </GlassCard>

            <SectionHeader icon="calendar-range" title="Dates" light />
            <GlassCard opacity={0.92}>
              <DatePickerField
                label="Start Date *"
                value={startDate}
                onChange={setStartDate}
                maxDate={new Date()}
                accentColor="#2e7d32"
              />
              <DatePickerField
                label="End Date"
                value={endDate}
                onChange={setEndDate}
                minDate={startDate ? new Date(startDate) : undefined}
                maxDate={new Date()}
                accentColor="#2e7d32"
                optional
              />
            </GlassCard>

            <SectionHeader icon="cog-outline" title="Methane Reduction" light />
            <GlassCard opacity={0.92}>
              <Text variant="labelMedium" style={styles.sectionLabel}>Baseline Method</Text>
              <ChipGroup options={BASELINE_METHODS} selected={baseline} onSelect={setBaseline} />

              <Text variant="labelMedium" style={styles.sectionLabel}>Reduction Practice</Text>
              <ChipGroup options={REDUCTION_PRACTICES} selected={practice} onSelect={setPractice} />
            </GlassCard>

            <View style={styles.submitSection}>
              <AppButton
                mode="contained"
                onPress={handleSubmit}
                loading={submitting}
                disabled={submitting}
                buttonColor="#2e7d32"
                icon="check-circle-outline"
              >
                Create Crop Cycle
              </AppButton>
            </View>
            <View style={styles.bottomPad} />
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </RoleBackground>
  );
}

function ChipGroup({
  options,
  selected,
  onSelect,
}: {
  options: string[];
  selected: string;
  onSelect: (v: string) => void;
}) {
  return (
    <View style={styles.chipRow}>
      {options.map((o) => (
        <Text
          key={o}
          style={[styles.chip, selected === o && styles.chipSelected]}
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
  sectionLabel: { color: '#555', fontWeight: '600', marginBottom: 8, marginTop: 12 },
  input: { marginBottom: 10, backgroundColor: 'rgba(255,255,255,0.9)' },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 },
  chip: {
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 16, borderWidth: 1, borderColor: '#bbb',
    backgroundColor: 'rgba(255,255,255,0.6)',
    fontSize: 13, color: '#555',
    overflow: 'hidden',
  },
  chipSelected: { borderColor: '#2e7d32', backgroundColor: '#e8f5e9', color: '#2e7d32', fontWeight: '700' } as any,
  submitSection: { marginHorizontal: 16, marginTop: 16 },
  bottomPad: { height: 16 },
});
