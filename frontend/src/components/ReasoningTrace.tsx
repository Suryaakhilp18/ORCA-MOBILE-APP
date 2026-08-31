import { Ionicons } from "@expo/vector-icons";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Lang, trackingFor } from "@/src/context/AppContext";
import { colors, fonts, radius, spacing, type } from "@/src/theme";

// Collapsible raw reasoning trace (planner -> agents -> synthesizer) in mono.
export default function ReasoningTrace({
  trace,
  label,
  lang = "en",
}: {
  trace: { agent: string; detail: string }[];
  label: string;
  lang?: Lang;
}) {
  const [open, setOpen] = useState(false);
  if (!trace?.length) return null;
  return (
    <View style={styles.wrap}>
      <Pressable
        testID="reasoning-toggle"
        onPress={() => setOpen((o) => !o)}
        style={styles.header}
      >
        <Ionicons name="git-branch" size={14} color={colors.onSurface} />
        <Text style={[styles.headerText, { letterSpacing: trackingFor(lang, 1) }]}>
          {label} ({trace.length})
        </Text>
        <Ionicons
          name={open ? "chevron-up" : "chevron-down"}
          size={16}
          color={colors.onSurface}
        />
      </Pressable>
      {open && (
        <View testID="reasoning-body" style={styles.body}>
          {trace.map((step, i) => (
            <View key={i} style={styles.row}>
              <Text style={styles.step}>
                {String(i + 1).padStart(2, "0")}
              </Text>
              <View style={{ flex: 1 }}>
                <Text style={styles.agent}>{step.agent}</Text>
                <Text style={styles.detail}>{step.detail}</Text>
              </View>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginTop: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    overflow: "hidden",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.sm,
    backgroundColor: colors.surfaceTertiary,
  },
  headerText: {
    flex: 1,
    fontFamily: fonts.mono,
    fontSize: type.sm,
    fontWeight: "700",
    letterSpacing: 1,
    color: colors.onSurface,
  },
  body: {
    backgroundColor: colors.surfaceInverse,
    padding: spacing.sm,
    gap: spacing.sm,
  },
  row: { flexDirection: "row", gap: spacing.sm },
  step: {
    fontFamily: fonts.mono,
    fontSize: type.sm,
    color: colors.brand,
    fontWeight: "700",
  },
  agent: {
    fontFamily: fonts.mono,
    fontSize: type.sm,
    color: colors.onSurfaceInverse,
    fontWeight: "700",
  },
  detail: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.muted,
    marginTop: 2,
    lineHeight: 16,
  },
});
