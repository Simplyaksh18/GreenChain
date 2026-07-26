/**
 * AddEvidenceScreen — Phase 14 / Phase 15
 *
 * Allows FPO (and optionally Farmer) to upload evidence for a farm.
 * Upload options:
 *   1. Take Photo      — requests camera permission first
 *   2. Record Video    — requests camera permission first
 *   3. Choose from Gallery  — requests media library permission
 *   4. Choose File/PDF — expo-document-picker
 *   5. Choose from Google Drive — Google OAuth (Phase 15)
 *
 * POST /evidence/upload (multipart)        — options 1–4
 * POST /evidence/google-drive/import       — option 5
 *
 * Navigation params:
 *   farmId, farmName, cropCycleId? (optional)
 */
import React, { useEffect, useState } from 'react';
import {
  Alert,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import { Text, Button, TextInput, Menu } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { uploadEvidenceFile } from '../../api/auditApi';
import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';
import { SectionHeader } from '../../components/SectionHeader';
import { GOOGLE_AUTH_ENABLED } from '../../utils/featureFlags';
import {
  useGoogleAuth,
  fetchDriveFiles,
  type DriveFile,
} from '../../services/googleAuthService';
import { useAuthStore } from '../../store/authStore';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://192.168.1.10:8000';

// ── Navigation param type (shared across FPO and Farmer stacks) ───────────────
export type AddEvidenceParams = {
  farmId: number;
  farmName: string;
  cropCycleId?: number;
};

const EVIDENCE_TYPES = [
  'PHOTO', 'VIDEO', 'PDF', 'DOCUMENT',
  'SENSOR_EXPORT', 'SATELLITE_EXPORT', 'DRONE_EXPORT', 'OTHER',
] as const;

interface PickedFile {
  uri: string;
  name: string;
  mimeType: string;
  size?: number;
  isImage: boolean;
  isVideo: boolean;
}

type Props = NativeStackScreenProps<any, any>;

export function AddEvidenceScreen({ route, navigation }: Props) {
  const { farmId, farmName, cropCycleId } = route.params as AddEvidenceParams;
  const authToken = useAuthStore((s) => s.token);

  const [pickedFile, setPickedFile]     = useState<PickedFile | null>(null);
  const [evidenceType, setEvidenceType] = useState<string>('PHOTO');
  const [description, setDescription]  = useState('');
  const [uploading, setUploading]      = useState(false);
  const [menuOpen, setMenuOpen]        = useState(false);

  // ── Google Drive picker state ─────────────────────────────────────────────
  const [driveFiles, setDriveFiles]     = useState<DriveFile[]>([]);
  const [driveOpen, setDriveOpen]       = useState(false);
  const [driveToken, setDriveToken]     = useState<string | null>(null);
  const [driveLoading, setDriveLoading] = useState(false);

  const { request: googleRequest, response: googleResponse, promptAsync: googlePrompt } = useGoogleAuth();

  useEffect(() => {
    if (!googleResponse) return;
    (async () => {
      setDriveLoading(true);
      try {
        if (googleResponse.type === 'success' && googleResponse.authentication?.accessToken) {
          const token = googleResponse.authentication.accessToken;
          // Token used to list files — never stored beyond this call
          const files = await fetchDriveFiles(token);
          setDriveToken(token);  // kept briefly for the import call below
          setDriveFiles(files);
          setDriveOpen(true);
        }
      } finally {
        setDriveLoading(false);
      }
    })();
  }, [googleResponse]);

  async function handleImportFromDrive(file: DriveFile) {
    if (!driveToken) return;
    setDriveOpen(false);
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('farm_id', String(farmId));
      formData.append('file_id', file.id);
      formData.append('google_access_token', driveToken);
      formData.append('evidence_type', evidenceType);
      if (cropCycleId) formData.append('crop_cycle_id', String(cropCycleId));
      if (description.trim()) formData.append('description', description.trim());

      const headers: Record<string, string> = { 'Content-Type': 'multipart/form-data' };
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      const resp = await fetch(`${API_BASE_URL}/evidence/google-drive/import`, {
        method: 'POST',
        headers,
        body: formData,
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body?.detail ?? `Import failed (HTTP ${resp.status})`);
      }
      Alert.alert('✅ Imported', `${file.name} imported from Google Drive.`, [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (err: any) {
      Alert.alert('Drive Import Failed', err?.message ?? 'Please try again.');
    } finally {
      setUploading(false);
      setDriveToken(null); // discard token immediately after use
    }
  }

  // ── Permission helpers ──────────────────────────────────────────────────────

  async function _requestCameraPermission(): Promise<boolean> {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert(
        'Permission required',
        'Camera permission is required to capture evidence. Please allow camera access in Settings.',
      );
      return false;
    }
    return true;
  }

  async function _requestMediaPermission(): Promise<boolean> {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert(
        'Permission required',
        'Media library access is required to select photos or videos.',
      );
      return false;
    }
    return true;
  }

  // ── Source pickers ──────────────────────────────────────────────────────────

  async function handleTakePhoto() {
    const ok = await _requestCameraPermission();
    if (!ok) return;
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.85,
      allowsEditing: false,
    });
    if (!result.canceled && result.assets.length > 0) {
      const asset = result.assets[0];
      setPickedFile({
        uri: asset.uri,
        name: asset.fileName ?? `photo_${Date.now()}.jpg`,
        mimeType: asset.mimeType ?? 'image/jpeg',
        size: asset.fileSize,
        isImage: true,
        isVideo: false,
      });
      setEvidenceType('PHOTO');
    }
  }

  async function handleRecordVideo() {
    const ok = await _requestCameraPermission();
    if (!ok) return;
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Videos,
      videoMaxDuration: 120,
      quality: ImagePicker.UIImagePickerControllerQualityType.Medium,
    });
    if (!result.canceled && result.assets.length > 0) {
      const asset = result.assets[0];
      setPickedFile({
        uri: asset.uri,
        name: asset.fileName ?? `video_${Date.now()}.mp4`,
        mimeType: asset.mimeType ?? 'video/mp4',
        size: asset.fileSize,
        isImage: false,
        isVideo: true,
      });
      setEvidenceType('VIDEO');
    }
  }

  async function handlePickFromGallery() {
    const ok = await _requestMediaPermission();
    if (!ok) return;
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.All,
      quality: 0.9,
    });
    if (!result.canceled && result.assets.length > 0) {
      const asset = result.assets[0];
      const isVideo = (asset.type === 'video') || (asset.mimeType?.startsWith('video') ?? false);
      setPickedFile({
        uri: asset.uri,
        name: asset.fileName ?? `media_${Date.now()}`,
        mimeType: asset.mimeType ?? (isVideo ? 'video/mp4' : 'image/jpeg'),
        size: asset.fileSize,
        isImage: !isVideo,
        isVideo,
      });
      setEvidenceType(isVideo ? 'VIDEO' : 'PHOTO');
    }
  }

  async function handlePickFile() {
    const result = await DocumentPicker.getDocumentAsync({
      type: ['application/pdf', 'application/msword',
             'text/csv', 'application/json', '*/*'],
      copyToCacheDirectory: true,
    });
    if (!result.canceled && result.assets.length > 0) {
      const asset = result.assets[0];
      const mime = asset.mimeType ?? 'application/octet-stream';
      setPickedFile({
        uri: asset.uri,
        name: asset.name,
        mimeType: mime,
        size: asset.size,
        isImage: false,
        isVideo: false,
      });
      if (mime === 'application/pdf') setEvidenceType('PDF');
      else if (mime === 'text/csv') setEvidenceType('SENSOR_EXPORT');
      else setEvidenceType('DOCUMENT');
    }
  }

  // ── Upload ──────────────────────────────────────────────────────────────────

  async function handleUpload() {
    if (!pickedFile) {
      Alert.alert('No file selected', 'Please select a file to upload.');
      return;
    }
    setUploading(true);
    try {
      await uploadEvidenceFile({
        farmId,
        cropCycleId,
        evidenceType,
        description: description.trim() || undefined,
        uri: pickedFile.uri,
        fileName: pickedFile.name,
        mimeType: pickedFile.mimeType,
      });
      Alert.alert(
        '✅ Uploaded',
        `${pickedFile.name} uploaded successfully.\nHash computed and stored.`,
        [{ text: 'OK', onPress: () => navigation.goBack() }],
      );
    } catch (err: any) {
      Alert.alert('Upload failed', err?.response?.data?.detail ?? 'Please try again.');
    } finally {
      setUploading(false);
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <ScrollView contentContainerStyle={styles.scroll}>
          <SectionHeader icon="cloud-upload-outline" title="Add Evidence" light />

          {/* Farm context */}
          <GlassCard opacity={0.88} style={styles.card}>
            <Text variant="labelSmall" style={styles.label}>Farm</Text>
            <Text variant="bodyMedium">{farmName}</Text>
            {cropCycleId && (
              <Text variant="bodySmall" style={styles.sub}>Crop Cycle #{cropCycleId}</Text>
            )}
          </GlassCard>

          {/* Source buttons */}
          <GlassCard opacity={0.90} style={styles.card}>
            <Text variant="labelSmall" style={styles.label}>Select Source</Text>
            <View style={styles.sourceGrid}>
              <SourceButton icon="camera" label="Take Photo"  color="#1565c0" onPress={handleTakePhoto} />
              <SourceButton icon="video"  label="Record Video" color="#6a1b9a" onPress={handleRecordVideo} />
              <SourceButton icon="image-multiple" label="Gallery" color="#2e7d32" onPress={handlePickFromGallery} />
              <SourceButton icon="file-upload-outline" label="File / PDF" color="#e65100" onPress={handlePickFile} />
              {/* Google Drive — hidden behind GOOGLE_AUTH_ENABLED flag */}
              {GOOGLE_AUTH_ENABLED && (
                <SourceButton
                  icon="google-drive"
                  label={driveLoading ? "Connecting…" : "Google Drive"}
                  color="#1a73e8"
                  onPress={() => {
                    if (googleRequest && !driveLoading) googlePrompt();
                  }}
                />
              )}
            </View>

            {/* Google Drive file list — shown after successful Google auth */}
            {GOOGLE_AUTH_ENABLED && driveOpen && driveFiles.length > 0 && (
              <View style={styles.driveList}>
                <Text variant="labelSmall" style={[styles.label, { marginBottom: 8 }]}>
                  Select a file from Google Drive
                </Text>
                {driveFiles.map((f) => (
                  <TouchableOpacity
                    key={f.id}
                    style={styles.driveItem}
                    onPress={() => handleImportFromDrive(f)}
                  >
                    <MaterialCommunityIcons
                      name={f.mimeType.startsWith('image') ? 'image' : f.mimeType === 'application/pdf' ? 'file-pdf-box' : 'file-document-outline'}
                      size={22}
                      color="#1a73e8"
                    />
                    <View style={{ flex: 1 }}>
                      <Text variant="bodySmall" numberOfLines={1}>{f.name}</Text>
                      <Text variant="labelSmall" style={styles.sub}>{f.mimeType}</Text>
                    </View>
                    <MaterialCommunityIcons name="cloud-download-outline" size={18} color="#888" />
                  </TouchableOpacity>
                ))}
                <TouchableOpacity onPress={() => setDriveOpen(false)} style={{ alignItems: 'center', marginTop: 8 }}>
                  <Text style={{ color: '#888', fontSize: 13 }}>Cancel</Text>
                </TouchableOpacity>
              </View>
            )}
          </GlassCard>

          {/* Selected file preview */}
          {pickedFile && (
            <GlassCard opacity={0.92} style={styles.card}>
              <Text variant="labelSmall" style={styles.label}>Selected File</Text>
              <View style={styles.fileRow}>
                <MaterialCommunityIcons
                  name={pickedFile.isImage ? 'image' : pickedFile.isVideo ? 'video' : 'file-document-outline'}
                  size={28}
                  color="#1565c0"
                />
                <View style={styles.fileInfo}>
                  <Text variant="bodyMedium" numberOfLines={1}>{pickedFile.name}</Text>
                  <Text variant="bodySmall" style={styles.sub}>
                    {pickedFile.mimeType}
                    {pickedFile.size ? `  •  ${(pickedFile.size / 1024).toFixed(1)} KB` : ''}
                  </Text>
                </View>
                <TouchableOpacity onPress={() => setPickedFile(null)}>
                  <MaterialCommunityIcons name="close-circle" size={22} color="#aaa" />
                </TouchableOpacity>
              </View>
            </GlassCard>
          )}

          {/* Evidence type picker */}
          <GlassCard opacity={0.88} style={styles.card}>
            <Text variant="labelSmall" style={styles.label}>Evidence Type</Text>
            <Menu
              visible={menuOpen}
              onDismiss={() => setMenuOpen(false)}
              anchor={
                <TouchableOpacity style={styles.typeBtn} onPress={() => setMenuOpen(true)}>
                  <Text variant="bodyMedium">{evidenceType}</Text>
                  <MaterialCommunityIcons name="chevron-down" size={20} color="#555" />
                </TouchableOpacity>
              }
            >
              {EVIDENCE_TYPES.map((t) => (
                <Menu.Item
                  key={t}
                  title={t}
                  onPress={() => { setEvidenceType(t); setMenuOpen(false); }}
                />
              ))}
            </Menu>
          </GlassCard>

          {/* Description */}
          <GlassCard opacity={0.88} style={styles.card}>
            <TextInput
              label="Description (optional)"
              value={description}
              onChangeText={setDescription}
              mode="outlined"
              multiline
              numberOfLines={3}
              style={styles.input}
            />
          </GlassCard>

          {/* Upload button */}
          <Button
            mode="contained"
            onPress={handleUpload}
            loading={uploading}
            disabled={!pickedFile || uploading}
            icon="cloud-upload-outline"
            style={styles.uploadBtn}
            contentStyle={styles.uploadBtnContent}
          >
            Upload Evidence
          </Button>

          <View style={{ height: 24 }} />
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

function SourceButton({ icon, label, color, onPress }: {
  icon: string; label: string; color: string; onPress: () => void;
}) {
  return (
    <TouchableOpacity style={[styles.srcBtn, { borderColor: color }]} onPress={onPress}>
      <MaterialCommunityIcons name={icon as any} size={26} color={color} />
      <Text variant="labelSmall" style={[styles.srcLabel, { color }]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  safe:    { flex: 1 },
  scroll:  { paddingBottom: 40 },
  card:    { marginBottom: 8 },
  label:   { color: '#888', fontWeight: '600', fontSize: 11, letterSpacing: 0.4, marginBottom: 6 },
  sub:     { color: '#aaa', fontSize: 11, marginTop: 2 },
  sourceGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  srcBtn: {
    width: '46%',
    borderWidth: 1.5,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(255,255,255,0.06)',
  },
  srcLabel: { fontSize: 12, fontWeight: '600' },
  fileRow:  { flexDirection: 'row', alignItems: 'center', gap: 10 },
  fileInfo: { flex: 1 },
  typeBtn:  { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 8 },
  input:    { backgroundColor: 'transparent' },
  uploadBtn: { marginHorizontal: 16, marginTop: 8, borderRadius: 10 },
  uploadBtnContent: { paddingVertical: 4 },
  driveList: {
    marginTop: 10,
    borderRadius: 10,
    backgroundColor: 'rgba(255,255,255,0.08)',
    padding: 10,
  },
  driveItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.12)',
  },
});
