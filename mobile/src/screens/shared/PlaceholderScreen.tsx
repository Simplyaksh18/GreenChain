/**
 * PlaceholderScreen — shown for screens not yet built (Phase 9B).
 * Uses RoleBackground so every tab gets the correct background image.
 */
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { RoleBackground } from '../../components/RoleBackground';
import { GlassCard } from '../../components/GlassCard';

export function PlaceholderScreen() {
  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <View style={styles.center}>
          <GlassCard style={styles.card}>
            <View style={styles.inner}>
              <MaterialCommunityIcons name="hammer-wrench" size={48} color="#2e7d32" />
              <Text variant="titleLarge" style={styles.title}>
                Coming Soon
              </Text>
              <Text variant="bodyMedium" style={styles.message}>
                This screen will be available in the next phase.
              </Text>
            </View>
          </GlassCard>
        </View>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  center: { flex: 1, justifyContent: 'center' },
  card: { marginHorizontal: 24 },
  inner: { alignItems: 'center', gap: 12, paddingVertical: 16 },
  title: { fontWeight: '800', color: '#1b5e20' },
  message: { textAlign: 'center', color: '#555', lineHeight: 22 },
});
