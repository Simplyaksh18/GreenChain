import React from 'react';
import { StyleSheet, View, ViewStyle } from 'react-native';
import { Text } from 'react-native-paper';

type Status =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'VERIFIED'
  | 'REJECTED'
  | 'MINTED'
  | 'RETIRED'
  | 'SUSPENDED'
  | 'PENDING'
  | 'APPROVED'
  | 'MANUAL_REVIEW'
  | 'LOW'
  | 'MEDIUM'
  | 'HIGH'
  | 'CRITICAL'
  | 'ACTIVE'
  | 'INACTIVE'
  | 'COMPLETED'
  | 'CANCELLED'
  | string;

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  DRAFT: { bg: '#e0e0e0', text: '#616161' },
  SUBMITTED: { bg: '#e3f2fd', text: '#1565c0' },
  VERIFIED: { bg: '#e8f5e9', text: '#2e7d32' },
  REJECTED: { bg: '#ffebee', text: '#c62828' },
  MINTED: { bg: '#e8f5e9', text: '#2e7d32' },
  RETIRED: { bg: '#f3e5f5', text: '#6a1b9a' },
  SUSPENDED: { bg: '#fff3e0', text: '#e65100' },
  PENDING: { bg: '#fff8e1', text: '#f57f17' },
  APPROVED: { bg: '#e8f5e9', text: '#2e7d32' },
  MANUAL_REVIEW: { bg: '#e3f2fd', text: '#1565c0' },
  LOW: { bg: '#e8f5e9', text: '#2e7d32' },
  MEDIUM: { bg: '#fff8e1', text: '#f57f17' },
  HIGH: { bg: '#ffebee', text: '#c62828' },
  CRITICAL: { bg: '#880e4f', text: '#fff' },
  ACTIVE: { bg: '#e8f5e9', text: '#2e7d32' },
  INACTIVE: { bg: '#f5f5f5', text: '#9e9e9e' },
  COMPLETED: { bg: '#e3f2fd', text: '#1565c0' },
  CANCELLED: { bg: '#f5f5f5', text: '#9e9e9e' },
  PENDING_APPROVAL: { bg: '#fff8e1', text: '#f57f17' },
  ARCHIVED: { bg: '#eceff1', text: '#546e7a' },
  // Marketplace-specific (Phase 22B)
  INTERESTED: { bg: '#e3f2fd', text: '#1565c0' },
  PAID: { bg: '#e0f2f1', text: '#00695c' },
  SOLD_OUT: { bg: '#efebe9', text: '#4e342e' },
  PAUSED: { bg: '#fff8e1', text: '#f57f17' },
};

interface Props {
  status: Status;
  style?: ViewStyle;
}

export function StatusBadge({ status, style }: Props) {
  const colors = STATUS_COLORS[status] ?? { bg: '#f5f5f5', text: '#333' };

  return (
    <View style={[styles.badge, { backgroundColor: colors.bg }, style]}>
      <Text style={[styles.text, { color: colors.text }]}>{status.replace(/_/g, ' ')}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 12,
    alignSelf: 'flex-start',
  },
  text: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
});
