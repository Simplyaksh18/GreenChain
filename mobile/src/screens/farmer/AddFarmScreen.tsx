/**
 * AddFarmScreen — Phase 9C (9C-bugfix-v2)
 * POST /farms — farmer registers a new farm.
 * GET /fpo/list — populates FPO selector.
 *
 * Root cause of fpo_id = NULL bug:
 *   The old validate() had no FPO-selection check, so the form could be
 *   submitted with selectedFPO = null, silently sending fpo_id: null.
 *
 * Fix:
 *   - validate() now blocks submission if FPO list loaded but none selected.
 *   - FPO load errors are shown (not silently swallowed).
 *   - Dev-mode console logging for selected FPO, payload, and response.
 *   - Success alert shows farm id, fpo_id, and approval status from backend.
 *   - FPO dropdown shows FPO Profile ID for transparency.
 */
import React, { useEffect, useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import { Text, TextInput } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { createFarmApi } from '../../api/farmApi';
import { getFPOListApi, type FPOListItem } from '../../api/fpoApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { AppButton } from '../../components/AppButton';
import type { FarmerFarmsParamList } from '../../navigation/FarmerFarmsStack';

type Props = NativeStackScreenProps<FarmerFarmsParamList, 'AddFarm'>;

const SOIL_TYPES = ['Clay', 'Sandy', 'Loamy', 'Silty', 'Peaty', 'Chalky', 'Other'];
const WATER_SOURCES = ['Rain-fed', 'Canal', 'Borewell', 'River', 'Tank', 'Other'];

function Field({
  label,
  value,
  onChangeText,
  keyboardType,
  placeholder,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  keyboardType?: 'default' | 'numeric' | 'decimal-pad';
  placeholder?: string;
}) {
  return (
    <TextInput
      mode="outlined"
      label={label}
      value={value}
      onChangeText={onChangeText}
      keyboardType={keyboardType ?? 'default'}
      placeholder={placeholder}
      style={styles.input}
      outlineColor="#9e9e9e"
      activeOutlineColor="#2e7d32"
    />
  );
}

function ChipSelect({
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
        <TouchableOpacity
          key={o}
          style={[styles.chip, selected === o && styles.chipSelected]}
          onPress={() => onSelect(o)}
        >
          <Text style={[styles.chipText, selected === o && styles.chipTextSelected]}>{o}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

export function AddFarmScreen({ navigation }: Props) {
  const [farmName, setFarmName]           = useState('');
  const [landArea, setLandArea]           = useState('');
  const [latitude, setLatitude]           = useState('');
  const [longitude, setLongitude]         = useState('');
  const [village, setVillage]             = useState('');
  const [district, setDistrict]           = useState('');
  const [state, setState]                 = useState('');
  const [soilType, setSoilType]           = useState('Loamy');
  const [waterSource, setWaterSource]     = useState('Rain-fed');
  const [selectedFPO, setSelectedFPO]     = useState<FPOListItem | null>(null);
  const [fpoList, setFpoList]             = useState<FPOListItem[]>([]);
  const [fpoLoadError, setFpoLoadError]   = useState(false);
  const [fpoLoading, setFpoLoading]       = useState(true);
  const [showFPOPicker, setShowFPOPicker] = useState(false);
  const [submitting, setSubmitting]       = useState(false);

  useEffect(() => {
    setFpoLoading(true);
    getFPOListApi()
      .then((list) => {
        setFpoList(list);
        if (__DEV__) {
          console.log('[AddFarm] FPO list loaded:', JSON.stringify(list, null, 2));
        }
      })
      .catch((err) => {
        setFpoLoadError(true);
        if (__DEV__) {
          console.warn('[AddFarm] Failed to load FPO list:', err?.response?.data ?? err?.message ?? err);
        }
      })
      .finally(() => setFpoLoading(false));
  }, []);

  const validate = (): string | null => {
    if (!farmName.trim()) return 'Farm name is required.';
    const area = parseFloat(landArea);
    if (isNaN(area) || area <= 0) return 'Land area must be greater than 0.';
    const lat = parseFloat(latitude);
    if (isNaN(lat) || lat < -90 || lat > 90) return 'Latitude must be between -90 and 90.';
    const lon = parseFloat(longitude);
    if (isNaN(lon) || lon < -180 || lon > 180) return 'Longitude must be between -180 and 180.';
    if (!village.trim()) return 'Village is required.';
    if (!district.trim()) return 'District is required.';
    if (!state.trim()) return 'State is required.';
    // KEY FIX: Require FPO selection when FPOs are available
    // Without this check the form silently submits fpo_id: null
    if (!fpoLoadError && fpoList.length > 0 && !selectedFPO) {
      return 'Please select an FPO. Without one this farm will not appear in the FPO approval queue and carbon credits cannot be issued.';
    }
    return null;
  };

  const handleSubmit = async () => {
    const err = validate();
    if (err) { Alert.alert('Validation Error', err); return; }

    const payload = {
      farm_name: farmName.trim(),
      land_area_acres: parseFloat(landArea),
      latitude: parseFloat(latitude),
      longitude: parseFloat(longitude),
      village: village.trim(),
      district: district.trim(),
      state: state.trim(),
      soil_type: soilType,
      water_source: waterSource,
      fpo_id: selectedFPO?.id ?? null,
    };

    // Dev logging — confirms what is actually sent to the backend
    if (__DEV__) {
      console.log('[AddFarm] Selected FPO object:', JSON.stringify(selectedFPO, null, 2));
      console.log('[AddFarm] POST /farms payload:', JSON.stringify(payload, null, 2));
    }

    try {
      setSubmitting(true);
      const created = await createFarmApi(payload);

      if (__DEV__) {
        console.log('[AddFarm] Backend response:', JSON.stringify(created, null, 2));
      }

      Alert.alert(
        'Farm Registered ✓',
        [
          selectedFPO
            ? `Farm submitted to ${selectedFPO.organization_name} for approval.`
            : 'Farm registered. Pending admin approval (no FPO linked).',
          '',
          `Farm ID: #${created.id}`,
          `FPO ID: ${created.fpo_id !== null && created.fpo_id !== undefined ? String(created.fpo_id) : 'None'}`,
          `Approval status: ${created.is_approved ? 'Approved' : 'Pending approval'}`,
        ].join('\n'),
        [{ text: 'OK', onPress: () => navigation.goBack() }],
      );
    } catch (e: any) {
      if (__DEV__) {
        console.error('[AddFarm] createFarmApi error:', e?.response?.data ?? e?.message ?? e);
      }
      const msg = e?.response?.data?.detail ?? 'Failed to register farm. Please try again.';
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
            {/* Info banner */}
            <GlassCard style={styles.infoBanner} opacity={0.92}>
              <View style={styles.bannerRow}>
                <MaterialCommunityIcons name="information-outline" size={20} color="#1565c0" />
                <Text variant="bodySmall" style={styles.bannerText}>
                  New farms require FPO approval before carbon tracking begins.
                  Select your FPO below — they will review and approve your farm.
                </Text>
              </View>
            </GlassCard>

            {/* Basic Info */}
            <SectionHeader icon="home-outline" title="Farm Information" light />
            <GlassCard opacity={0.92}>
              <Field label="Farm Name *" value={farmName} onChangeText={setFarmName} placeholder="e.g. Green Valley Farm" />
              <Field
                label="Land Area (acres) *"
                value={landArea}
                onChangeText={setLandArea}
                keyboardType="decimal-pad"
                placeholder="e.g. 5.5"
              />
            </GlassCard>

            {/* Location */}
            <SectionHeader icon="map-marker-outline" title="Location" light />
            <GlassCard opacity={0.92}>
              <Field label="Village *" value={village} onChangeText={setVillage} />
              <Field label="District *" value={district} onChangeText={setDistrict} />
              <Field label="State *" value={state} onChangeText={setState} />
              <Field
                label="Latitude *"
                value={latitude}
                onChangeText={setLatitude}
                keyboardType="decimal-pad"
                placeholder="-90 to 90  (e.g. 13.0827)"
              />
              <Field
                label="Longitude *"
                value={longitude}
                onChangeText={setLongitude}
                keyboardType="decimal-pad"
                placeholder="-180 to 180  (e.g. 80.2707)"
              />
            </GlassCard>

            {/* Soil & Water */}
            <SectionHeader icon="terrain" title="Soil & Water" light />
            <GlassCard opacity={0.92}>
              <Text variant="labelMedium" style={styles.pickerLabel}>Soil Type</Text>
              <ChipSelect options={SOIL_TYPES} selected={soilType} onSelect={setSoilType} />
              <Text variant="labelMedium" style={[styles.pickerLabel, { marginTop: 14 }]}>Water Source</Text>
              <ChipSelect options={WATER_SOURCES} selected={waterSource} onSelect={setWaterSource} />
            </GlassCard>

            {/* FPO Linkage — REQUIRED */}
            <SectionHeader icon="office-building-outline" title="Link to an FPO (Required)" light />
            <GlassCard opacity={0.92}>
              {fpoLoading ? (
                <View style={styles.noFPORow}>
                  <MaterialCommunityIcons name="loading" size={16} color="#888" />
                  <Text variant="bodySmall" style={styles.noFPOText}>
                    Loading FPO organizations…
                  </Text>
                </View>
              ) : fpoLoadError ? (
                <View style={styles.errorRow}>
                  <MaterialCommunityIcons name="alert-circle-outline" size={16} color="#c62828" />
                  <Text variant="bodySmall" style={styles.errorText}>
                    Could not load FPO list. Check your connection.
                    Without an FPO, your farm cannot be approved for carbon credits.
                  </Text>
                </View>
              ) : fpoList.length === 0 ? (
                <View style={styles.noFPORow}>
                  <MaterialCommunityIcons name="information-outline" size={16} color="#888" />
                  <Text variant="bodySmall" style={styles.noFPOText}>
                    No FPO organizations found. Contact your FPO to register on GreenChain.
                  </Text>
                </View>
              ) : (
                <>
                  {/* Orange warning if nothing selected */}
                  {!selectedFPO && (
                    <View style={styles.warnRow}>
                      <MaterialCommunityIcons name="alert-outline" size={16} color="#e65100" />
                      <Text variant="bodySmall" style={styles.warnText}>
                        No FPO selected. This farm will not appear for approval and carbon credits cannot be issued.
                      </Text>
                    </View>
                  )}

                  <Text variant="bodySmall" style={styles.fpoHint}>
                    Select the FPO that manages your region.
                  </Text>

                  {/* Selector button */}
                  <TouchableOpacity
                    style={[styles.fpoSelector, !selectedFPO && styles.fpoSelectorWarn]}
                    onPress={() => setShowFPOPicker(!showFPOPicker)}
                  >
                    <View style={styles.fpoSelectorInner}>
                      <MaterialCommunityIcons
                        name={selectedFPO ? 'office-building' : 'office-building-outline'}
                        size={20}
                        color={selectedFPO ? '#2e7d32' : '#e65100'}
                      />
                      <Text style={[styles.fpoSelectorText, selectedFPO && styles.fpoSelectorTextSelected]}>
                        {selectedFPO ? selectedFPO.organization_name : 'Select FPO *'}
                      </Text>
                    </View>
                    <MaterialCommunityIcons
                      name={showFPOPicker ? 'chevron-up' : 'chevron-down'}
                      size={20}
                      color="#888"
                    />
                  </TouchableOpacity>

                  {/* Dropdown list */}
                  {showFPOPicker && (
                    <View style={styles.fpoDropdown}>
                      {fpoList.map((fpo) => (
                        <TouchableOpacity
                          key={fpo.id}
                          style={[
                            styles.fpoOption,
                            selectedFPO?.id === fpo.id && styles.fpoOptionSelected,
                          ]}
                          onPress={() => { setSelectedFPO(fpo); setShowFPOPicker(false); }}
                        >
                          <View style={styles.fpoOptionRow}>
                            <Text style={[
                              styles.fpoOptionText,
                              selectedFPO?.id === fpo.id && styles.fpoOptionTextSelected,
                            ]}>
                              {fpo.organization_name}
                            </Text>
                            {selectedFPO?.id === fpo.id && (
                              <MaterialCommunityIcons name="check-circle" size={16} color="#2e7d32" />
                            )}
                          </View>
                          <Text style={styles.fpoOptionSub}>Registration: {fpo.registration_number}</Text>
                          <Text style={styles.fpoOptionSub}>{fpo.district}, {fpo.state}</Text>
                          <Text style={styles.fpoOptionId}>FPO Profile ID: {fpo.id}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  )}

                  {/* Selected FPO confirmation */}
                  {selectedFPO && (
                    <View style={styles.selectedFPOCard}>
                      <MaterialCommunityIcons name="check-circle" size={16} color="#2e7d32" />
                      <View style={styles.selectedFPOText}>
                        <Text variant="labelMedium" style={styles.selectedFPOName}>
                          Selected FPO: {selectedFPO.organization_name}
                        </Text>
                        <Text variant="labelSmall" style={styles.selectedFPOMeta}>
                          Reg: {selectedFPO.registration_number} · {selectedFPO.district}, {selectedFPO.state}
                        </Text>
                        <Text variant="labelSmall" style={styles.selectedFPOMeta}>
                          FPO Profile ID: {selectedFPO.id}
                        </Text>
                      </View>
                      <TouchableOpacity onPress={() => setSelectedFPO(null)}>
                        <MaterialCommunityIcons name="close-circle-outline" size={20} color="#888" />
                      </TouchableOpacity>
                    </View>
                  )}
                </>
              )}
            </GlassCard>

            {/* Submit */}
            <View style={styles.submitSection}>
              <AppButton
                mode="contained"
                onPress={handleSubmit}
                loading={submitting}
                disabled={submitting}
                buttonColor="#2e7d32"
                icon="check-circle-outline"
              >
                Register Farm
              </AppButton>
            </View>

            <View style={styles.bottomPad} />
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  flex: { flex: 1 },
  scroll: { paddingTop: 8, paddingBottom: 32 },

  infoBanner: { marginTop: 8 },
  bannerRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  bannerText: { flex: 1, color: '#1565c0', lineHeight: 18 },

  input: { marginBottom: 10, backgroundColor: 'rgba(255,255,255,0.9)' },

  pickerLabel: { color: '#555', marginBottom: 8, fontWeight: '600' },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 16, borderWidth: 1, borderColor: '#bbb',
    backgroundColor: 'rgba(255,255,255,0.6)',
  },
  chipSelected: { borderColor: '#2e7d32', backgroundColor: '#e8f5e9' },
  chipText: { fontSize: 13, color: '#555' },
  chipTextSelected: { color: '#2e7d32', fontWeight: '700' },

  // FPO section
  errorRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  errorText: { flex: 1, color: '#c62828', lineHeight: 18 },
  noFPORow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  noFPOText: { flex: 1, color: '#888' },
  warnRow: {
    flexDirection: 'row', gap: 8, alignItems: 'flex-start',
    backgroundColor: '#fff3e0', borderRadius: 8,
    padding: 10, marginBottom: 10,
  },
  warnText: { flex: 1, color: '#e65100', lineHeight: 18 },
  fpoHint: { color: '#555', marginBottom: 10, lineHeight: 18 },

  fpoSelector: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    borderWidth: 1.5, borderColor: '#bbb', borderRadius: 8,
    padding: 12, backgroundColor: 'rgba(255,255,255,0.8)',
  },
  fpoSelectorWarn: { borderColor: '#e65100' },
  fpoSelectorInner: { flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 },
  fpoSelectorText: { color: '#e65100', fontSize: 15 },
  fpoSelectorTextSelected: { color: '#2e7d32', fontWeight: '700' },

  fpoDropdown: {
    marginTop: 4, borderWidth: 1, borderColor: '#e0e0e0',
    borderRadius: 8, backgroundColor: '#fff', overflow: 'hidden',
  },
  fpoOption: {
    paddingHorizontal: 14, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: '#f0f0f0',
  },
  fpoOptionSelected: { backgroundColor: '#e8f5e9' },
  fpoOptionRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  fpoOptionText: { fontSize: 14, color: '#333', fontWeight: '600' },
  fpoOptionTextSelected: { color: '#2e7d32', fontWeight: '700' },
  fpoOptionSub: { fontSize: 12, color: '#888', marginTop: 2 },
  fpoOptionId: { fontSize: 11, color: '#aaa', marginTop: 2 },

  selectedFPOCard: {
    flexDirection: 'row', gap: 8, alignItems: 'flex-start',
    marginTop: 10, padding: 10,
    backgroundColor: '#e8f5e9', borderRadius: 8,
  },
  selectedFPOText: { flex: 1 },
  selectedFPOName: { color: '#2e7d32', fontWeight: '700' },
  selectedFPOMeta: { color: '#555', marginTop: 2 },

  submitSection: { marginHorizontal: 16, marginTop: 16 },
  bottomPad: { height: 16 },
});
