/**
 * AIInsightsCard.tsx — Phase 18 AI Layer.
 *
 * Shared card component that displays AI-generated insights with:
 *   - Confidence level badge (HIGH / MEDIUM / LOW)
 *   - List of insight items with colour-coded icons
 *   - Mandatory disclaimer footer
 *   - "AI" chip so users know it's not verified data
 *
 * Used on: Farmer dashboard, FPO dashboard, Verifier report detail,
 *          Carbon report detail.
 */

import React from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { AIInsight } from '../api/aiApi';

// ── Types ──────────────────────────────────────────────────────────────────────

export interface AIInsightsCardProps {
  /** Loading state — shows spinner while fetch is in-flight */
  loading?: boolean;
  /** Error message — shown if fetch failed */
  error?: string | null;
  /** Short summary paragraph */
  summary?: string;
  /** List of insight items */
  insights?: AIInsight[];
  /** Data completeness % (0–100). Shown only when provided. */
  dataCompletenessPct?: number;
  /** Confidence level label */
  confidenceLevel?: 'HIGH' | 'MEDIUM' | 'LOW';
  /** Disclaimer string from API */
  disclaimer?: string;
  /** Called when the user taps "Refresh" */
  onRefresh?: () => void;
}

// ── Icon / colour map for insight types ───────────────────────────────────────

const INSIGHT_META: Record<
  AIInsight['type'],
  { icon: string; color: string; bg: string }
> = {
  info:     { icon: 'information-outline',       color: '#1565c0', bg: '#e3f2fd' },
  positive: { icon: 'check-circle-outline',      color: '#2e7d32', bg: '#e8f5e9' },
  warning:  { icon: 'alert-outline',             color: '#e65100', bg: '#fff3e0' },
  risk:     { icon: 'shield-alert-outline',      color: '#b71c1c', bg: '#ffebee' },
  action:   { icon: 'arrow-right-circle-outline', color: '#2e7d32', bg: '#e8f5e9' },
};

const CONFIDENCE_META: Record<
  'HIGH' | 'MEDIUM' | 'LOW',
  { color: string; label: string }
> = {
  HIGH:   { color: '#2e7d32', label: 'High confidence' },
  MEDIUM: { color: '#e65100', label: 'Medium confidence' },
  LOW:    { color: '#b71c1c', label: 'Low confidence'  },
};

// ── Component ──────────────────────────────────────────────────────────────────

export function AIInsightsCard({
  loading = false,
  error = null,
  summary,
  insights = [],
  dataCompletenessPct,
  confidenceLevel,
  disclaimer,
  onRefresh,
}: AIInsightsCardProps) {
  return (
    <View style={styles.card}>
      {/* Header row */}
      <View style={styles.headerRow}>
        <View style={styles.aiChip}>
          <MaterialCommunityIcons name="brain" size={13} color="#7b1fa2" />
          <Text style={styles.aiChipText}>AI Insights</Text>
        </View>
        {confidenceLevel && (
          <Text
            style={[
              styles.confidenceBadge,
              { color: CONFIDENCE_META[confidenceLevel].color },
            ]}
          >
            {CONFIDENCE_META[confidenceLevel].label}
          </Text>
        )}
        {onRefresh && !loading && (
          <TouchableOpacity onPress={onRefresh} style={styles.refreshBtn}>
            <MaterialCommunityIcons name="refresh" size={16} color="#555" />
          </TouchableOpacity>
        )}
      </View>

      {/* Loading */}
      {loading && (
        <View style={styles.centered}>
          <ActivityIndicator size="small" color="#7b1fa2" />
          <Text style={styles.loadingText}>Generating insights…</Text>
        </View>
      )}

      {/* Error */}
      {!loading && error && (
        <View style={styles.errorRow}>
          <MaterialCommunityIcons name="alert-circle-outline" size={16} color="#b71c1c" />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {/* Content */}
      {!loading && !error && (
        <>
          {/* Summary */}
          {summary ? (
            <Text style={styles.summary}>{summary}</Text>
          ) : null}

          {/* Completeness bar */}
          {dataCompletenessPct !== undefined && (
            <View style={styles.progressRow}>
              <Text style={styles.progressLabel}>
                Data completeness: {dataCompletenessPct}%
              </Text>
              <View style={styles.progressBar}>
                <View
                  style={[
                    styles.progressFill,
                    {
                      width: `${dataCompletenessPct}%` as any,
                      backgroundColor:
                        dataCompletenessPct >= 70
                          ? '#2e7d32'
                          : dataCompletenessPct >= 40
                          ? '#e65100'
                          : '#b71c1c',
                    },
                  ]}
                />
              </View>
            </View>
          )}

          {/* Insights list */}
          {insights.length > 0 && (
            <View style={styles.insightsList}>
              {insights.map((item, idx) => {
                const meta = INSIGHT_META[item.type] ?? INSIGHT_META.info;
                return (
                  <View
                    key={idx}
                    style={[styles.insightRow, { backgroundColor: meta.bg }]}
                  >
                    <MaterialCommunityIcons
                      name={meta.icon as any}
                      size={16}
                      color={meta.color}
                      style={styles.insightIcon}
                    />
                    <View style={styles.insightBody}>
                      {item.title ? (
                        <Text style={[styles.insightTitle, { color: meta.color }]}>
                          {item.title}
                        </Text>
                      ) : null}
                      <Text style={[styles.insightText, { color: meta.color }]}>
                        {item.message}
                      </Text>
                    </View>
                  </View>
                );
              })}
            </View>
          )}
        </>
      )}

      {/* Disclaimer — always shown when there is content */}
      {!loading && !error && disclaimer && (
        <View style={styles.disclaimerRow}>
          <MaterialCommunityIcons name="information" size={12} color="#999" />
          <Text style={styles.disclaimerText}>{disclaimer}</Text>
        </View>
      )}
    </View>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#fafafa',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e1bee7',
    padding: 14,
    marginVertical: 8,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
    gap: 8,
  },
  aiChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f3e5f5',
    borderRadius: 10,
    paddingHorizontal: 8,
    paddingVertical: 3,
    gap: 4,
  },
  aiChipText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#7b1fa2',
    letterSpacing: 0.3,
  },
  confidenceBadge: {
    fontSize: 11,
    fontWeight: '600',
    flex: 1,
  },
  refreshBtn: {
    padding: 2,
  },
  centered: {
    alignItems: 'center',
    paddingVertical: 12,
    gap: 6,
  },
  loadingText: {
    fontSize: 12,
    color: '#888',
  },
  errorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
  },
  errorText: {
    fontSize: 12,
    color: '#b71c1c',
    flex: 1,
  },
  summary: {
    fontSize: 13,
    color: '#333',
    lineHeight: 19,
    marginBottom: 10,
  },
  progressRow: {
    marginBottom: 10,
  },
  progressLabel: {
    fontSize: 11,
    color: '#666',
    marginBottom: 4,
  },
  progressBar: {
    height: 6,
    backgroundColor: '#e0e0e0',
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 3,
  },
  insightsList: {
    gap: 6,
  },
  insightRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    borderRadius: 8,
    padding: 8,
    gap: 8,
  },
  insightIcon: {
    marginTop: 2,
  },
  insightBody: {
    flex: 1,
    gap: 2,
  },
  insightTitle: {
    fontSize: 12,
    fontWeight: '700',
    lineHeight: 16,
  },
  insightText: {
    fontSize: 12,
    lineHeight: 17,
  },
  disclaimerRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginTop: 10,
    paddingTop: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#ddd',
    gap: 5,
  },
  disclaimerText: {
    flex: 1,
    fontSize: 10,
    color: '#999',
    lineHeight: 14,
    fontStyle: 'italic',
  },
});
