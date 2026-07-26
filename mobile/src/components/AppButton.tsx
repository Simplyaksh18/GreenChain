import React from 'react';
import { StyleSheet, StyleProp, ViewStyle } from 'react-native';
import { Button } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface Props {
  /** Text label — use `label` OR `children`, not both. */
  label?: string;
  children?: React.ReactNode;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  mode?: 'contained' | 'outlined' | 'text';
  style?: StyleProp<ViewStyle>;
  /** Foreground text/icon color (passed to react-native-paper Button) */
  textColor?: string;
  /** MaterialCommunityIcons icon name shown before label */
  icon?: keyof typeof MaterialCommunityIcons.glyphMap;
  /** Background color override for contained buttons */
  buttonColor?: string;
}

export function AppButton({
  label,
  children,
  onPress,
  loading = false,
  disabled = false,
  mode = 'contained',
  style,
  textColor,
  icon,
  buttonColor,
}: Props) {
  const content = children ?? label ?? '';
  return (
    <Button
      mode={mode}
      onPress={onPress}
      disabled={disabled || loading}
      loading={loading}
      style={[styles.button, style]}
      contentStyle={styles.content}
      textColor={textColor}
      buttonColor={buttonColor}
      icon={icon as string | undefined}
    >
      {content}
    </Button>
  );
}

const styles = StyleSheet.create({
  button: {
    borderRadius: 8,
  },
  content: {
    height: 48,
  },
});
