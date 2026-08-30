import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";

import { colors, fonts, spacing, type } from "@/src/theme";

// Prominent yellow stale/offline banner — hard black text for sun readability.
export default function StaleBanner({
  message,
  updatedAt,
}: {
  message: string;
  updatedAt?: string | null;
}) {
  let ago = "";
  if (updatedAt) {
    const diffH = Math.max(
      0,
      Math.round((Date.now() - new Date(updatedAt).getTime()) / 3600000),
    );
    ago = ` · last updated ${diffH}h ago — may be stale`;
  }
  return (
    <View testID="stale-banner" style={styles.wrap}>
      <Ionicons name="cloud-offline" size={16} color={colors.onWarning} />
      <Text style={styles.text}>
        {message}
        {ago}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.warning,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderBottomWidth: 2,
    borderColor: colors.border,
  },
  text: {
    flex: 1,
    color: colors.onWarning,
    fontFamily: fonts.mono,
    fontSize: type.sm,
    fontWeight: "700",
  },
});
