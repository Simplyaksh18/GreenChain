/**
 * ManualDroneObservationScreen — Phase 9C
 * POST /drone/observations
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

import { createManualDroneObservationApi } from '../../api/observationApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { AppButton } from '../../components/AppButton';
import { DatePickerField } from '../../components/DatePickerField';
import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'ManualDroneObservation'>;

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export function ManualDroneObservationScreen({ navigation, route }: Props) {
  const { cycleId, farmId } = route.params;

  const [obsDate, setObsDate]           = useState(todayISO());
  const [vegCover, setVegCover]         = useState('');
  const [standingWater, setStandingWater] = useState('');
  const [anomalyScore, setAnomalyScore] = useState('0');
  const [imageRef, setImageRef]         = useState('');
  const [submitting, setSubmitting]     = useState(false);

  const handleSubmit = async () => {
    const vc = parseFloat(vegCover);
    const sw = parseFloat(standingWater);
    const as_ = parseFloat(anomalyScore || '0');

    if (!obsDate) { Alert.alert('Validation', 'Please select an observation date.'); return; }
    if (obsDate > new Date().toISOString().slice(0, 10)) { Alert.alert('Validation', 'Observation date cannot be in the future.'); return; }
    if (isNaN(vc) || vc < 0 || vc > 100)  { Alert.alert('Validation', 'Vegetation cover must be 0–100%'); return; }
    if (isNaN(sw) || sw < 0 || sw > 100)  { Alert.alert('Validation', 'Standing water must be 0–100%'); return; }
    if (isNaN(as_) || as_ < 0 || as_ > 100) { Alert.alert('Validation', 'Anomaly score must be 0–100'); return; }

    try {
      setSubmitting(true);
      await createManualDroneObservationApi({
        farm_id: farmId,
        crop_cycle_id: cycleId,
        observation_date: obsDate,
        vegetation_cover_percent: vc,
        standing_water_percent: sw,
        anomaly_score: as_,
        image_reference: imageRef.trim() || null,
      });
      Alert.alert('Saved', 'Drone observation recorded.', [
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
            <SectionHeader icon="drone" title="Drone Observation" light />

            <GlassCard opacity={0.92}>
              <DatePickerField
                label="Observation Date *"
                value={obsDate}
                onChange={setObsDate}
                maxDate={new Date()}
                accentColor="#37474f"
              />
            </GlassCard>

            <SectionHeader icon="grass" title="Field Measurements" light />
            <GlassCard opacity={0.92}>
              <NumberField label="Vegetation Cover %" hint="0–100" value={vegCover} onChange={setVegCover} />
              <NumberField label="Standing Water %" hint="0–100" value={standingWater} onChange={setStandingWater} />
              <NumberField label="Anomaly Score" hint="0–100 (default 0)" value={anomalyScore} onChange={setAnomalyScore} />
            </GlassCard>

            <SectionHeader icon="image-outline" title="Image Reference (optional)" light />
            <GlassCard opacity={0.92}>
              <TextInput
                mode="outlined"
                label="Image filename or URL"
                value={imageRef}
                onChangeText={setImageRef}
                placeholder="e.g. drone_farm5_obs1.jpg"
                style={styles.input}
                outlineColor="#9e9e9e"
                activeOutlineColor="#37474f"
              />
              <Text variant="bodySmall" style={styles.hint}>
                Optional. Enter a filename, S3 key, or URL for the drone image.
              </Text>
            </GlassCard>

            <View style={styles.btnRow}>
              <AppButton
                mode="contained"
                onPress={handleSubmit}
                loading={submitting}
                disabled={submitting}
                buttonColor="#37474f"
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

function NumberField({
  label, hint, value, onChange,
}: { label: string; hint: string; value: string; onChange: (v: string) => void }) {
  return (
    <TextInput
      mode="outlined"
      label={`${label} (${hint})`}
      value={value}
      onChangeText={onChange}
      keyboardType="numeric"
      style={styles.input}
      outlineColor="#9e9e9e"
      activeOutlineColor="#37474f"
    />
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  flex: { flex: 1 },
  scroll: { paddingTop: 8, paddingBottom: 32 },
  input: { marginBottom: 8, backgroundColor: 'rgba(255,255,255,0.9)' },
  btnRow: { marginHorizontal: 16, marginTop: 16 },
  hint: { color: '#888', marginBottom: 4 },
});
