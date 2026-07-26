import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface Props {
  icon?: keyof typeof MaterialCommunityIcons.glyphMap;
  title?: string;
  message?: string;
}

export function EmptyState({
  icon = 'inbox-outline',
  title = 'Nothing here yet',
  message = 'No data available.',
}: Props) {
  return (
    <View style={styles.container}>
      <MaterialCommunityIcons name={icon} size={56} color="#9e9e9e" />
      <Text variant="titleMedium" style={styles.title}>
        {title}
      </Text>
      <Text variant="bodyMedium" style={styles.message}>
        {message}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    gap: 12,
  },
  title: {
    fontWeight: 'bold',
  },
  message: {
    textAlign: 'center',
    opacity: 0.6,
  },
});
