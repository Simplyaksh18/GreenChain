/**
 * EditCropCycleScreen — Phase 9C
 * PATCH /farms/{farm_id}/crop-cycles/{cycle_id}
 * Pre-filled from existing crop cycle data.
 */
import React, { useCallback, useState } from 'react';
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
import { useFocusEffect } from '@react-navigation/native';

import { getCropCyclesApi, updateCropCycleApi } from '../../api/farmApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { AppButton } from '../../components/AppButton';
import { LoadingView } from '../../components/LoadingView';
import { DatePickerField } from '../../components/DatePickerField';
import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'EditCropCycle'>;

const CROP_TYPES = ['Rice', 'Wheat', 'Maize', 'Sugarcane', 'Cotton', 'Soybean', 'Groundnut', 'Other'];
const SEASONS = ['Kharif', 'Rabi', 'Zaid'];
const BASELINE_METHODS = ['Continuous Flooding', 'Intermittent Flooding', 'Rainfed', 'Irrigated'];
const REDUCTION_PRACTICES = ['Alternate Wetting and Drying', 'System of Rice Intensification', 'Direct Seeded Rice', 'Other'];
const STATUSES = ['ACTIVE', 'COMPLETED', 'CANCELLED'] as const;

export function EditCropCycleScreen({ navigation, route }: Props) {
  const { cycleId, farmId, farmName } = route.params;

  const [cropType, setCropType]     = useState('Rice');
  const [season, setSeason]         = useState('Kharif');
  const [startDate, setStartDate]   = useState('');
  const [endDate, setEndDate]       = useState('');
  const [baseline, setBaseline]     = useState('Continuous Flooding');
  const [practice, setPractice]     = useState('Alternate Wetting and Drying');
  const [cycleStatus, setCycleStatus] = useState<typeof STATUSES[number]>('ACTIVE');
  const [loading, setLoading]       = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useFocusEffect(
    useCallback(() => {
      (async () => {
        try {
          const cycles = await getCropCyclesApi(farmId);
          const cycle = cycles.find((c) => c.id === cycleId);
          if (cycle) {
            setCropType(cycle.crop_type);
            setSeason(cycle.season);
            setStartDate(cycle.start_date);
            setEndDate(cycle.end_date ?? '');
            setBaseline(cycle.baseline_method);
            setPractice(cycle.reduction_practice);
            setCycleStatus(cycle.status as typeof STATUSES[number]);
          }
        } catch {
          Alert.alert('Error', 'Failed to load crop cycle data.');
          navigation.goBack();
        } finally {
          setLoading(false);
        }
      })();
    }, [farmId, cycleId]),
  );

  const handleSave = async () => {
    if (!startDate.trim()) {
      Alert.alert('Error', 'Please select a start date.');
      return;
    }
    if (endDate && endDate < startDate) {
      Alert.alert('Error', 'End date cannot be before start date.');
      return;
    }

    try {
      setSubmitting(true);
      await updateCropCycleApi(farmId, cycleId, {
        crop_type: cropType,
        season,
        start_date: startDate.trim(),
        end_date: endDate.trim() || null,
        baseline_method: baseline,
        reduction_practice: practice,
        status: cycleStatus,
      });
      Alert.alert('Saved', 'Crop cycle updated successfully.', [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? 'Failed to update crop cycle.';
      Alert.alert('Error', msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingView message="Loading crop cycle…" />;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <KeyboardAvoidingView
          style={styles.flex}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <ScrollView contentContainerStyle={styles.scroll}>
            <SectionHeader icon="pencil-outline" title={`Edit Cycle — ${farmName}`} light />

            <GlassCard opacity={0.92}>
              <Text variant="labelMedium" style={styles.label}>Crop Type</Text>
              <ChipGroup options={CROP_TYPES} selected={cropType} onSelect={setCropType} />

              <Text variant="labelMedium" style={styles.label}>Season</Text>
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
              <Text variant="labelMedium" style={styles.label}>Baseline Method</Text>
              <ChipGroup options={BASELINE_METHODS} selected={baseline} onSelect={setBaseline} />

              <Text variant="labelMedium" style={styles.label}>Reduction Practice</Text>
              <ChipGroup options={REDUCTION_PRACTICES} selected={practice} onSelect={setPractice} />
            </GlassCard>

            <SectionHeader icon="flag-outline" title="Status" light />
            <GlassCard opacity={0.92}>
              <ChipGroup options={[...STATUSES]} selected={cycleStatus} onSelect={(v) => setCycleStatus(v as typeof STATUSES[number])} />
            </GlassCard>

            <View style={styles.btnRow}>
              <AppButton
                mode="contained"
                onPress={handleSave}
                loading={submitting}
                disabled={submitting}
                buttonColor="#2e7d32"
                icon="content-save-outline"
              >
                Save Changes
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
  label: { color: '#555', fontWeight: '600', marginBottom: 8, marginTop: 12 },
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
  btnRow: { marginHorizontal: 16, marginTop: 16 },
});
