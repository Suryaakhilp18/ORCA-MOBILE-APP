// App-wide state: language (EN/Telugu), chat session id, user id, and a Toast.
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { Animated, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { storage } from "@/src/utils/storage";
import { colors, fonts, radius, spacing, type } from "@/src/theme";

export type Lang = "en" | "te";

type ToastKind = "info" | "success" | "error";

type AppState = {
  lang: Lang;
  setLang: (l: Lang) => void;
  sessionId: string;
  newSession: () => void;
  userId: string;
  showToast: (msg: string, kind?: ToastKind) => void;
};

const Ctx = createContext<AppState | null>(null);

export const useApp = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error("useApp must be used within AppProvider");
  return c;
};

// UI string table (EN + Telugu).
export const STRINGS: Record<string, Record<Lang, string>> = {
  chat: { en: "Chat", te: "చాట్" },
  alerts: { en: "Alerts", te: "హెచ్చరికలు" },
  saved: { en: "Saved", te: "సేవ్‌లు" },
  askPlaceholder: {
    en: "Ask about tides, safety, fishing zones…",
    te: "అలలు, భద్రత, ఫిషింగ్ జోన్‌ల గురించి అడగండి…",
  },
  send: { en: "SEND", te: "పంపు" },
  emptyTitle: { en: "ORCA MARINE INTELLIGENCE", te: "ORCA సముద్ర ఇంటెలిజెన్స్" },
  emptySub: {
    en: "Ask a question to get evidence-based, explainable marine advisories.",
    te: "ఆధారసహిత, వివరణాత్మక సముద్ర సలహాల కోసం ప్రశ్న అడగండి.",
  },
  reasoning: { en: "REASONING TRACE", te: "రీజనింగ్ ట్రేస్" },
  sources: { en: "SOURCES", te: "మూలాలు" },
  activeAlerts: { en: "ACTIVE HAZARDS", te: "సక్రియ ప్రమాదాలు" },
  notifications: { en: "NOTIFICATIONS", te: "నోటిఫికేషన్లు" },
  noHazards: { en: "No active hazards", te: "సక్రియ ప్రమాదాలు లేవు" },
  offline: {
    en: "OFFLINE — showing last cached data",
    te: "ఆఫ్‌లైన్ — చివరిగా సేవ్ చేసిన డేటా",
  },
  savedLocations: { en: "SAVED LOCATIONS", te: "సేవ్ చేసిన స్థానాలు" },
  addLocation: { en: "SAVE A LOCATION", te: "స్థానం సేవ్ చేయండి" },
};

export const t = (key: string, lang: Lang) =>
  STRINGS[key]?.[lang] ?? STRINGS[key]?.en ?? key;

const rid = () =>
  `sess-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  const [sessionId, setSessionId] = useState<string>("boot");
  const userId = "demo-user";

  useEffect(() => {
    (async () => {
      const savedLang = (await storage.getItem("orca_lang", "en")) as Lang;
      setLangState(savedLang === "te" ? "te" : "en");
      let sid = (await storage.getItem("orca_session", "")) as string;
      if (!sid) {
        sid = rid();
        await storage.setItem("orca_session", sid);
      }
      setSessionId(sid);
    })();
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    storage.setItem("orca_lang", l);
  }, []);

  const newSession = useCallback(() => {
    const sid = rid();
    setSessionId(sid);
    storage.setItem("orca_session", sid);
  }, []);

  // --- Toast ---
  const [toast, setToast] = useState<{ msg: string; kind: ToastKind } | null>(
    null,
  );
  const opacity = useRef(new Animated.Value(0)).current;
  const insets = useSafeAreaInsets();

  const showToast = useCallback(
    (msg: string, kind: ToastKind = "info") => {
      setToast({ msg, kind });
      Animated.timing(opacity, {
        toValue: 1,
        duration: 180,
        useNativeDriver: true,
      }).start();
      setTimeout(() => {
        Animated.timing(opacity, {
          toValue: 0,
          duration: 220,
          useNativeDriver: true,
        }).start(() => setToast(null));
      }, 2600);
    },
    [opacity],
  );

  const toastBg =
    toast?.kind === "error"
      ? colors.error
      : toast?.kind === "success"
        ? colors.success
        : colors.surfaceInverse;

  return (
    <Ctx.Provider
      value={{ lang, setLang, sessionId, newSession, userId, showToast }}
    >
      {children}
      {toast && (
        <Animated.View
          testID="app-toast"
          pointerEvents="none"
          style={[
            styles.toast,
            { top: insets.top + spacing.md, backgroundColor: toastBg, opacity },
          ]}
        >
          <Text style={styles.toastText}>{toast.msg}</Text>
        </Animated.View>
      )}
    </Ctx.Provider>
  );
}

const styles = StyleSheet.create({
  toast: {
    position: "absolute",
    left: spacing.lg,
    right: spacing.lg,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  toastText: {
    color: colors.onSurfaceInverse,
    fontFamily: fonts.mono,
    fontSize: type.sm,
  },
});
