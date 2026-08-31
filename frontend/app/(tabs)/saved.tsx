import { Ionicons } from "@expo/vector-icons";
import * as Location from "expo-location";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Linking,
  Modal,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { KeyboardAvoidingView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, GeoResult } from "@/src/api";
import { useApp, t, Lang, trackingFor } from "@/src/context/AppContext";
import { colors, fonts, radius, spacing, type } from "@/src/theme";

type SavedLoc = {
  id: string;
  name: string;
  lat: number;
  lon: number;
  is_vessel?: boolean;
};

const ASK_QUERY: Record<Lang, string> = {
  en: "What are the tide, weather and sea conditions near my fishing location?",
  te: "నా ఫిషింగ్ స్థానం దగ్గర అలలు, వాతావరణం మరియు సముద్ర పరిస్థితులు ఎలా ఉన్నాయి?",
  hi: "मेरी फिशिंग जगह के पास ज्वार, मौसम और समुद्र की स्थिति कैसी है?",
};

export default function SavedScreen() {
  const { lang, userId, showToast } = useApp();
  const insets = useSafeAreaInsets();
  const [locations, setLocations] = useState<SavedLoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(false);
  const [busy, setBusy] = useState(false);

  // form
  const [name, setName] = useState("");
  const [lat, setLat] = useState("16.96");
  const [lon, setLon] = useState("82.31");
  const [isVessel, setIsVessel] = useState(false);
  const [locating, setLocating] = useState(false);
  const [searchQ, setSearchQ] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<GeoResult[] | null>(null);

  const load = useCallback(async () => {
    try {
      const list = await api.listLocations(userId);
      setLocations(list || []);
    } catch {
      /* offline */
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const useMyLocation = async () => {
    setLocating(true);
    try {
      let perm = await Location.getForegroundPermissionsAsync();
      if (perm.status !== "granted" && perm.canAskAgain) {
        perm = await Location.requestForegroundPermissionsAsync();
      }
      if (perm.status !== "granted") {
        showToast(t("toastPermissionNeeded", lang), "error");
        Linking.openSettings();
        return;
      }
      const pos = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      setLat(pos.coords.latitude.toFixed(4));
      setLon(pos.coords.longitude.toFixed(4));
      showToast(t("toastUsingCurrentLocation", lang), "success");
    } catch {
      showToast(t("toastCouldNotGetLocation", lang), "error");
    } finally {
      setLocating(false);
    }
  };

  const searchLocation = async () => {
    const q = searchQ.trim();
    if (q.length < 2) return;
    setSearching(true);
    try {
      const res = await api.geocode(q);
      if (!res.results?.length) {
        showToast(t("toastNoMatchingLocation", lang), "error");
        setSearchResults([]);
      } else {
        setSearchResults(res.results.slice(0, 5));
      }
    } catch {
      showToast(t("toastSearchOffline", lang), "error");
    } finally {
      setSearching(false);
    }
  };

  const pickSearchResult = (r: GeoResult) => {
    setLat(r.lat.toFixed(4));
    setLon(r.lon.toFixed(4));
    if (!name.trim()) setName(r.display_name.split(",")[0]);
    setSearchResults(null);
    setSearchQ("");
    showToast(`${t("toastCoordsFilledFrom", lang)} ${r.display_name}`, "success");
  };

  const save = async () => {
    const la = parseFloat(lat);
    const lo = parseFloat(lon);
    if (!name.trim() || isNaN(la) || isNaN(lo)) {
      showToast(t("toastEnterNameCoords", lang), "error");
      return;
    }
    setBusy(true);
    try {
      await api.saveLocation({
        name: name.trim(),
        lat: la,
        lon: lo,
        user_id: userId,
        is_vessel: isVessel,
      });
      showToast(t("toastLocationSaved", lang), "success");
      setModal(false);
      setName("");
      setIsVessel(false);
      setSearchQ("");
      setSearchResults(null);
      load();
    } catch {
      showToast(t("toastCouldNotSaveOffline", lang), "error");
    } finally {
      setBusy(false);
    }
  };

  const del = async (id: string) => {
    setLocations((p) => p.filter((l) => l.id !== id));
    try {
      await api.deleteLocation(id);
    } catch {
      /* ignore */
    }
  };

  const checkGeofence = async (l: SavedLoc) => {
    try {
      const res = await api.geofenceCheck({
        name: l.name,
        lat: l.lat,
        lon: l.lon,
        user_id: userId,
      });
      if (res.breach) {
        showToast(`${t("toastBreach", lang)}: ${res.zones[0].name}`, "error");
        setTimeout(() => router.push("/(tabs)/alerts"), 900);
      } else {
        showToast(t("toastClearNoBreach", lang), "success");
      }
    } catch {
      showToast(t("toastGeofenceFailedOffline", lang), "error");
    }
  };

  const askInChat = (l: SavedLoc) => {
    router.push({
      pathname: "/(tabs)",
      params: {
        q: ASK_QUERY[lang],
        lat: String(l.lat),
        lon: String(l.lon),
        locName: l.name,
      },
    });
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={[styles.title, { letterSpacing: trackingFor(lang, 2) }]}>{t("saved", lang).toUpperCase()}</Text>
        <Ionicons name="bookmark" size={22} color={colors.brand} />
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brand} />
        </View>
      ) : (
        <FlatList
          data={locations}
          keyExtractor={(l) => l.id}
          numColumns={2}
          columnWrapperStyle={{ gap: spacing.md }}
          contentContainerStyle={styles.listContent}
          ListHeaderComponent={
            <Text style={styles.sectionTitle}>{t("savedLocations", lang)}</Text>
          }
          ListEmptyComponent={
            <View testID="saved-empty" style={styles.emptyBox}>
              <Ionicons name="navigate" size={28} color={colors.muted} />
              <Text style={styles.emptyText}>{t("savedEmptyTitle", lang)}</Text>
              <Text style={styles.hint}>{t("savedEmptyHint", lang)}</Text>
            </View>
          }
          renderItem={({ item }) => (
            <View testID={`loc-card-${item.id}`} style={styles.card}>
              <View style={styles.cardTop}>
                <Ionicons
                  name={item.is_vessel ? "boat" : "location"}
                  size={16}
                  color={colors.onSurface}
                />
                <Pressable onPress={() => del(item.id)} testID={`del-${item.id}`}>
                  <Ionicons name="close" size={16} color={colors.brand} />
                </Pressable>
              </View>
              <Text style={styles.cardName} numberOfLines={1}>
                {item.name}
              </Text>
              <Text style={styles.coords}>
                {item.lat.toFixed(3)}, {item.lon.toFixed(3)}
              </Text>
              <View style={styles.cardActions}>
                <Pressable
                  testID={`ask-${item.id}`}
                  onPress={() => askInChat(item)}
                  style={styles.actionBtn}
                >
                  <Ionicons
                    name="chatbubble-ellipses"
                    size={14}
                    color={colors.onSurfaceInverse}
                  />
                  <Text style={[styles.actionText, { letterSpacing: trackingFor(lang, 1) }]}>
                    {t("ask", lang)}
                  </Text>
                </Pressable>
                <Pressable
                  testID={`geofence-${item.id}`}
                  onPress={() => checkGeofence(item)}
                  style={[styles.actionBtn, styles.actionBtnAlt]}
                >
                  <Ionicons name="scan" size={14} color={colors.onSurface} />
                  <Text
                    style={[
                      styles.actionText,
                      { color: colors.onSurface, letterSpacing: trackingFor(lang, 1) },
                    ]}
                  >
                    {t("geofence", lang)}
                  </Text>
                </Pressable>
              </View>
            </View>
          )}
        />
      )}

      <Pressable
        testID="add-location-fab"
        style={[styles.fab, { bottom: spacing.lg }]}
        onPress={() => setModal(true)}
      >
        <Ionicons name="add" size={22} color={colors.onBrand} />
        <Text style={[styles.fabText, { letterSpacing: trackingFor(lang, 1) }]}>
          {t("addLocation", lang)}
        </Text>
      </Pressable>

      {/* Add location modal */}
      <Modal visible={modal} transparent animationType="fade">
        <KeyboardAvoidingView
          behavior="padding"
          style={styles.modalOverlay}
        >
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { letterSpacing: trackingFor(lang, 1) }]}>
                {t("addLocation", lang)}
              </Text>
              <Pressable
                testID="close-modal"
                onPress={() => {
                  setModal(false);
                  setSearchQ("");
                  setSearchResults(null);
                }}
              >
                <Ionicons name="close" size={22} color={colors.onSurface} />
              </Pressable>
            </View>

        <Text style={[styles.label, { letterSpacing: trackingFor(lang, 1) }]}>{t("name", lang)}</Text>
            <TextInput
              testID="loc-name-input"
              value={name}
              onChangeText={setName}
              placeholder={t("namePlaceholder", lang)}
              placeholderTextColor={colors.muted}
              style={styles.input}
            />

            <Text style={[styles.label, { letterSpacing: trackingFor(lang, 1) }]}>{t("searchAnyLocationLabel", lang)}</Text>
            <View style={styles.searchRow}>
              <TextInput
                testID="loc-search-input"
                value={searchQ}
                onChangeText={(v) => {
                  setSearchQ(v);
                  if (!v) setSearchResults(null);
                }}
                placeholder={t("searchAnyLocation", lang)}
                placeholderTextColor={colors.muted}
                style={[styles.input, styles.flex1, { marginBottom: 0 }]}
                onSubmitEditing={searchLocation}
                returnKeyType="search"
              />
              <Pressable
                testID="loc-search-btn"
                onPress={searchLocation}
                style={styles.searchIconBtn}
                disabled={searching}
              >
                {searching ? (
                  <ActivityIndicator size="small" color={colors.onBrand} />
                ) : (
                  <Ionicons name="search" size={18} color={colors.onBrand} />
                )}
              </Pressable>
            </View>
            {searchResults !== null && (
              <View style={styles.searchResultsBox}>
                {searchResults.length === 0 ? (
                  <Text style={styles.hint}>{t("noResultsFound", lang)}</Text>
                ) : (
                  searchResults.map((r, i) => (
                    <Pressable
                      key={`${r.lat}-${r.lon}-${i}`}
                      testID={`loc-search-result-${i}`}
                      style={styles.searchResultRow}
                      onPress={() => pickSearchResult(r)}
                    >
                      <Ionicons name="pin" size={14} color={colors.brand} />
                      <Text style={styles.searchResultText} numberOfLines={2}>
                        {r.display_name}
                      </Text>
                    </Pressable>
                  ))
                )}
              </View>
            )}

            <View style={styles.row}>
              <View style={styles.flex1}>
                <Text style={[styles.label, { letterSpacing: trackingFor(lang, 1) }]}>{t("lat", lang)}</Text>
                <TextInput
                  testID="loc-lat-input"
                  value={lat}
                  onChangeText={setLat}
                  keyboardType="numbers-and-punctuation"
                  style={styles.input}
                />
              </View>
              <View style={styles.flex1}>
                <Text style={[styles.label, { letterSpacing: trackingFor(lang, 1) }]}>{t("lon", lang)}</Text>
                <TextInput
                  testID="loc-lon-input"
                  value={lon}
                  onChangeText={setLon}
                  keyboardType="numbers-and-punctuation"
                  style={styles.input}
                />
              </View>
            </View>

            <Pressable
              testID="use-my-location"
              onPress={useMyLocation}
              style={styles.gpsBtn}
            >
              {locating ? (
                <ActivityIndicator size="small" color={colors.onBrand} />
              ) : (
                <Ionicons name="locate" size={16} color={colors.onBrand} />
              )}
              <Text style={styles.gpsText}>{t("useMyLocation", lang)}</Text>
            </Pressable>

            <View style={styles.switchRow}>
              <Text style={[styles.label, { letterSpacing: trackingFor(lang, 1) }]}>{t("vesselProfile", lang)}</Text>
              <Switch
                testID="vessel-switch"
                value={isVessel}
                onValueChange={setIsVessel}
                trackColor={{ true: colors.success, false: colors.surfaceTertiary }}
              />
            </View>

            <Pressable
              testID="save-location-btn"
              onPress={save}
              disabled={busy}
              style={[styles.saveBtn, busy && { opacity: 0.6 }]}
            >
              {busy ? (
                <ActivityIndicator color={colors.onBrand} />
              ) : (
                <Text style={[styles.saveText, { letterSpacing: trackingFor(lang, 1) }]}>
                  {t("saveLocationBtn", lang)}
                </Text>
              )}
            </Pressable>
          </View>
        </KeyboardAvoidingView>
      </Modal>
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
  listContent: { padding: spacing.lg, paddingBottom: 96, gap: spacing.md },
  sectionTitle: {
    fontFamily: fonts.mono,
    fontSize: type.sm,
    fontWeight: "700",
    letterSpacing: 1,
    color: colors.onSurface,
    marginBottom: spacing.md,
  },
  emptyBox: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.xl,
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surface,
  },
  emptyText: {
    fontSize: type.sm,
    color: colors.onSurfaceSecondary,
    textAlign: "center",
  },
  hint: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.brand,
    textAlign: "center",
  },
  card: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    backgroundColor: colors.surface,
    marginBottom: spacing.md,
  },
  cardTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  cardName: {
    fontSize: type.base,
    fontWeight: "800",
    color: colors.onSurface,
    marginTop: spacing.sm,
  },
  coords: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.muted,
    marginTop: 2,
    marginBottom: spacing.md,
  },
  cardActions: { gap: spacing.xs },
  actionBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    backgroundColor: colors.brand,
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
  },
  actionBtnAlt: {
    backgroundColor: colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: colors.border,
  },
  actionText: {
    fontFamily: fonts.mono,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 1,
    color: colors.onBrand,
  },
  fab: {
    position: "absolute",
    right: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.brand,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.pill,
  },
  fabText: {
    fontFamily: fonts.mono,
    fontSize: type.sm,
    fontWeight: "700",
    letterSpacing: 1,
    color: colors.onBrand,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(9,9,11,0.6)",
    justifyContent: "center",
    padding: spacing.lg,
  },
  modalCard: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.lg,
  },
  modalTitle: {
    fontSize: type.lg,
    fontWeight: "900",
    letterSpacing: 1,
    color: colors.onSurface,
  },
  label: {
    fontFamily: fonts.mono,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 1,
    color: colors.onSurfaceSecondary,
    marginBottom: spacing.xs,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceTertiary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: type.base,
    color: colors.onSurface,
    marginBottom: spacing.md,
  },
  row: { flexDirection: "row", gap: spacing.md },
  flex1: { flex: 1 },
  searchRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.sm },
  searchIconBtn: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brand,
    borderRadius: radius.sm,
  },
  searchResultsBox: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    marginBottom: spacing.md,
    overflow: "hidden",
  },
  searchResultRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.sm,
    borderBottomWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceTertiary,
  },
  searchResultText: {
    flex: 1,
    fontSize: 11,
    color: colors.onSurface,
  },
  gpsBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    borderRadius: radius.sm,
    backgroundColor: colors.brand,
    paddingVertical: spacing.sm,
    marginBottom: spacing.md,
  },
  gpsText: {
    fontFamily: fonts.mono,
    fontSize: type.sm,
    fontWeight: "700",
    color: colors.onBrand,
  },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.lg,
  },
  saveBtn: {
    backgroundColor: colors.brand,
    paddingVertical: spacing.md,
    alignItems: "center",
    borderRadius: radius.md,
  },
  saveText: {
    fontFamily: fonts.mono,
    fontSize: type.base,
    fontWeight: "700",
    letterSpacing: 1,
    color: colors.onBrand,
  },
});
