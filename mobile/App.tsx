/**
 * GreenChain Mobile App — Entry Point
 * Phase 9A: Authentication + Role-based Navigation
 */
import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { PaperProvider, MD3LightTheme } from 'react-native-paper';

import { RootNavigator } from './src/navigation/RootNavigator';

// GreenChain brand theme (primary = green)
const theme = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: '#2e7d32',
    primaryContainer: '#c8e6c9',
    secondary: '#558b2f',
    secondaryContainer: '#dcedc8',
  },
};

export default function App() {
  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>
        <StatusBar style="light" />
        <RootNavigator />
      </PaperProvider>
    </SafeAreaProvider>
  );
}
