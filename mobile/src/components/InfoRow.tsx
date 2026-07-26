/**
 * InfoRow — a labeled key/value row with an optional icon.
 * Used inside GlassCard sections for sensor data, report info, etc.
 */
import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface Props {
  icon?: keyof typeof MaterialCommunityIcons.glyphMap;
  label: string;
  value: React.ReactNode;
  valueColor?: string;
  last?: boolean;
}

export function InfoRow({ icon, label, value, valueColor = '#1b5e20', last = false }: Props) {
  return (
    <View style={[styles.row, last ? undefined : styles.border]}>
      {icon ? (
        <MaterialCommunityIcons name={icon} size={18} color="#66bb6a" style={styles.icon} />
      ) : (
        <View style={styles.icon} />
      )}
      <Text variant="bodyMedium" style={styles.label}>
        {label}
      </Text>
      <Text variant="bodyMedium" style={[styles.value, { color: valueColor }]}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomColor: '#f0f0f0',
  },
  border: {
    borderBottomWidth: 1,
  },
  icon: {
    marginRight: 10,
    width: 22,
  },
  label: {
    flex: 1,
    color: '#555',
  },
  value: {
    fontWeight: '700',
    fontSize: 14,
  },
});
