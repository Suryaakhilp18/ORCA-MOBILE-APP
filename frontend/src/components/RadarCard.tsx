import { Ionicons } from "@expo/vector-icons";
import { useEffect } from "react";
import { StyleSheet, Text, View } from "react-native";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";

import { Lang, t } from "@/src/context/AppContext";
import { colors, fonts, radius, severityColor, spacing } from "@/src/theme";

type RegionLite = {
  name: string;
  state: string;
  center: { lat: number; lon: number };
  sea?: string;
};

// Live-feeling, continuously-animated radar sweep tied to the CURRENT
// region + rule-computed severity (never invented — colour and index are a
// deterministic function of `severity`). This is a DEMO BASELINE
// visualization, not a real sensor feed, clearly labelled as such.
export default function RadarCard({
  region,
  severity = "advisory",
  windKn,
  waveM,
  sstC,
  lang = "en",
}: {
  region?: RegionLite;
  severity?: "critical" | "warning" | "advisory";
  windKn?: number;
  waveM?: number;
  sstC?: number;
  lang?: Lang;
}) {
  const lat = region?.center.lat ?? 16.9891;
  const lon = region?.center.lon ?? 82.2475;
  const sector = region
    ? `${region.name} Sector · ${region.sea || "coastal waters"}`
    : "Kakinada Sector · Bay of Bengal";
  const sc = severityColor(severity);
  const index = severity === "critical" ? 32 : severity === "warning" ? 64 : 93;

  const rotation = useSharedValue(0);
  useEffect(() => {
    rotation.value = withRepeat(
      withTiming(360, { duration: 3200, easing: Easing.linear }),
      -1,
      false,
    );
  }, [rotation]);
  const sweepStyle = useAnimatedStyle(() => ({
    transform: [{ rotate: `${rotation.value}deg` }],
  }));

  return (
    <View testID="radar-card" style={styles.card}>
      <View style={styles.header}>
        <View style={styles.sysRow}>
          <View style={[styles.dot, { backgroundColor: sc.bg }]} />
          <Text style={styles.sys}>SYS://COASTAL-RADAR.01</Text>
        </View>
        <View style={styles.livePill}>
          <Text style={styles.liveText}>DEMO BASELINE</Text>
        </View>
      </View>

      <View style={styles.telemetry}>
        <View style={styles.telemetryTop}>
          <View>
            <Text style={styles.coord}>
              {lat.toFixed(4)}° N, {lon.toFixed(4)}° E
            </Text>
            <Text style={styles.sector}>{sector}</Text>
          </View>
          <View style={{ alignItems: "flex-end" }}>
            <Text style={styles.metric}>
              SST: <Text style={styles.metricVal}>{sstC != null ? `${sstC}°C` : "—"}</Text>
            </Text>
            <Text style={styles.metric}>
              {t("windLabel", lang)}: <Text style={styles.metricVal}>{windKn != null ? `${windKn} kn` : "—"}</Text>
            </Text>
            <Text style={styles.metric}>
              {t("waveLabel", lang)}: <Text style={styles.metricVal}>{waveM != null ? `${waveM} m` : "—"}</Text>
            </Text>
          </View>
        </View>

        {/* animated radar sweep */}
        <View style={styles.radarBox}>
          <View style={[styles.ring, styles.ring1]} />
          <View style={[styles.ring, styles.ring2]} />
          <View style={[styles.ring, styles.ring3, { borderColor: sc.bg }]} />
          <Animated.View style={[styles.sweepPivot, sweepStyle]}>
            <View style={[styles.sweep, { backgroundColor: sc.bg }]} />
          </Animated.View>
          <View style={[styles.centerDot, { backgroundColor: sc.bg }]} />
        </View>

        <View style={styles.footerRow}>
          <View style={styles.sysRow}>
            <Ionicons name="pulse" size={12} color={sc.bg} />
            <Text style={[styles.scanText, { color: sc.bg }]}>
              {t("radarScanning", lang)}
            </Text>
          </View>
          <Text style={styles.safetyIdx}>
            INDEX: <Text style={[styles.metricVal, { color: sc.bg }]}>{index}/100</Text>
          </Text>
        </View>
      </View>

      <View style={styles.agents}>
        <AgentChip icon="water" label="Ocean Agent" value={sstC != null ? `${sstC}°C` : "—"} />
        <AgentChip icon="cloud" label="Weather Agent" value={windKn != null ? `${windKn} kn` : "—"} />
        <AgentChip
          icon="scan"
          label="Risk Agent"
          value={severity === "critical" ? "Elevated" : severity === "warning" ? "Watch" : "Clear"}
        />
      </View>
    </View>
  );
}

function AgentChip({
  icon,
  label,
  value,
}: {
  icon: any;
  label: string;
  value: string;
}) {
  return (
    <View style={styles.chip}>
      <Ionicons name={icon} size={14} color={colors.brand} />
      <Text style={styles.chipLabel}>{label}</Text>
      <Text style={styles.chipValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    width: "100%",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: spacing.xl,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  sysRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.brand },
  sys: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.onSurfaceSecondary,
    letterSpacing: 0.5,
  },
  livePill: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  liveText: { fontFamily: fonts.mono, fontSize: 9, color: colors.brand },
  telemetry: {
    backgroundColor: colors.surfaceInverse,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  telemetryTop: { flexDirection: "row", justifyContent: "space-between" },
  coord: { fontFamily: fonts.mono, fontSize: 11, color: colors.dataBlue },
  sector: {
    fontFamily: fonts.mono,
    fontSize: 10,
    color: colors.muted,
    marginTop: 2,
  },
  metric: {
    fontFamily: fonts.mono,
    fontSize: 10,
    color: colors.onSurfaceTertiary,
  },
  metricVal: { color: colors.data },
  radarBox: {
    height: 100,
    alignItems: "center",
    justifyContent: "center",
    marginVertical: spacing.sm,
  },
  ring: {
    position: "absolute",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
  },
  ring1: { width: 96, height: 96 },
  ring2: { width: 64, height: 64 },
  ring3: { width: 32, height: 32, borderColor: colors.brand },
  sweepPivot: {
    position: "absolute",
    width: 96,
    height: 96,
    alignItems: "center",
    justifyContent: "flex-start",
  },
  sweep: {
    width: 2,
    height: 48,
    opacity: 0.75,
  },
  centerDot: {
    position: "absolute",
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  footerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  scanText: {
    fontFamily: fonts.mono,
    fontSize: 10,
    letterSpacing: 0.5,
  },
  safetyIdx: {
    fontFamily: fonts.mono,
    fontSize: 10,
    color: colors.onSurfaceTertiary,
  },
  agents: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.md },
  chip: {
    flex: 1,
    backgroundColor: colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.sm,
    alignItems: "center",
    gap: 3,
  },
  chipLabel: {
    fontFamily: fonts.mono,
    fontSize: 9,
    color: colors.muted,
    textAlign: "center",
  },
  chipValue: {
    fontFamily: fonts.mono,
    fontSize: 10,
    color: colors.data,
    fontWeight: "700",
    textAlign: "center",
  },
});
