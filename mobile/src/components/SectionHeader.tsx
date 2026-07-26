import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface Props {
  icon: keyof typeof MaterialCommunityIcons.glyphMap;
  title: string;
  style?: ViewStyle;
  light?: boolean; // true = white text (for use over dark backgrounds)
}

export function SectionHeader({ icon, title, style, light = false }: Props) {
  const color = light ? '#fff' : '#2e7d32';
  const textColor = light ? '#fff' : '#1b5e20';

  return (
    <View style={[styles.row, style]}>
      <MaterialCommunityIcons name={icon} size={20} color={color} />
      <Text variant="titleMedium" style={[styles.title, { color: textColor }]}>
        {title}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 20,
    marginBottom: 8,
    marginHorizontal: 16,
  },
  title: {
    fontWeight: '700',
    letterSpacing: 0.3,
  },
});
