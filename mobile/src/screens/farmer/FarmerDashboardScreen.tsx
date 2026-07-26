import React, { useEffect, useState, useCallback } from "react";
import {
  ScrollView,
  StyleSheet,
  View,
  RefreshControl,
  Image,
} from "react-native";
import { Text } from "react-native-paper";
import { SafeAreaView } from "react-native-safe-area-context";

import { getMobileDashboardApi } from "../../api/dashboardApi";
import { getFarmsApi } from "../../api/farmApi";
import { getSensorsByFarmApi } from "../../api/sensorApi";
import { getReportsByFarmApi } from "../../api/carbonApi";
import { getMyWalletApi } from "../../api/tokenApi";
import { getSatelliteObsApi, getDroneObsApi } from "../../api/dashboardApi";
import { useAuthStore } from "../../store/authStore";
import { MetricCard } from "../../components/MetricCard";
import { GlassCard } from "../../components/GlassCard";
import { SectionHeader } from "../../components/SectionHeader";
import { InfoRow } from "../../components/InfoRow";
import { StatusBadge } from "../../components/StatusBadge";
import { RoleBackground } from "../../components/RoleBackground";
import { LoadingView } from "../../components/LoadingView";
import { ErrorView } from "../../components/ErrorView";
import type {
  FarmerDashboard,
  Farm,
  SensorReading,
  CarbonReport,
  CarbonToken,
  SatelliteObservation,
  DroneObservation,
} from "../../types";

const LOGO = require("../../../assets/logo-transparent.png");

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function formatDate(): string {
  return new Date().toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/**
 * Build fully dynamic, data-driven insights.
 * Every sentence must reference an actual number from the API.
 * Returns [] when there is genuinely no data to draw from.
 */
function buildInsights(
  d: FarmerDashboard,
  latestSensor: SensorReading | null,
  latestReport: CarbonReport | null,
  latestToken: CarbonToken | null,
  latestSat: SatelliteObservation | null,
  latestDrone: DroneObservation | null,
): string[] {
  const insights: string[] = [];

  if (latestSensor) {
    insights.push(
      `Latest soil moisture is ${latestSensor.soil_moisture.toFixed(2)}%, indicating ${
        latestSensor.soil_moisture > 60
          ? "high field moisture — consider water drainage."
          : latestSensor.soil_moisture > 30
            ? "moderate field moisture."
            : "low field moisture — consider irrigation."
      }`,
    );
    insights.push(
      `Estimated methane in the latest reading is ${latestSensor.estimated_methane.toFixed(4)} kg/m²/day.`,
    );
  }

  if (latestReport) {
    insights.push(
      `Your latest carbon report (#${latestReport.id}) is ${latestReport.status}.`,
    );
  }

  if (latestToken) {
    insights.push(
      `Your current token status is ${latestToken.status} (${latestToken.credit_amount.toFixed(2)} credits).`,
    );
  }

  if (latestSat) {
    insights.push(
      `Satellite observations show ${latestSat.vegetation_health} vegetation health (NDVI: ${latestSat.ndvi.toFixed(3)}).`,
    );
  }

  if (latestDrone) {
    insights.push(
      `Drone observations show ${latestDrone.standing_water_percent.toFixed(2)}% standing water in the field.`,
    );
  }

  return insights;
}

export function FarmerDashboardScreen() {
  const user = useAuthStore((s) => s.user);

  const [dashboard, setDashboard] = useState<FarmerDashboard | null>(null);
  const [farms, setFarms] = useState<Farm[]>([]);
  const [latestSensor, setLatestSensor] = useState<SensorReading | null>(null);
  const [latestReport, setLatestReport] = useState<CarbonReport | null>(null);
  const [latestToken, setLatestToken] = useState<CarbonToken | null>(null);
  const [latestSat, setLatestSat] = useState<SatelliteObservation | null>(null);
  const [latestDrone, setLatestDrone] = useState<DroneObservation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      setError("");

      // 1. Core dashboard metrics
      const dashResp = await getMobileDashboardApi();
      const d = dashResp.data.data as FarmerDashboard;
      setDashboard(d);

      // 2. Farm list
      const farmList = await getFarmsApi({ limit: 5 }).catch(
        () => [] as Farm[],
      );
      setFarms(farmList);

      if (farmList.length > 0) {
        const fid = farmList[0].id;

        // 3. Parallel data fetches
        const [sensors, reports, tokens, sat, drone] = await Promise.allSettled(
          [
            getSensorsByFarmApi(fid, { limit: 200 }),
            getReportsByFarmApi(fid, { limit: 100 }),
            getMyWalletApi({ limit: 10 }),
            getSatelliteObsApi(fid, { limit: 10 }),
            getDroneObsApi(fid, { limit: 10 }),
          ],
        );

        // Take the last element (highest ID = most recent insertion order)
        if (sensors.status === "fulfilled" && sensors.value.length > 0) {
          setLatestSensor(sensors.value[sensors.value.length - 1]);
        } else {
          setLatestSensor(null);
        }

        if (reports.status === "fulfilled" && reports.value.length > 0) {
          setLatestReport(reports.value[reports.value.length - 1]);
        } else {
          setLatestReport(null);
        }

        if (tokens.status === "fulfilled" && tokens.value.length > 0) {
          setLatestToken(tokens.value[tokens.value.length - 1]);
        } else {
          setLatestToken(null);
        }

        if (sat.status === "fulfilled" && sat.value.length > 0) {
          setLatestSat(sat.value[sat.value.length - 1]);
        } else {
          setLatestSat(null);
        }

        if (drone.status === "fulfilled" && drone.value.length > 0) {
          setLatestDrone(drone.value[drone.value.length - 1]);
        } else {
          setLatestDrone(null);
        }
      } else {
        setLatestSensor(null);
        setLatestReport(null);
        setLatestToken(null);
        setLatestSat(null);
        setLatestDrone(null);
      }
    } catch {
      setError("Failed to load dashboard. Pull down to retry.");
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

  if (loading) return <LoadingView message="Loading your dashboard…" />;
  if (error) return <ErrorView message={error} onRetry={fetchAll} />;

  if (!dashboard) {
    return (
      <ErrorView
        message="Failed to load dashboard. Pull down to retry."
        onRetry={fetchAll}
      />
    );
  }

  const d = dashboard;
  const firstName = user?.name?.split(" ")[0] ?? "Farmer";
  const insights = buildInsights(
    d,
    latestSensor,
    latestReport,
    latestToken,
    latestSat,
    latestDrone,
  );

  const reportStatusColor =
    latestReport?.status === "VERIFIED"
      ? "#2e7d32"
      : latestReport?.status === "SUBMITTED"
        ? "#e65100"
        : latestReport?.status === "REJECTED"
          ? "#c62828"
          : "#555";

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
          {/* ── SECTION 1: Welcome Header ─────────────────────────── */}
          <GlassCard style={styles.welcomeCard} opacity={0.92}>
            <View style={styles.welcomeRow}>
              <Image
                source={LOGO}
                style={styles.logoSmall}
                resizeMode="contain"
              />
              <View style={styles.welcomeText}>
                <Text variant="titleMedium" style={styles.greeting}>
                  {getGreeting()}, {firstName} 👋
                </Text>
                <Text variant="bodySmall" style={styles.dateText}>
                  {formatDate()}
                </Text>
              </View>
            </View>
            <Text variant="bodySmall" style={styles.welcomeSub}>
              Farm & carbon credit overview
            </Text>
          </GlassCard>

          {/* ── SECTION 2: Farm Summary ───────────────────────────── */}
          <SectionHeader icon="sprout" title="Farm Summary" light />
          <View style={styles.metricsRow}>
            <MetricCard
              label="Total Farms"
              value={d.my_farms_count}
              icon="map-marker-outline"
              highlight
            />
            <MetricCard
              label="Approved"
              value={d.approved_farms_count}
              icon="check-decagram-outline"
            />
          </View>
          <View style={styles.metricsRow}>
            <MetricCard
              label="Active Cycles"
              value={d.active_crop_cycles}
              icon="rotate-right"
              highlight
            />
            <MetricCard
              label="Total Reports"
              value={d.total_carbon_reports}
              icon="file-chart-outline"
            />
          </View>

          {/* ── SECTION 3: Carbon Credit Overview ────────────────── */}
          <SectionHeader icon="leaf" title="Carbon Credit Overview" light />
          <View style={styles.metricsRow}>
            <MetricCard
              label="tCO₂ Reduced"
              value={d.total_credits.toFixed(1)}
              icon="molecule-co2"
              highlight
            />
            <MetricCard
              label="Reports Verified"
              value={d.verified_reports}
              icon="shield-check-outline"
            />
          </View>
          <View style={styles.metricsRow}>
            <MetricCard
              label="Tokens Held"
              value={d.token_count}
              icon="currency-btc"
              highlight
            />
            <MetricCard
              label="Sensor Points"
              value={d.total_sensor_readings}
              icon="access-point"
            />
          </View>

          {/* ── SECTION 4: Latest Sensor Snapshot ────────────────── */}
          <SectionHeader
            icon="access-point-network"
            title="Latest Sensor Snapshot"
            light
          />
          <GlassCard opacity={0.88}>
            {latestSensor ? (
              <>
                <Text variant="labelSmall" style={styles.snapshotDate}>
                  Last reading:{" "}
                  {new Date(latestSensor.reading_time).toLocaleString("en-IN", {
                    day: "numeric",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </Text>
                <InfoRow
                  icon="water-percent"
                  label="Soil Moisture"
                  value={`${latestSensor.soil_moisture.toFixed(1)}%`}
                />
                <InfoRow
                  icon="thermometer"
                  label="Temperature"
                  value={`${latestSensor.temperature_c.toFixed(1)}°C`}
                />
                <InfoRow
                  icon="waves"
                  label="Water Depth"
                  value={`${latestSensor.water_depth_cm.toFixed(1)} cm`}
                />
                <InfoRow
                  icon="molecule-co2"
                  label="Est. Methane"
                  value={`${latestSensor.estimated_methane.toFixed(4)} kg/m²`}
                  last
                />
              </>
            ) : (
              <View style={styles.emptyBox}>
                <Text variant="bodyMedium" style={styles.emptyText}>
                  No sensor data available yet.{"\n"}Add a sensor to your farm
                  to start tracking.
                </Text>
              </View>
            )}
          </GlassCard>

          {/* ── SECTION 5: Latest Carbon Report ──────────────────── */}
          <SectionHeader
            icon="file-certificate-outline"
            title="Latest Carbon Report"
            light
          />
          <GlassCard opacity={0.88}>
            {latestReport ? (
              <>
                <View style={styles.reportHeader}>
                  <Text variant="labelMedium" style={styles.reportId}>
                    Report #{latestReport.id}
                  </Text>
                  <StatusBadge status={latestReport.status} />
                </View>
                <InfoRow
                  icon="trending-down"
                  label="CO₂ Reduction"
                  value={`${latestReport.co2e_reduction_tonnes.toFixed(3)} tCO₂`}
                />
                <InfoRow
                  icon="cash-multiple"
                  label="Credits Estimated"
                  value={`${latestReport.estimated_credits.toFixed(2)} credits`}
                  valueColor={reportStatusColor}
                />
                <InfoRow
                  icon="gas-cylinder"
                  label="Methane Reduced"
                  value={`${latestReport.methane_reduction_kg.toFixed(2)} kg`}
                  last
                />
              </>
            ) : (
              <View style={styles.emptyBox}>
                <Text variant="bodyMedium" style={styles.emptyText}>
                  No carbon reports submitted yet.{"\n"}Complete a crop cycle to
                  generate your first report.
                </Text>
              </View>
            )}
          </GlassCard>

          {/* ── SECTION 6: Insights ───────────────────────────────── */}
          <SectionHeader icon="lightbulb-outline" title="Insights" light />
          <GlassCard opacity={0.88}>
            {insights.length === 0 ? (
              <View style={styles.emptyBox}>
                <Text variant="bodyMedium" style={styles.emptyText}>
                  More sensor and MRV data is needed to generate insights.
                </Text>
              </View>
            ) : (
              insights.map((insight, i) => (
                <View
                  key={i}
                  style={[
                    styles.insightItem,
                    i < insights.length - 1 && styles.insightBorder,
                  ]}
                >
                  <Text style={styles.insightBullet}>💡</Text>
                  <Text variant="bodyMedium" style={styles.insightText}>
                    {insight}
                  </Text>
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

  welcomeCard: { marginTop: 8 },
  welcomeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginBottom: 6,
  },
  logoSmall: { width: 44, height: 44, backgroundColor: 'transparent' },
  welcomeText: { flex: 1 },
  greeting: { fontWeight: "800", color: "#1b5e20" },
  dateText: { color: "#555", marginTop: 2 },
  welcomeSub: { color: "#777" },

  metricsRow: { flexDirection: "row", marginHorizontal: 11 },

  snapshotDate: { color: "#888", marginBottom: 8 },
  reportHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  reportId: { color: "#555", fontWeight: "700" },

  emptyBox: { paddingVertical: 12, alignItems: "center" },
  emptyText: { color: "#777", textAlign: "center", lineHeight: 22 },

  insightItem: { flexDirection: "row", gap: 8, paddingVertical: 8 },
  insightBorder: { borderBottomWidth: 1, borderBottomColor: "#e8e8e8" },
  insightBullet: { fontSize: 16 },
  insightText: { flex: 1, color: "#333", lineHeight: 20 },

  bottomPad: { height: 16 },
});
