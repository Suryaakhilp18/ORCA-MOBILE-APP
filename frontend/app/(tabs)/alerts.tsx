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

import { api, Situation } from "@/src/api";
import AlertCard, { AlertItem } from "@/src/components/AlertCard";
import ChartWidget from "@/src/components/ChartWidget";
import RadarCard from "@/src/components/RadarCard";
import SituationCard from "@/src/components/SituationCard";
import StaleBanner from "@/src/components/StaleBanner";
import { useApp, t, trackingFor } from "@/src/context/AppContext";
import { storage } from "@/src/utils/storage";
import { colors, fonts, radius, severityColor, spacing, type } from "@/src/theme";

const CACHE_KEY = "orca_alerts_cache";

export default function AlertsScreen() {
  const { lang, userId, region } = useApp();
  const insets = useSafeAreaInsets();
  const [situation, setSituation] = useState<Situation | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [notifs, setNotifs] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stale, setStale] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, a, n] = await Promise.all([
        api.getSituation(region.id),
        api.getAlerts(region.id),
        api.getNotifications(userId),
      ]);
      setSituation(s);
      setAlerts(a.alerts || []);
      setNotifs(n || []);
      setStale(null);
      await storage.setItem(
        CACHE_KEY,
        JSON.stringify({
          situation: s,
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
          setSituation(c.situation || null);
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
  }, [userId, region.id]);

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

  const sc = severityColor(situation?.severity);

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={[styles.header, { borderBottomColor: sc.bg }]}>
        <View>
          <Text style={[styles.title, { letterSpacing: trackingFor(lang, 2) }]}>
            {t("alerts", lang).toUpperCase()}
          </Text>
          <Text style={styles.regionText}>
            {region.name}, {region.state}
          </Text>
        </View>
        <View style={[styles.headerBadge, { backgroundColor: sc.bg }]}>
          <Ionicons name="warning" size={16} color={sc.fg} />
        </View>
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
          ListHeaderComponent={
            situation ? (
              <View>
                <SituationCard situation={situation} lang={lang} />
                <RadarCard
                  region={region}
                  severity={situation.severity}
                  windKn={situation.weather_today.wind_kn}
                  waveM={situation.weather_today.wave_m}
                  sstC={situation.trends.sst.values[situation.trends.sst.values.length - 1]}
                  lang={lang}
                />
                <ChartWidget
                  widget={{
                    type: "chart",
                    title: t("windTrendTitle", lang),
                    unit: situation.trends.wind.unit,
                    labels: situation.trends.wind.labels,
                    values: situation.trends.wind.values,
                    color: colors.warning,
                  }}
                  forceColor={colors.warning}
                />
                <ChartWidget
                  widget={{
                    type: "chart",
                    title: t("waveTrendTitle", lang),
                    unit: situation.trends.wave.unit,
                    labels: situation.trends.wave.labels,
                    values: situation.trends.wave.values,
                    color: colors.dataBlue,
                  }}
                  forceColor={colors.dataBlue}
                />
                <ChartWidget
                  widget={{
                    type: "chart",
                    title: t("sstTrendTitle", lang),
                    unit: situation.trends.sst.unit,
                    labels: situation.trends.sst.labels,
                    values: situation.trends.sst.values,
                    color: colors.error,
                  }}
                  forceColor={colors.error}
                />
                <View style={{ height: spacing.md }} />
              </View>
            ) : null
          }
          renderItem={({ item: section }) => (
            <View style={{ marginBottom: spacing.lg }}>
              <Text style={[styles.sectionTitle, { letterSpacing: trackingFor(lang, 1) }]}>
                {section.header}
              </Text>
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
                  <AlertCard key={i} item={it} lang={lang} />
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
    borderBottomWidth: 2,
    borderColor: colors.border,
  },
  title: {
    fontSize: type.xl,
    fontWeight: "900",
    letterSpacing: 2,
    color: colors.onSurface,
  },
  regionText: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.muted,
    marginTop: 2,
  },
  headerBadge: {
    width: 32,
    height: 32,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
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
