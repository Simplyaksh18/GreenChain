import React, { useEffect, useState, useCallback } from "react";
import { ScrollView, StyleSheet, View, RefreshControl } from "react-native";
import { Text } from "react-native-paper";
import { SafeAreaView } from "react-native-safe-area-context";
import { MaterialCommunityIcons } from "@expo/vector-icons";

import { getMobileDashboardApi } from "../../api/dashboardApi";
import { getFPOOperationsDashboardApi } from "../../api/fpoApi";
import { getFPOActionSummary, FPOActionSummaryResponse } from "../../api/aiApi";
import { useAuthStore } from "../../store/authStore";
import { Divider } from "react-native-paper";
import { MetricCard } from "../../components/MetricCard";
import { GlassCard } from "../../components/GlassCard";
import { SectionHeader } from "../../components/SectionHeader";
import { RoleBackground } from "../../components/RoleBackground";
import { LoadingView } from "../../components/LoadingView";
import { ErrorView } from "../../components/ErrorView";
import { AIInsightsCard } from "../../components/AIInsightsCard";
import type { FpoDashboard } from "../../types";

export function FPODashboardScreen() {
  const user = useAuthStore((s) => s.user);
  const [dashboard, setDashboard] = useState<FpoDashboard | null>(null);
  const [opsDashboard, setOpsDashboard] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  // Phase 18 — AI Action Summary
  const [aiActions, setAiActions] = useState<FPOActionSummaryResponse | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  const fetchDashboard = useCallback(async () => {
    try {
      setError("");
      const [resp, ops] = await Promise.all([
        getMobileDashboardApi(),
        getFPOOperationsDashboardApi().catch(() => null),
      ]);
      setDashboard(resp.data.data as FpoDashboard);
      setOpsDashboard(ops);
    } catch {
      setError("Failed to load dashboard.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const fetchAIActions = useCallback(async () => {
    setAiLoading(true);
    setAiError(null);
    try {
      const result = await getFPOActionSummary();
      setAiActions(result);
    } catch {
      setAiError("Could not load AI action summary.");
    } finally {
      setAiLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  useEffect(() => {
    fetchAIActions();
  }, [fetchAIActions]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchDashboard();
  };

  if (loading) return <LoadingView message="Loading FPO dashboard…" />;
  if (error) return <ErrorView message={error} onRetry={fetchDashboard} />;

  if (!dashboard) {
    return (
      <ErrorView message="Failed to load dashboard." onRetry={fetchDashboard} />
    );
  }

  const d = dashboard;
  const firstName = user?.name?.split(" ")[0] ?? "Manager";

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
              colors={["#42a5f5"]}
            />
          }
        >
          {/* Welcome */}
          <GlassCard style={styles.welcomeCard} opacity={0.92}>
            <View style={styles.welcomeRow}>
              <MaterialCommunityIcons name="domain" size={36} color="#1565c0" />
              <View style={styles.welcomeText}>
                <Text variant="titleMedium" style={styles.greeting}>
                  FPO Management Dashboard
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

          {/* Linked Farms */}
          <SectionHeader
            icon="map-marker-multiple-outline"
            title="Farm Portfolio"
            light
          />
          <View style={styles.metricsRow}>
            <MetricCard
              label="Linked Farms"
              value={d.linked_farms_count}
              icon="map-marker-outline"
              highlight
            />
            <MetricCard
              label="Approved"
              value={d.approved_linked_farms}
              icon="check-decagram-outline"
            />
          </View>
          <View style={styles.metricsRow}>
            <MetricCard
              label="Farmers"
              value={d.farmers_count}
              icon="account-group-outline"
              highlight
            />
            <MetricCard
              label="Pending Reports"
              value={d.pending_reports}
              icon="file-clock-outline"
            />
          </View>

          {/* High Risk Alert */}
          <SectionHeader
            icon="alert-circle-outline"
            title="Risk Overview"
            light
          />
          <GlassCard
            style={d.high_risk_farms > 0 ? styles.alertCard : undefined}
            opacity={0.88}
          >
            <View style={styles.riskRow}>
              <MaterialCommunityIcons
                name="alert-octagon-outline"
                size={36}
                color={d.high_risk_farms > 0 ? "#e65100" : "#2e7d32"}
              />
              <View style={styles.riskText}>
                <Text
                  variant="displaySmall"
                  style={[
                    styles.riskCount,
                    { color: d.high_risk_farms > 0 ? "#e65100" : "#2e7d32" },
                  ]}
                >
                  {d.high_risk_farms}
                </Text>
                <Text variant="bodySmall" style={styles.riskHint}>
                  {d.high_risk_farms > 0
                    ? "Farm(s) with at least one high-risk verification request"
                    : "All linked farms have acceptable risk levels"}
                </Text>
              </View>
            </View>
          </GlassCard>

          {/* Approval rate */}
          <SectionHeader icon="chart-pie" title="Approval Rate" light />
          <GlassCard opacity={0.88}>
            <View style={styles.rateRow}>
              <View style={styles.rateItem}>
                <Text variant="headlineMedium" style={styles.rateValue}>
                  {d.linked_farms_count > 0
                    ? `${Math.round((d.approved_linked_farms / d.linked_farms_count) * 100)}%`
                    : "N/A"}
                </Text>
                <Text variant="labelSmall" style={styles.rateLabel}>
                  FARM APPROVAL RATE
                </Text>
              </View>
              <View style={styles.rateDivider} />
              <View style={styles.rateItem}>
                <Text variant="headlineMedium" style={styles.rateValue}>
                  {d.farmers_count > 0
                    ? `${(d.linked_farms_count / d.farmers_count).toFixed(1)}`
                    : "N/A"}
                </Text>
                <Text variant="labelSmall" style={styles.rateLabel}>
                  FARMS PER FARMER
                </Text>
              </View>
            </View>
          </GlassCard>

          {/* ── Phase 15: Operations Dashboard ──────────────────── */}
          {opsDashboard && (
            <>
              {/* Operations Summary */}
              <SectionHeader icon="chart-bar" title="Operations Summary" light />
              <View style={styles.metricsRow}>
                <MetricCard
                  label="Total Tokens"
                  value={opsDashboard.summary.total_tokens}
                  icon="leaf-circle-outline"
                  highlight
                />
                <MetricCard
                  label="Total Payouts"
                  value={opsDashboard.summary.total_payouts}
                  icon="bank-transfer-out"
                />
              </View>
              <View style={styles.metricsRow}>
                <MetricCard
                  label="Reports"
                  value={opsDashboard.summary.total_reports}
                  icon="file-chart-outline"
                />
                <MetricCard
                  label="Crop Cycles"
                  value={opsDashboard.summary.total_crop_cycles}
                  icon="sprout-outline"
                />
              </View>

              {/* Action Queue */}
              {(opsDashboard.action_queue.farms_pending_approval.length > 0 ||
                opsDashboard.action_queue.mintable_reports.length > 0 ||
                opsDashboard.action_queue.initiated_payouts.length > 0) && (
                <>
                  <SectionHeader icon="bell-ring-outline" title="Action Queue" light />
                  <GlassCard opacity={0.95}>

                    {/* Farm Approval Queue */}
                    {opsDashboard.action_queue.farms_pending_approval.length > 0 && (
                      <View>
                        <Text variant="labelMedium" style={styles.aqSection}>
                          🌾 Farms Awaiting Approval ({opsDashboard.action_queue.farms_pending_approval.length})
                        </Text>
                        {opsDashboard.action_queue.farms_pending_approval.map((f: any, i: number) => (
                          <View key={f.id} style={[styles.aqRow, i < opsDashboard.action_queue.farms_pending_approval.length - 1 && styles.aqBorder]}>
                            <MaterialCommunityIcons name="map-marker-alert-outline" size={16} color="#e65100" />
                            <View style={styles.aqInfo}>
                              <Text variant="labelMedium" style={styles.aqTitle}>{f.farm_name}</Text>
                              <Text variant="labelSmall" style={styles.aqSub}>{f.village}, {f.district}</Text>
                            </View>
                          </View>
                        ))}
                      </View>
                    )}

                    {opsDashboard.action_queue.farms_pending_approval.length > 0 &&
                      opsDashboard.action_queue.mintable_reports.length > 0 && (
                        <Divider style={styles.divider} />
                      )}

                    {/* Mintable Reports */}
                    {opsDashboard.action_queue.mintable_reports.length > 0 && (
                      <View>
                        <Text variant="labelMedium" style={styles.aqSection}>
                          🪙 Reports Ready to Mint ({opsDashboard.action_queue.mintable_reports.length})
                        </Text>
                        {opsDashboard.action_queue.mintable_reports.map((r: any, i: number) => (
                          <View key={r.report_id} style={[styles.aqRow, i < opsDashboard.action_queue.mintable_reports.length - 1 && styles.aqBorder]}>
                            <MaterialCommunityIcons name="record-circle-outline" size={16} color="#2e7d32" />
                            <View style={styles.aqInfo}>
                              <Text variant="labelMedium" style={styles.aqTitle}>Report #{r.report_id}</Text>
                              <Text variant="labelSmall" style={styles.aqSub}>{r.estimated_credits} credits estimated</Text>
                            </View>
                          </View>
                        ))}
                      </View>
                    )}

                    {opsDashboard.action_queue.mintable_reports.length > 0 &&
                      opsDashboard.action_queue.initiated_payouts.length > 0 && (
                        <Divider style={styles.divider} />
                      )}

                    {/* Initiated Payouts */}
                    {opsDashboard.action_queue.initiated_payouts.length > 0 && (
                      <View>
                        <Text variant="labelMedium" style={styles.aqSection}>
                          💸 Initiated Payouts ({opsDashboard.action_queue.initiated_payouts.length})
                        </Text>
                        {opsDashboard.action_queue.initiated_payouts.map((p: any, i: number) => (
                          <View key={p.payout_id} style={[styles.aqRow, i < opsDashboard.action_queue.initiated_payouts.length - 1 && styles.aqBorder]}>
                            <MaterialCommunityIcons name="bank-outline" size={16} color="#1565c0" />
                            <View style={styles.aqInfo}>
                              <Text variant="labelMedium" style={styles.aqTitle}>Payout #{p.payout_id}</Text>
                              <Text variant="labelSmall" style={styles.aqSub}>
                                {p.amount_credits} credits · ₹{(p.payout_amount / 100).toFixed(2)}
                              </Text>
                            </View>
                          </View>
                        ))}
                      </View>
                    )}
                  </GlassCard>
                </>
              )}

              {/* Risk Alerts */}
              {opsDashboard.risk_alerts.length > 0 && (
                <>
                  <SectionHeader icon="shield-alert-outline" title="Risk Alerts" light />
                  <GlassCard opacity={0.92} style={styles.alertCard}>
                    {opsDashboard.risk_alerts.map((ra: any, i: number) => (
                      <View key={ra.verification_id} style={[styles.aqRow, i < opsDashboard.risk_alerts.length - 1 && styles.aqBorder]}>
                        <MaterialCommunityIcons
                          name="alert-circle-outline"
                          size={16}
                          color={ra.risk_level === 'HIGH' ? '#c62828' : '#e65100'}
                        />
                        <View style={styles.aqInfo}>
                          <Text variant="labelMedium" style={[styles.aqTitle, { color: ra.risk_level === 'HIGH' ? '#c62828' : '#e65100' }]}>
                            {ra.risk_level} RISK — Report #{ra.carbon_report_id}
                          </Text>
                          <Text variant="labelSmall" style={styles.aqSub}>
                            Score: {ra.risk_score} · {ra.recommendation?.replace('_', ' ')}
                          </Text>
                        </View>
                      </View>
                    ))}
                  </GlassCard>
                </>
              )}

              {/* Recent Evidence Uploads */}
              {opsDashboard.recent_evidence.length > 0 && (
                <>
                  <SectionHeader icon="paperclip" title="Recent Evidence Uploads" light />
                  <GlassCard opacity={0.88}>
                    {opsDashboard.recent_evidence.map((ev: any, i: number) => (
                      <View key={ev.id} style={[styles.aqRow, i < opsDashboard.recent_evidence.length - 1 && styles.aqBorder]}>
                        <MaterialCommunityIcons
                          name={
                            ev.file_type === 'IMAGE' ? 'image-outline'
                            : ev.file_type === 'PDF' ? 'file-pdf-box'
                            : 'file-document-outline'
                          }
                          size={16}
                          color="#6a1b9a"
                        />
                        <View style={styles.aqInfo}>
                          <Text variant="labelMedium" style={styles.aqTitle}>
                            {ev.evidence_type ?? ev.file_type}
                          </Text>
                          {ev.description ? (
                            <Text variant="labelSmall" style={styles.aqSub}>{ev.description}</Text>
                          ) : null}
                        </View>
                        {ev.created_at && (
                          <Text variant="labelSmall" style={styles.aqDate}>
                            {new Date(ev.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                          </Text>
                        )}
                      </View>
                    ))}
                  </GlassCard>
                </>
              )}
            </>
          )}

          {/* ── AI Action Summary — Phase 18 ─────────────────────── */}
          <SectionHeader icon="brain" title="AI Action Summary" light />
          <AIInsightsCard
            loading={aiLoading}
            error={aiError}
            summary={aiActions?.summary}
            insights={
              aiActions?.action_items.map((item) => ({
                type: 'action' as const,
                message: `${item.category}: ${item.message}${item.action ? ' → ' + item.action : ''}`,
              })) ?? []
            }
            disclaimer={aiActions?.disclaimer}
            onRefresh={fetchAIActions}
          />

          <View style={styles.bottomPad} />
        </ScrollView>
      </SafeAreaView>
    </RoleBackground>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { paddingTop: 12, paddingBottom: 24 },

  welcomeCard: { marginTop: 8 },
  welcomeRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  welcomeText: { flex: 1 },
  greeting: { fontWeight: "800", color: "#1565c0" },
  dateText: { color: "#666", marginTop: 2 },

  metricsRow: { flexDirection: "row", marginHorizontal: 11 },

  alertCard: { borderLeftWidth: 4, borderLeftColor: "#e65100" },
  riskRow: { flexDirection: "row", alignItems: "center", gap: 16 },
  riskText: { flex: 1 },
  riskCount: { fontWeight: "900", lineHeight: 44 },
  riskHint: { color: "#555" },

  rateRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    paddingVertical: 8,
  },
  rateItem: { alignItems: "center", flex: 1 },
  rateDivider: { width: 1, height: 48, backgroundColor: "#e0e0e0" },
  rateValue: { fontWeight: "800", color: "#1565c0" },
  rateLabel: { color: "#888", marginTop: 4, textAlign: "center" },

  bottomPad: { height: 16 },

  // Action Queue / Operations
  divider: { marginVertical: 8 },
  aqSection: { color: '#444', fontWeight: '700', marginBottom: 6 },
  aqRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 8 },
  aqBorder: { borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  aqInfo: { flex: 1 },
  aqTitle: { color: '#333', fontWeight: '600' },
  aqSub: { color: '#888', marginTop: 2 },
  aqDate: { color: '#aaa', fontSize: 10, marginTop: 2 },
});
