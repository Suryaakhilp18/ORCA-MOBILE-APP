import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";

import { colors, fonts, radius, spacing } from "@/src/theme";

type RegionLite = {
  name: string;
  state: string;
  center: { lat: number; lon: number };
  sea?: string;
};

// Console-style telemetry card (mirrors the ORCA command-console reference):
// coordinates + SST/Chl readouts + safety index + multi-agent status chips.
// Region-aware: coordinates/sector always reflect the currently selected
// India-wide coastal region. This is a DEMO BASELINE visualization, not a
// live radar feed — clearly labelled so it is never mistaken for real-time
// sensor data.
export default function RadarCard({ region }: { region?: RegionLite }) {
  const lat = region?.center.lat ?? 16.9891;
  const lon = region?.center.lon ?? 82.2475;
  const sector = region ? `${region.name} Sector · ${region.sea || "coastal waters"}`
                       : "Kakinada Sector · Bay of Bengal";
  return (
    <View testID="radar-card" style={styles.card}>
      <View style={styles.header}>
        <View style={styles.sysRow}>
          <View style={styles.dot} />
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
              SST: <Text style={styles.metricVal}>28.4°C</Text>
            </Text>
            <Text style={styles.metric}>
              Chl-a: <Text style={styles.metricVal}>1.82 mg/m³</Text>
            </Text>
          </View>
        </View>

        {/* radar rings motif */}
        <View style={styles.radarBox}>
          <View style={[styles.ring, styles.ring1]} />
          <View style={[styles.ring, styles.ring2]} />
          <View style={[styles.ring, styles.ring3]} />
          <View style={styles.sweep} />
        </View>

        <View style={styles.footerRow}>
          <View style={styles.sysRow}>
            <View style={[styles.dot, { backgroundColor: colors.success }]} />
            <Text style={styles.safeText}>PFZ-1 Confirmed Safe</Text>
          </View>
          <Text style={styles.safetyIdx}>
            SAFETY INDEX: <Text style={styles.metricVal}>94/100</Text>
          </Text>
        </View>
      </View>

      <View style={styles.agents}>
        <AgentChip
          icon="water"
          label="Ocean Agent"
          value="Thermocline OK"
        />
        <AgentChip icon="cloud" label="Weather Agent" value="11.4 kts" />
        <AgentChip icon="scan" label="Geofence Agent" value="Clear" />
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
    height: 92,
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
  ring1: { width: 90, height: 90 },
  ring2: { width: 60, height: 60 },
  ring3: { width: 30, height: 30, borderColor: colors.brand },
  sweep: {
    position: "absolute",
    width: 2,
    height: 45,
    backgroundColor: colors.brand,
    top: 1,
    opacity: 0.6,
  },
  footerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  safeText: { fontFamily: fonts.mono, fontSize: 11, color: colors.success },
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
