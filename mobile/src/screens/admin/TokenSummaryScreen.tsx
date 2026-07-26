import React, { useCallback, useEffect, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";
import { SafeAreaView } from "react-native-safe-area-context";
import { MaterialCommunityIcons } from "@expo/vector-icons";

import { getTokenSummaryApi } from "../../api/adminApi";
import { RoleBackground } from "../../components/RoleBackground";
import { GlassCard } from "../../components/GlassCard";
import { SectionHeader } from "../../components/SectionHeader";
import { MetricCard } from "../../components/MetricCard";
import { LoadingView } from "../../components/LoadingView";
import { ErrorView } from "../../components/ErrorView";
import type { TokenSummary } from "../../types";

export function TokenSummaryScreen() {
  const [summary, setSummary] = useState<TokenSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setError("");
      const data = await getTokenSummaryApi();
      setSummary(data);
    } catch {
      setError("Failed to load token summary.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) return <LoadingView message="Loading token summary…" />;
  if (error) return <ErrorView message={error} onRetry={fetchData} />;
  if (!summary)
    return <ErrorView message="No data available." onRetry={fetchData} />;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={["bottom"]}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => {
                setRefreshing(true);
                fetchData();
              }}
              tintColor="#fff"
              colors={["#bf360c"]}
            />
          }
        >
          {/* Header card */}
          <GlassCard style={styles.headerCard} opacity={0.95}>
            <View style={styles.headerRow}>
              <MaterialCommunityIcons
                name="certificate-outline"
                size={36}
                color="#bf360c"
              />
              <View style={styles.headerText}>
                <Text variant="titleMedium" style={styles.headerTitle}>
                  Carbon Token Registry
                </Text>
                <Text variant="bodySmall" style={styles.headerSub}>
                  On-chain ERC-1155 token statistics
                </Text>
              </View>
            </View>
          </GlassCard>

          {/* Main counts */}
          <SectionHeader icon="chart-bar" title="Token Counts" light />
          <View style={styles.metricsRow}>
            <MetricCard
              label="Total Tokens"
              value={summary.total_tokens}
              icon="certificate-outline"
              highlight
            />
            <MetricCard
              label="Active"
              value={summary.active_tokens}
              icon="check-circle-outline"
              highlight
            />
          </View>
          <View style={styles.metricsRow}>
            <MetricCard
              label="Retired"
              value={summary.retired_tokens}
              icon="archive-outline"
            />
            <MetricCard
              label="Suspended"
              value={summary.suspended_tokens}
              icon="pause-circle-outline"
            />
          </View>

          {/* Credits */}
          <SectionHeader
            icon="leaf-circle-outline"
            title="Credit Volume"
            light
          />
          <GlassCard opacity={0.92}>
            <View style={styles.creditRow}>
              <View style={styles.creditItem}>
                <Text variant="headlineLarge" style={styles.creditNum}>
                  {summary.total_minted_credits.toLocaleString()}
                </Text>
                <Text variant="labelSmall" style={styles.creditLabel}>
                  TOTAL CREDITS MINTED
                </Text>
              </View>
            </View>
            <View style={styles.certRow}>
              <MaterialCommunityIcons
                name="certificate"
                size={20}
                color="#888"
              />
              <Text variant="bodySmall" style={styles.certText}>
                {summary.zero_credit_certificates} zero-credit certificate
                {summary.zero_credit_certificates !== 1 ? "s" : ""} issued
              </Text>
            </View>
          </GlassCard>

          {/* Distribution breakdown */}
          <SectionHeader icon="chart-pie" title="Status Breakdown" light />
          <GlassCard opacity={0.92}>
            {[
              {
                label: "Active",
                count: summary.active_tokens,
                total: summary.total_tokens,
                color: "#2e7d32",
              },
              {
                label: "Retired",
                count: summary.retired_tokens,
                total: summary.total_tokens,
                color: "#607d8b",
              },
              {
                label: "Suspended",
                count: summary.suspended_tokens,
                total: summary.total_tokens,
                color: "#e65100",
              },
            ].map(({ label, count, total, color }) => {
              const pct = total > 0 ? Math.round((count / total) * 100) : 0;
              return (
                <View key={label} style={styles.barRow}>
                  <Text variant="labelSmall" style={styles.barLabel}>
                    {label}
                  </Text>
                  <View style={styles.barTrack}>
                    <View
                      style={[
                        styles.barFill,
                        { width: `${pct}%` as any, backgroundColor: color },
                      ]}
                    />
                  </View>
                  <Text variant="labelSmall" style={styles.barPct}>
                    {pct}%
                  </Text>
                </View>
              );
            })}
          </GlassCard>

          <View style={styles.bottomPad} />
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { paddingTop: 8, paddingBottom: 24 },

  headerCard: { marginTop: 8 },
  headerRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  headerText: { flex: 1 },
  headerTitle: { fontWeight: "800", color: "#1b5e20" },
  headerSub: { color: "#666", marginTop: 2 },

  metricsRow: { flexDirection: "row", marginHorizontal: 11 },

  creditRow: { alignItems: "center", paddingVertical: 8 },
  creditItem: { alignItems: "center" },
  creditNum: { fontWeight: "900", color: "#2e7d32" },
  creditLabel: { color: "#888", marginTop: 2 },
  certRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 8 },
  certText: { color: "#888" },

  barRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginVertical: 6,
  },
  barLabel: { width: 64, color: "#555" },
  barTrack: {
    flex: 1,
    height: 10,
    backgroundColor: "#f0f0f0",
    borderRadius: 5,
    overflow: "hidden",
  },
  barFill: { height: 10, borderRadius: 5, minWidth: 2 },
  barPct: { width: 36, color: "#888", textAlign: "right" },

  bottomPad: { height: 16 },
});
