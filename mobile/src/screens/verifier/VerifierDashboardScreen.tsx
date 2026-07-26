import React, { useEffect, useState, useCallback } from "react";
import { ScrollView, StyleSheet, View, RefreshControl } from "react-native";
import { Text } from "react-native-paper";
import { SafeAreaView } from "react-native-safe-area-context";
import { MaterialCommunityIcons } from "@expo/vector-icons";

import { getMobileDashboardApi } from "../../api/dashboardApi";
import { getPendingVerificationsApi } from "../../api/verificationApi";
import { useAuthStore } from "../../store/authStore";
import { RoleBackground } from "../../components/RoleBackground";
import { MetricCard } from "../../components/MetricCard";
import { GlassCard } from "../../components/GlassCard";
import { SectionHeader } from "../../components/SectionHeader";
import { StatusBadge } from "../../components/StatusBadge";
import { LoadingView } from "../../components/LoadingView";
import { ErrorView } from "../../components/ErrorView";
import type { VerifierDashboard, VerificationRequest } from "../../types";

const RISK_COLOR: Record<string, string> = {
  LOW: "#2e7d32",
  MEDIUM: "#e65100",
  HIGH: "#c62828",
};

export function VerifierDashboardScreen() {
  const user = useAuthStore((s) => s.user);

  const [dashboard, setDashboard] = useState<VerifierDashboard | null>(null);
  const [pending, setPending] = useState<VerificationRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      setError("");
      const [dashResp, pendingResp] = await Promise.allSettled([
        getMobileDashboardApi(),
        getPendingVerificationsApi(),
      ]);

      if (dashResp.status === "fulfilled") {
        setDashboard(dashResp.value.data.data as VerifierDashboard);
      }
      if (pendingResp.status === "fulfilled") {
        setPending(pendingResp.value);
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

  if (loading) return <LoadingView message="Loading verifier dashboard…" />;
  if (error) return <ErrorView message={error} onRetry={fetchAll} />;

  if (!dashboard) {
    return <ErrorView message="Failed to load dashboard." onRetry={fetchAll} />;
  }

  const d = dashboard;
  const firstName = user?.name?.split(" ")[0] ?? "Verifier";

  // Workload computed from pending list
  const avgRiskScore =
    pending.length > 0
      ? pending.reduce((sum, r) => sum + r.risk_score, 0) / pending.length
      : 0;
  const highRiskCount = pending.filter((r) => r.risk_level === "HIGH").length;
  const recentRequests = pending.slice(0, 5);

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
          {/* Welcome card */}
          <GlassCard style={styles.welcomeCard} opacity={0.95}>
            <View style={styles.welcomeRow}>
              <MaterialCommunityIcons
                name="shield-search"
                size={36}
                color="#1b5e20"
              />
              <View style={styles.welcomeText}>
                <Text variant="titleMedium" style={styles.greeting}>
                  Verifier Dashboard
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

          {/* ── Key Metrics ────────────────────────────────── */}
          <SectionHeader
            icon="clipboard-list-outline"
            title="Workload Overview"
            light
          />

          {/* Urgent: pending count */}
          <GlassCard
            style={d.pending_verifications > 0 ? styles.urgentCard : undefined}
          >
            <View style={styles.urgentRow}>
              <MaterialCommunityIcons
                name="timer-sand"
                size={32}
                color={d.pending_verifications > 0 ? "#e65100" : "#2e7d32"}
              />
              <View style={styles.urgentText}>
                <Text
                  variant="displaySmall"
                  style={[
                    styles.pendingCount,
                    {
                      color:
                        d.pending_verifications > 0 ? "#e65100" : "#2e7d32",
                    },
                  ]}
                >
                  {d.pending_verifications}
                </Text>
                <Text variant="bodySmall" style={styles.urgentLabel}>
                  {d.pending_verifications === 1 ? "Report" : "Reports"}{" "}
                  awaiting your review
                </Text>
              </View>
            </View>
          </GlassCard>

          <View style={styles.metricsRow}>
            <MetricCard
              label="Approved Today"
              value={d.approved_today}
              icon="check-circle-outline"
              highlight
            />
            <MetricCard
              label="Rejected Today"
              value={d.rejected_today}
              icon="close-circle-outline"
            />
          </View>
          <View style={styles.metricsRow}>
            <MetricCard
              label="High Risk"
              value={d.high_risk_reports}
              icon="alert-circle-outline"
            />
            <MetricCard
              label="In Queue"
              value={d.pending_verifications}
              icon="format-list-bulleted"
              highlight
            />
          </View>

          {/* ── Workload Summary ───────────────────────────── */}
          <SectionHeader icon="chart-bar" title="Workload Summary" light />
          <GlassCard>
            <View style={styles.summaryRow}>
              <View style={styles.summaryItem}>
                <Text variant="headlineMedium" style={styles.summaryValue}>
                  {avgRiskScore.toFixed(0)}
                </Text>
                <Text variant="labelSmall" style={styles.summaryLabel}>
                  AVG RISK SCORE
                </Text>
              </View>
              <View style={styles.summaryDivider} />
              <View style={styles.summaryItem}>
                <Text
                  variant="headlineMedium"
                  style={[
                    styles.summaryValue,
                    highRiskCount > 0 && styles.dangerText,
                  ]}
                >
                  {highRiskCount}
                </Text>
                <Text variant="labelSmall" style={styles.summaryLabel}>
                  HIGH RISK IN QUEUE
                </Text>
              </View>
              <View style={styles.summaryDivider} />
              <View style={styles.summaryItem}>
                <Text variant="headlineMedium" style={styles.summaryValue}>
                  {pending.length}
                </Text>
                <Text variant="labelSmall" style={styles.summaryLabel}>
                  TOTAL PENDING
                </Text>
              </View>
            </View>
          </GlassCard>

          {/* ── Recent Verification Requests ──────────────── */}
          <SectionHeader
            icon="clipboard-check-outline"
            title="Recent Verification Requests"
            light
          />
          <GlassCard>
            {recentRequests.length === 0 ? (
              <View style={styles.emptyBox}>
                <MaterialCommunityIcons
                  name="check-all"
                  size={32}
                  color="#66bb6a"
                />
                <Text variant="bodyMedium" style={styles.emptyText}>
                  No pending verifications
                </Text>
              </View>
            ) : (
              recentRequests.map((req, i) => (
                <View
                  key={req.id}
                  style={[
                    styles.reqRow,
                    i < recentRequests.length - 1 && styles.reqBorder,
                  ]}
                >
                  <View style={styles.reqLeft}>
                    <Text variant="labelMedium" style={styles.reqTitle}>
                      Report #{req.carbon_report_id}
                    </Text>
                    <Text variant="bodySmall" style={styles.reqDate}>
                      {new Date(req.created_at).toLocaleDateString("en-IN", {
                        day: "numeric",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </Text>
                  </View>
                  <View style={styles.reqRight}>
                    <View
                      style={[
                        styles.riskPill,
                        { backgroundColor: RISK_COLOR[req.risk_level] + "20" },
                      ]}
                    >
                      <Text
                        style={[
                          styles.riskText,
                          { color: RISK_COLOR[req.risk_level] },
                        ]}
                      >
                        {req.risk_level}
                      </Text>
                    </View>
                    <Text variant="labelSmall" style={styles.riskScore}>
                      Score: {req.risk_score}
                    </Text>
                  </View>
                  <View style={styles.reqStatus}>
                    <StatusBadge status={req.status} />
                  </View>
                </View>
              ))
            )}
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
  greeting: { fontWeight: "800", color: "#1b5e20" },
  dateText: { color: "#666", marginTop: 2 },

  // Urgent card
  urgentCard: { borderLeftWidth: 4, borderLeftColor: "#e65100" },
  urgentRow: { flexDirection: "row", alignItems: "center", gap: 16 },
  urgentText: { flex: 1 },
  pendingCount: { fontWeight: "900", lineHeight: 44 },
  urgentLabel: { color: "#555" },

  // Metrics
  metricsRow: { flexDirection: "row", marginHorizontal: 11 },

  // Summary
  summaryRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    paddingVertical: 8,
  },
  summaryItem: { alignItems: "center", flex: 1 },
  summaryDivider: { width: 1, height: 48, backgroundColor: "#e0e0e0" },
  summaryValue: { fontWeight: "800", color: "#1b5e20" },
  summaryLabel: { color: "#888", marginTop: 2, textAlign: "center" },
  dangerText: { color: "#c62828" },

  // Request list
  reqRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
    gap: 8,
  },
  reqBorder: { borderBottomWidth: 1, borderBottomColor: "#f0f0f0" },
  reqLeft: { flex: 1 },
  reqTitle: { fontWeight: "700", color: "#333" },
  reqDate: { color: "#888", marginTop: 2 },
  reqRight: { alignItems: "center", gap: 4 },
  reqStatus: {},
  riskPill: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8 },
  riskText: { fontSize: 11, fontWeight: "800" },
  riskScore: { color: "#888" },

  // Empty
  emptyBox: { paddingVertical: 20, alignItems: "center", gap: 8 },
  emptyText: { color: "#777" },

  bottomPad: { height: 16 },
});
