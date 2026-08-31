import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";

import { Lang, t } from "@/src/context/AppContext";
import { colors, fonts, radius, spacing, type } from "@/src/theme";

const CONFIG: Record<
  string,
  { bg: string; fg: string; icon: any }
> = {
  cyclone: { bg: colors.error, fg: colors.onError, icon: "thunderstorm" },
  lightning: { bg: colors.warning, fg: colors.onWarning, icon: "flash" },
  geofence: { bg: colors.error, fg: colors.onError, icon: "warning" },
  hazard: { bg: colors.warning, fg: colors.onWarning, icon: "alert" },
};

export type AlertItem = {
  type?: string;
  severity?: string;
  title: string;
  body: string;
  source?: string;
  issued_at?: string;
  created_at?: string;
  location_name?: string;
};

export default function AlertCard({ item, lang = "en" }: { item: AlertItem; lang?: Lang }) {
  const cfg = CONFIG[item.type || ""] || {
    bg: colors.surfaceInverse,
    fg: colors.onSurfaceInverse,
    icon: "information-circle",
  };
  const ts = item.issued_at || item.created_at;
  return (
    <View testID={`alert-card-${item.type}`} style={styles.card}>
      <View style={[styles.iconStrip, { backgroundColor: cfg.bg }]}>
        <Ionicons name={cfg.icon} size={20} color={cfg.fg} />
      </View>
      <View style={styles.body}>
        <Text style={styles.title}>{item.title}</Text>
        <Text style={styles.text}>{item.body}</Text>
        <View style={styles.metaRow}>
          {!!item.source && (
            <Text style={styles.meta}>
              {t("source", lang)}: {item.source}
            </Text>
          )}
          {!!ts && (
            <Text style={styles.meta}>
              {new Date(ts).toLocaleString()}
            </Text>
          )}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    overflow: "hidden",
    marginBottom: spacing.md,
    backgroundColor: colors.surface,
  },
  iconStrip: {
    width: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  body: { flex: 1, padding: spacing.md },
  title: {
    fontSize: type.base,
    fontWeight: "800",
    color: colors.onSurface,
    marginBottom: spacing.xs,
  },
  text: {
    fontSize: type.sm,
    color: colors.onSurfaceSecondary,
    lineHeight: 19,
  },
  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  meta: { fontFamily: fonts.mono, fontSize: 10, color: colors.muted },
});
