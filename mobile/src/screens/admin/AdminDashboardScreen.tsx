import React, { useEffect, useState, useCallback } from "react";
import { ScrollView, StyleSheet, View, RefreshControl } from "react-native";
import { Text } from "react-native-paper";
import { SafeAreaView } from "react-native-safe-area-context";
import { MaterialCommunityIcons } from "@expo/vector-icons";

import { getMobileDashboardApi } from "../../api/dashboardApi";
import { getSystemStatusApi } from "../../api/adminApi";
import { useAuthStore } from "../../store/authStore";
import { MetricCard } from "../../components/MetricCard";
import { GlassCard } from "../../components/GlassCard";
import { SectionHeader } from "../../components/SectionHeader";
import { InfoRow } from "../../components/InfoRow";
import { LoadingView } from "../../components/LoadingView";
import { RoleBackground } from "../../components/RoleBackground";
import { ErrorView } from "../../components/ErrorView";
import type { AdminDashboard, SystemStatus } from "../../types";

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <View
      style={[
        styles.statusDot,
        { backgroundColor: ok ? "#2e7d32" : "#c62828" },
      ]}
    />
  );
}

export function AdminDashboardScreen() {
  const user = useAuthStore((s) => s.user);

  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null);
  const [sysStatus, setSysStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      setError("");
      const [dashResp, statusResp] = await Promise.allSettled([
        getMobileDashboardApi(),
        getSystemStatusApi(),
      ]);

      if (dashResp.status === "fulfilled") {
        setDashboard(dashResp.value.data.data as AdminDashboard);
      }
      if (statusResp.status === "fulfilled") {
        setSysStatus(statusResp.value);
      }

      if (dashResp.status === "rejected") {
        setError("Failed to load dashboard.");
      }
    } catch {
      setError("Failed to load dashboard.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchAll();
  };

  if (loading) return <LoadingView message="Loading admin dashboard…" />;
  if (error) return <ErrorView message={error} onRetry={fetchAll} />;

  if (!dashboard) {
    return <ErrorView message="Failed to load dashboard." onRetry={fetchAll} />;
  }

  const d = dashboard;
  const firstName = user?.name?.split(" ")[0] ?? "Admin";

  const apiOk = sysStatus?.api_status === "ok";
  const dbOk = sysStatus?.database_status === "ok";
  const blockchainMode = sysStatus?.blockchain_mode ?? "—";
  const blockchainConfigured = sysStatus?.blockchain_configured ?? false;

  return (
    <RoleBackground>
      <SafeAreaView style={styles.safe} edges={["bottom"]}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#fff"
              colors={["#66bb6a"]}
            />
          }
        >
          {/* Welcome */}
          <GlassCard style={styles.welcomeCard} opacity={0.95}>
            <View style={styles.welcomeRow}>
              <MaterialCommunityIcons
                name="shield-crown-outline"
                size={36}
                color="#bf360c"
              />
              <View style={styles.welcomeText}>
                <Text variant="titleMedium" style={styles.greeting}>
                  Admin Control Centre
                </Text>
                <Text variant="bodySmall" style={styles.dateText}>
                  Welcome, {firstName} ·{" "}
                  {new Date().toLocaleDateString("en-IN", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
                </Text>
              </View>
            </View>
          </GlassCard>

          {/* ── Platform Health ─────────────────────────────── */}
          <SectionHeader icon="heart-pulse" title="Platform Health" light />
          <GlassCard>
            {sysStatus ? (
              <>
                <View style={styles.healthRow}>
                  <StatusDot ok={apiOk} />
                  <Text variant="bodyMedium" style={styles.healthLabel}>
                    API Server
                  </Text>
                  <Text
                    variant="labelMedium"
                    style={apiOk ? styles.okText : styles.errText}
                  >
                    {sysStatus.api_status.toUpperCase()}
                  </Text>
                </View>
                <View style={[styles.healthRow, styles.healthBorder]}>
                  <StatusDot ok={dbOk} />
                  <Text variant="bodyMedium" style={styles.healthLabel}>
                    Database
                  </Text>
                  <Text
                    variant="labelMedium"
                    style={dbOk ? styles.okText : styles.errText}
                  >
                    {sysStatus.database_status.toUpperCase()}
                  </Text>
                </View>
                <View style={[styles.healthRow, styles.healthBorder]}>
                  <MaterialCommunityIcons
                    name="link-variant"
                    size={12}
                    color="#66bb6a"
                  />
                  <Text variant="bodyMedium" style={styles.healthLabel}>
                    Blockchain Mode
                  </Text>
                  <View style={styles.modePill}>
                    <Text style={styles.modeText}>
                      {blockchainMode.toUpperCase()}
                    </Text>
                    {blockchainConfigured && (
                      <MaterialCommunityIcons
                        name="check-circle"
                        size={12}
                        color="#2e7d32"
                        style={{ marginLeft: 4 }}
                      />
                    )}
                  </View>
                </View>
                <View style={[styles.healthRow, styles.healthBorder]}>
                  <MaterialCommunityIcons
                    name="routes"
                    size={12}
                    color="#9e9e9e"
                  />
                  <Text variant="bodyMedium" style={styles.healthLabel}>
                    API Routes
                  </Text>
                  <Text variant="labelMedium" style={styles.healthValue}>
                    {sysStatus.total_routes} endpoints
                  </Text>
                </View>
                <Text variant="labelSmall" style={styles.timestamp}>
                  Last checked:{" "}
                  {new Date(sysStatus.timestamp).toLocaleTimeString("en-IN")}
                </Text>
              </>
            ) : (
              <View style={styles.emptyBox}>
                <Text variant="bodySmall" style={styles.emptyText}>
                  System status unavailable
                </Text>
              </View>
            )}
          </GlassCard>

          {/* ── Platform Activity ───────────────────────────── */}
          <SectionHeader icon="chart-line" title="Platform Activity" light />
          <View style={styles.metricsRow}>
            <MetricCard
              label="Total Farms"
              value={d.total_farms}
              icon="map-marker-multiple-outline"
              highlight
            />
            <MetricCard
              label="Total Users"
              value={d.total_users}
              icon="account-group-outline"
            />
          </View>
          <View style={styles.metricsRow}>
            <MetricCard
              label="Total Reports"
              value={d.total_reports}
              icon="file-chart-outline"
            />
            <MetricCard
              label="Verified"
              value={d.verified_reports}
              icon="shield-check-outline"
              highlight
            />
          </View>
          <View style={styles.metricsRow}>
            <MetricCard
              label="Tokens Minted"
              value={d.total_tokens}
              icon="currency-btc"
              highlight
            />
            <MetricCard
              label="tCO₂ Issued"
              value={d.total_credits.toFixed(1)}
              icon="molecule-co2"
            />
          </View>

          {/* ── Risk Monitoring ─────────────────────────────── */}
          <SectionHeader
            icon="alert-circle-outline"
            title="Risk Monitoring"
            light
          />
          <GlassCard
            style={d.high_risk_reports > 0 ? styles.riskCard : undefined}
          >
            <InfoRow
              icon="alert-octagon-outline"
              label="High Risk Reports"
              value={String(d.high_risk_reports)}
              valueColor={d.high_risk_reports > 0 ? "#c62828" : "#2e7d32"}
            />
            <InfoRow
              icon="file-cancel-outline"
              label="Unverified Reports"
              value={String(d.total_reports - d.verified_reports)}
              valueColor={
                d.total_reports - d.verified_reports > 0 ? "#e65100" : "#2e7d32"
              }
            />
            <InfoRow
              icon="percent-outline"
              label="Verification Rate"
              value={
                d.total_reports > 0
                  ? `${((d.verified_reports / d.total_reports) * 100).toFixed(1)}%`
                  : "N/A"
              }
              last
            />
          </GlassCard>

          <View style={styles.bottomPad} />
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { paddingTop: 12, paddingBottom: 24 },

  // Welcome
  welcomeCard: { marginTop: 8 },
  welcomeRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  welcomeText: { flex: 1 },
  greeting: { fontWeight: "800", color: "#bf360c" },
  dateText: { color: "#666", marginTop: 2 },

  // Health
  healthRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    gap: 10,
  },
  healthBorder: { borderTopWidth: 1, borderTopColor: "#f0f0f0" },
  healthLabel: { flex: 1, color: "#444" },
  healthValue: { color: "#555", fontWeight: "600" },
  okText: { color: "#2e7d32", fontWeight: "700" },
  errText: { color: "#c62828", fontWeight: "700" },
  modePill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#e8f5e9",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
  },
  modeText: { fontSize: 11, color: "#1b5e20", fontWeight: "700" },
  statusDot: { width: 10, height: 10, borderRadius: 5 },
  timestamp: { color: "#aaa", marginTop: 8 },

  // Metrics
  metricsRow: { flexDirection: "row", marginHorizontal: 11 },

  // Risk card
  riskCard: { borderLeftWidth: 4, borderLeftColor: "#c62828" },

  // Empty
  emptyBox: { paddingVertical: 12, alignItems: "center" },
  emptyText: { color: "#777" },

  bottomPad: { height: 16 },
});
