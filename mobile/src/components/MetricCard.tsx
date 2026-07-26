import React from 'react';
import { StyleSheet, View, ViewStyle } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface Props {
  label: string;
  value: string | number;
  unit?: string;
  icon?: keyof typeof MaterialCommunityIcons.glyphMap;
  style?: ViewStyle;
  highlight?: boolean;
}

export function MetricCard({ label, value, unit, icon, style, highlight = false }: Props) {
  // Semi-transparent: background images are visible through the card
  const bg = highlight
    ? 'rgba(232,245,233,0.62)'  // light green tint, transparent
    : 'rgba(255,255,255,0.55)'; // plain glass
  const valueColor = highlight ? '#1b5e20' : '#1a1a1a';
  const iconColor  = highlight ? '#2e7d32' : '#9e9e9e';

  return (
    <View style={[styles.card, { backgroundColor: bg }, style]}>
      {icon && (
        <MaterialCommunityIcons name={icon} size={18} color={iconColor} style={styles.icon} />
      )}
      <Text variant="labelSmall" style={styles.label}>
        {label.toUpperCase()}
      </Text>
      <View style={styles.valueRow}>
        <Text variant="headlineMedium" style={[styles.value, { color: valueColor }]}>
          {value}
        </Text>
        {unit ? (
          <Text variant="labelSmall" style={styles.unit}>{unit}</Text>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    padding: 14,
    borderRadius: 16,
    margin: 5,
    flex: 1,
    minWidth: 130,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.35)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 6,
    elevation: 2,
  },
  icon:     { marginBottom: 4 },
  label:    { opacity: 0.65, marginBottom: 4, letterSpacing: 0.3 },
  valueRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 3 },
  value:    { fontWeight: '800' },
  unit:     { color: '#777', marginBottom: 4 },
});
