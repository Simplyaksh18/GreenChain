/**
 * ManualSensorReadingScreen — Phase 9C
 * POST /sensors/readings
 * Allows farmer to manually enter a single sensor reading.
 * estimated_methane is auto-calculated by the backend emission estimator.
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
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { createManualSensorReadingApi } from '../../api/sensorApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { AppButton } from '../../components/AppButton';
import { DatePickerField } from '../../components/DatePickerField';
import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'ManualSensorReading'>;

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

function nowTime() {
  const d = new Date();
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  return `${h}:${m}`;
}

export function ManualSensorReadingScreen({ navigation, route }: Props) {
  const { cycleId, farmId } = route.params;

  const [readingDate, setReadingDate]       = useState(todayDate());
  const [readingHHMM, setReadingHHMM]       = useState(nowTime());
  const [soilMoisture, setSoilMoisture]     = useState('');
  const [waterDepth, setWaterDepth]         = useState('');
  const [temperature, setTemperature]       = useState('');
  const [humidity, setHumidity]             = useState('');
  const [rainfall, setRainfall]             = useState('');
  const [qualityScore, setQualityScore]     = useState('');
  const [submitting, setSubmitting]         = useState(false);

  const handleSubmit = async () => {
    const sm = parseFloat(soilMoisture);
    const wd = parseFloat(waterDepth);
    const tc = parseFloat(temperature);
    const hm = parseFloat(humidity);
    const rf = parseFloat(rainfall);
    const qs = parseFloat(qualityScore);

    if (isNaN(sm) || sm < 0 || sm > 100) { Alert.alert('Validation', 'Soil moisture must be 0–100%'); return; }
    if (isNaN(wd) || wd < 0 || wd > 30)  { Alert.alert('Validation', 'Water depth must be 0–30 cm'); return; }
    if (isNaN(tc) || tc < 15 || tc > 45) { Alert.alert('Validation', 'Temperature must be 15–45 °C'); return; }
    if (isNaN(hm) || hm < 20 || hm > 100){ Alert.alert('Validation', 'Humidity must be 20–100%'); return; }
    if (isNaN(rf) || rf < 0 || rf > 100) { Alert.alert('Validation', 'Rainfall must be 0–100 mm'); return; }
    if (isNaN(qs) || qs < 0 || qs > 100) { Alert.alert('Validation', 'Data quality must be 0–100'); return; }

    if (!readingDate) { Alert.alert('Validation', 'Please select a reading date.'); return; }
    const timeStr = readingHHMM.trim() || '00:00';
    // Build ISO datetime
    const isoTime = `${readingDate}T${timeStr}:00Z`;

    try {
      setSubmitting(true);
      await createManualSensorReadingApi({
        farm_id: farmId,
        crop_cycle_id: cycleId,
        reading_time: isoTime,
        soil_moisture: sm,
        water_depth_cm: wd,
        temperature_c: tc,
        humidity: hm,
        rainfall_mm: rf,
        data_quality_score: qs,
      });
      Alert.alert('Saved', 'Sensor reading recorded. Methane estimated automatically.', [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? 'Failed to save reading.';
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
            <GlassCard style={styles.infoBanner} opacity={0.92}>
              <View style={styles.bannerRow}>
                <MaterialCommunityIcons name="information-outline" size={16} color="#1565c0" />
                <Text variant="bodySmall" style={styles.bannerText}>
                  Methane emission is auto-calculated from your inputs. Select date and optionally enter time (HH:MM).
                </Text>
              </View>
            </GlassCard>

            <SectionHeader icon="clock-outline" title="Reading Date & Time" light />
            <GlassCard opacity={0.92}>
              <DatePickerField
                label="Reading Date *"
                value={readingDate}
                onChange={setReadingDate}
                maxDate={new Date()}
                accentColor="#2e7d32"
              />
              <TextInput
                mode="outlined"
                label="Reading Time (HH:MM, optional — default 00:00)"
                value={readingHHMM}
                onChangeText={setReadingHHMM}
                placeholder="e.g. 08:30"
                style={styles.input}
                outlineColor="#9e9e9e"
                activeOutlineColor="#2e7d32"
                keyboardType="numbers-and-punctuation"
              />
            </GlassCard>

            <SectionHeader icon="water-outline" title="Soil & Water" light />
            <GlassCard opacity={0.92}>
              <NumberField label="Soil Moisture (%)" hint="0–100" value={soilMoisture} onChange={setSoilMoisture} />
              <NumberField label="Water Depth (cm)" hint="0–30" value={waterDepth} onChange={setWaterDepth} />
              <NumberField label="Rainfall (mm)" hint="0–100" value={rainfall} onChange={setRainfall} />
            </GlassCard>

            <SectionHeader icon="thermometer" title="Atmosphere" light />
            <GlassCard opacity={0.92}>
              <NumberField label="Temperature (°C)" hint="15–45" value={temperature} onChange={setTemperature} />
              <NumberField label="Humidity (%)" hint="20–100" value={humidity} onChange={setHumidity} />
            </GlassCard>

            <SectionHeader icon="star-outline" title="Data Quality" light />
            <GlassCard opacity={0.92}>
              <NumberField label="Data Quality Score" hint="0–100" value={qualityScore} onChange={setQualityScore} />
              <Text variant="bodySmall" style={styles.hint}>Higher = better quality sensor data (manual readings: 70–85 recommended)</Text>
            </GlassCard>

            <View style={styles.btnRow}>
              <AppButton
                mode="contained"
                onPress={handleSubmit}
                loading={submitting}
                disabled={submitting}
                buttonColor="#2e7d32"
                icon="content-save-outline"
              >
                Save Reading
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
      activeOutlineColor="#2e7d32"
    />
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  flex: { flex: 1 },
  scroll: { paddingTop: 8, paddingBottom: 32 },
  input: { marginBottom: 8, backgroundColor: 'rgba(255,255,255,0.9)' },
  btnRow: { marginHorizontal: 16, marginTop: 16 },
  infoBanner: { marginTop: 8 },
  bannerRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  bannerText: { flex: 1, color: '#1565c0', lineHeight: 18 },
  hint: { color: '#888', marginTop: 2, marginBottom: 4 },
});
