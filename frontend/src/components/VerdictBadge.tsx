import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";

import { Lang, t, trackingFor } from "@/src/context/AppContext";
import { fonts, spacing, type, verdictColor } from "@/src/theme";

const ICON: Record<string, any> = {
  SAFE: "checkmark-circle",
  UNSAFE: "alert-circle",
  CAUTION: "warning",
};
const LABEL_KEY: Record<string, string> = {
  SAFE: "verdictSafe",
  UNSAFE: "verdictUnsafe",
  CAUTION: "verdictCaution",
};
export default function VerdictBadge({
  verdict,
  lang = "en",
}: {
  verdict?: string | null;
  lang?: Lang;
}) {
  if (!verdict) return null;
  const c = verdictColor(verdict);
  const label = LABEL_KEY[verdict] ? t(LABEL_KEY[verdict], lang) : verdict;
  return (
    <View
      testID={`verdict-badge-${verdict.toLowerCase()}`}
      style={[styles.wrap, { backgroundColor: c.bg }]}
    >
      <Ionicons name={ICON[verdict] || "help-circle"} size={16} color={c.fg} />
      <Text style={[styles.text, { color: c.fg, letterSpacing: trackingFor(lang, 1) }]}>
        {label}
      </Text>
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
