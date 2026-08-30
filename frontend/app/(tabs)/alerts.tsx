import { Ionicons } from "@expo/vector-icons";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import AlertCard, { AlertItem } from "@/src/components/AlertCard";
import StaleBanner from "@/src/components/StaleBanner";
import { useApp, t } from "@/src/context/AppContext";
import { storage } from "@/src/utils/storage";
import { colors, fonts, radius, spacing, type } from "@/src/theme";

const CACHE_KEY = "orca_alerts_cache";

export default function AlertsScreen() {
  const { lang, userId } = useApp();
  const insets = useSafeAreaInsets();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [notifs, setNotifs] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stale, setStale] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [a, n] = await Promise.all([
        api.getAlerts(),
        api.getNotifications(userId),
      ]);
      setAlerts(a.alerts || []);
      setNotifs(n || []);
      setStale(null);
      await storage.setItem(
        CACHE_KEY,
        JSON.stringify({
          alerts: a.alerts || [],
          notifs: n || [],
          ts: new Date().toISOString(),
        }),
      );
    } catch {
      const raw = (await storage.getItem(CACHE_KEY, "")) as string;
      if (raw) {
        try {
          const c = JSON.parse(raw);
          setAlerts(c.alerts || []);
          setNotifs(c.notifs || []);
          setStale(c.ts);
        } catch {
          /* ignore */
        }
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [userId]);

  useEffect(() => {
    load();
  }, [load]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const data = [
    { header: t("activeAlerts", lang), items: alerts },
    { header: t("notifications", lang), items: notifs },
  ];

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={styles.title}>{t("alerts", lang).toUpperCase()}</Text>
        <Ionicons name="warning" size={22} color={colors.brand} />
      </View>

      {stale && <StaleBanner message={t("offline", lang)} updatedAt={stale} />}

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brand} />
        </View>
      ) : (
        <FlatList
          data={data}
          keyExtractor={(s) => s.header}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => {
                setRefreshing(true);
                load();
              }}
              tintColor={colors.brand}
            />
          }
          contentContainerStyle={styles.listContent}
          renderItem={({ item: section }) => (
            <View style={{ marginBottom: spacing.lg }}>
              <Text style={styles.sectionTitle}>{section.header}</Text>
              {section.items.length === 0 ? (
                <View testID="no-hazards" style={styles.emptyBox}>
                  <Ionicons
                    name="checkmark-circle"
                    size={18}
                    color={colors.success}
                  />
                  <Text style={styles.emptyText}>{t("noHazards", lang)}</Text>
                </View>
              ) : (
                section.items.map((it, i) => (
                  <AlertCard key={i} item={it} />
                ))
              )}
            </View>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surfaceSecondary },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderColor: colors.border,
  },
  title: {
    fontSize: type.xl,
    fontWeight: "900",
    letterSpacing: 2,
    color: colors.onSurface,
  },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  listContent: { padding: spacing.lg },
  sectionTitle: {
    fontFamily: fonts.mono,
    fontSize: type.sm,
    fontWeight: "700",
    letterSpacing: 1,
    color: colors.onSurface,
    marginBottom: spacing.md,
  },
  emptyBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    backgroundColor: colors.surface,
  },
  emptyText: {
    fontFamily: fonts.mono,
    fontSize: type.sm,
    color: colors.success,
    fontWeight: "700",
  },
});
