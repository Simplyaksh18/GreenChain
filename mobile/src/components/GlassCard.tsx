/**
 * GlassCard — visibly semi-transparent frosted card.
 * Default opacity 0.55 keeps background images clearly visible
 * while maintaining text readability.
 */
import React from 'react';
import { View, StyleSheet, StyleProp, ViewStyle } from 'react-native';

interface Props {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  /** White fill opacity 0–1. Default 0.55 for visible transparency. */
  opacity?: number;
}

export function GlassCard({ children, style, opacity = 0.55 }: Props) {
  return (
    <View
      style={[
        styles.card,
        { backgroundColor: `rgba(255,255,255,${opacity})` },
        style,
      ]}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 20,
    padding: 16,
    marginHorizontal: 16,
    marginVertical: 6,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.35)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 12,
    elevation: 4,
  },
});
