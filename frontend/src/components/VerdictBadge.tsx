import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";

import { colors, fonts, spacing, type, verdictColor } from "@/src/theme";

const ICON: Record<string, any> = {
  SAFE: "checkmark-circle",
  UNSAFE: "alert-circle",
  CAUTION: "warning",
};
export default function VerdictBadge({ verdict }: { verdict?: string | null }) {
  if (!verdict) return null;
  const c = verdictColor(verdict);
  return (
    <View
      testID={`verdict-badge-${verdict.toLowerCase()}`}
      style={[styles.wrap, { backgroundColor: c.bg }]}
    >
      <Ionicons name={ICON[verdict] || "help-circle"} size={16} color={c.fg} />
      <Text style={[styles.text, { color: c.fg }]}>{verdict}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    alignSelf: "flex-start",
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    borderRadius: 999,
    marginBottom: spacing.sm,
  },
  text: {
    fontFamily: fonts.mono,
    fontSize: type.sm,
    fontWeight: "700",
    letterSpacing: 1,
  },
});
