// App-wide state: language (EN/Telugu), chat session id, user id, selected
// coastal region (India-wide), and a Toast.
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { Animated, StyleSheet, Text } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Region } from "@/src/api";
import { storage } from "@/src/utils/storage";
import { colors, fonts, radius, spacing, type } from "@/src/theme";

export type Lang = "en" | "te" | "hi";

export const LANGUAGES: { code: Lang; label: string; native: string }[] = [
  { code: "en", label: "English", native: "English" },
  { code: "te", label: "Telugu", native: "తెలుగు" },
  { code: "hi", label: "Hindi", native: "हिन्दी" },
];

type ToastKind = "info" | "success" | "error";

const DEFAULT_REGION: Region = {
  id: "kakinada",
  name: "Kakinada",
  state: "Andhra Pradesh",
  center: { lat: 16.9891, lon: 82.2475 },
};

type AppState = {
  lang: Lang;
  setLang: (l: Lang) => void;
  sessionId: string;
  newSession: () => void;
  userId: string;
  showToast: (msg: string, kind?: ToastKind) => void;
  region: Region;
  regions: Region[];
  setRegion: (r: Region) => void;
};

const Ctx = createContext<AppState | null>(null);

export const useApp = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error("useApp must be used within AppProvider");
  return c;
};

// UI string table — English / Telugu / Hindi. Every user-facing string in
// the app should live here (never hard-code translated text in a widget).
export const STRINGS: Record<string, Record<Lang, string>> = {
  chat: { en: "Chat", te: "చాట్", hi: "चैट" },
  alerts: { en: "Alerts", te: "హెచ్చరికలు", hi: "अलर्ट" },
  saved: { en: "Saved", te: "సేవ్‌లు", hi: "सेव्ड" },
  askPlaceholder: {
    en: "Ask about tides, safety, fishing zones…",
    te: "అలలు, భద్రత, ఫిషింగ్ జోన్‌ల గురించి అడగండి…",
    hi: "ज्वार, सुरक्षा, फिशिंग ज़ोन के बारे में पूछें…",
  },
  send: { en: "SEND", te: "పంపు", hi: "भेजें" },
  emptyTitle: {
    en: "ORCA MARINE INTELLIGENCE",
    te: "ORCA సముద్ర ఇంటెలిజెన్స్",
    hi: "ORCA समुद्री इंटेलिजेंस",
  },
  emptySub: {
    en: "Ask a question to get evidence-based, explainable marine advisories.",
    te: "ఆధారసహిత, వివరణాత్మక సముద్ర సలహాల కోసం ప్రశ్న అడగండి.",
    hi: "प्रमाण-आधारित, समझने योग्य समुद्री सलाह पाने के लिए एक सवाल पूछें।",
  },
  reasoning: { en: "REASONING TRACE", te: "రీజనింగ్ ట్రేస్", hi: "रीज़निंग ट्रेस" },
  sources: { en: "SOURCES", te: "మూలాలు", hi: "स्रोत" },
  activeAlerts: {
    en: "ACTIVE HAZARDS",
    te: "సక్రియ ప్రమాదాలు",
    hi: "सक्रिय खतरे",
  },
  notifications: {
    en: "NOTIFICATIONS",
    te: "నోటిఫికేషన్లు",
    hi: "सूचनाएं",
  },
  noHazards: {
    en: "No active hazards",
    te: "సక్రియ ప్రమాదాలు లేవు",
    hi: "कोई सक्रिय खतरा नहीं",
  },
  offline: {
    en: "OFFLINE — showing last cached data",
    te: "ఆఫ్‌లైన్ — చివరిగా సేవ్ చేసిన డేటా",
    hi: "ऑफ़लाइन — पिछला सेव किया डेटा दिखा रहे हैं",
  },
  savedLocations: {
    en: "SAVED LOCATIONS",
    te: "సేవ్ చేసిన స్థానాలు",
    hi: "सेव्ड लोकेशन",
  },
  addLocation: {
    en: "SAVE A LOCATION",
    te: "స్థానం సేవ్ చేయండి",
    hi: "लोकेशन सेव करें",
  },
  selectRegion: {
    en: "SELECT COASTAL REGION",
    te: "తీర ప్రాంతం ఎంచుకోండి",
    hi: "तटीय क्षेत्र चुनें",
  },
  useCurrentLocation: {
    en: "USE CURRENT LOCATION",
    te: "ప్రస్తుత స్థానం వాడండి",
    hi: "वर्तमान लोकेशन उपयोग करें",
  },
  searchAnyLocation: {
    en: "Search any location in India…",
    te: "భారతదేశంలో ఏదైనా స్థానాన్ని వెతకండి…",
    hi: "भारत में कोई भी लोकेशन खोजें…",
  },
  marineIntelligence: {
    en: "marine intelligence",
    te: "సముద్ర ఇంటెలిజెన్స్",
    hi: "समुद्री इंटेलिजेंस",
  },
  thinking: {
    en: "ORCA is reasoning…",
    te: "ORCA విశ్లేషిస్తోంది…",
    hi: "ORCA विश्लेषण कर रहा है…",
  },
  selectLanguage: {
    en: "SELECT LANGUAGE",
    te: "భాష ఎంచుకోండి",
    hi: "भाषा चुनें",
  },
  backToRegionList: {
    en: "Back to region list",
    te: "ప్రాంతాల జాబితాకు తిరిగి వెళ్లండి",
    hi: "क्षेत्र सूची पर वापस जाएं",
  },
  name: { en: "NAME", te: "పేరు", hi: "नाम" },
  namePlaceholder: {
    en: "e.g. Morning fishing spot",
    te: "ఉదా. ఉదయం ఫిషింగ్ స్థలం",
    hi: "उदा. सुबह की फिशिंग जगह",
  },
  searchAnyLocationLabel: {
    en: "SEARCH ANY LOCATION IN INDIA",
    te: "భారతదేశంలో స్థానాన్ని వెతకండి",
    hi: "भारत में कोई भी लोकेशन खोजें",
  },
  lat: { en: "LAT", te: "అక్షాంశం", hi: "लैट" },
  lon: { en: "LON", te: "రేఖాంశం", hi: "लॉन्ग" },
  useMyLocation: {
    en: "USE MY LOCATION",
    te: "నా స్థానాన్ని ఉపయోగించండి",
    hi: "मेरी लोकेशन उपयोग करें",
  },
  vesselProfile: {
    en: "VESSEL PROFILE",
    te: "నౌక ప్రొఫైల్",
    hi: "वेसल प्रोफ़ाइल",
  },
  saveLocationBtn: {
    en: "SAVE LOCATION",
    te: "స్థానం సేవ్ చేయండి",
    hi: "लोकेशन सेव करें",
  },
  ask: { en: "ASK", te: "అడుగు", hi: "पूछें" },
  geofence: { en: "GEOFENCE", te: "జియోఫెన్స్", hi: "जियोफेंस" },
  noResultsFound: {
    en: "No results found",
    te: "ఫలితాలు లేవు",
    hi: "कोई परिणाम नहीं मिला",
  },
  savedEmptyTitle: {
    en: "Save a coordinate to get quick advisories & alerts.",
    te: "త్వరిత సలహాలు & హెచ్చరికల కోసం స్థానాన్ని సేవ్ చేయండి.",
    hi: "त्वरित सलाह और अलर्ट पाने के लिए एक लोकेशन सेव करें।",
  },
  savedEmptyHint: {
    en: "Tip: save 16.96, 82.31 to trigger a geofence-breach demo.",
    te: "టిప్: జియోఫెన్స్ డెమో కోసం 16.96, 82.31 సేవ్ చేయండి.",
    hi: "टिप: जियोफेंस डेमो देखने के लिए 16.96, 82.31 सेव करें।",
  },
  verdictSafe: { en: "SAFE", te: "సురక్షితం", hi: "सुरक्षित" },
  verdictCaution: { en: "CAUTION", te: "జాగ్రత్త", hi: "सावधानी" },
  verdictUnsafe: { en: "UNSAFE", te: "అసురక్షితం", hi: "असुरक्षित" },
  source: { en: "SRC", te: "మూలం", hi: "स्रोत" },
  toastPermissionNeeded: {
    en: "Location permission needed. Open settings.",
    te: "స్థాన అనుమతి అవసరం. సెట్టింగ్‌లను తెరవండి.",
    hi: "लोकेशन अनुमति ज़रूरी है। सेटिंग्स खोलें।",
  },
  toastUsingCurrentLocation: {
    en: "Using your current location",
    te: "మీ ప్రస్తుత స్థానాన్ని ఉపయోగిస్తోంది",
    hi: "आपकी वर्तमान लोकेशन का उपयोग किया जा रहा है",
  },
  toastCouldNotGetLocation: {
    en: "Could not get location",
    te: "స్థానాన్ని పొందలేకపోయాం",
    hi: "लोकेशन प्राप्त नहीं हो सकी",
  },
  toastNoMatchingLocation: {
    en: "No matching location found",
    te: "సరిపోలిన స్థానం కనుగొనబడలేదు",
    hi: "कोई मिलती-जुलती लोकेशन नहीं मिली",
  },
  toastSearchOffline: {
    en: "Search unavailable (offline)",
    te: "శోధన అందుబాటులో లేదు (ఆఫ్‌లైన్)",
    hi: "खोज उपलब्ध नहीं (ऑफ़लाइन)",
  },
  toastCoordsFilledFrom: {
    en: "Coordinates filled from",
    te: "నుండి కోఆర్డినేట్‌లు నింపబడ్డాయి",
    hi: "से कोऑर्डिनेट भरे गए",
  },
  toastEnterNameCoords: {
    en: "Enter a name and valid coordinates",
    te: "పేరు మరియు సరైన కోఆర్డినేట్‌లను నమోదు చేయండి",
    hi: "नाम और सही कोऑर्डिनेट डालें",
  },
  toastLocationSaved: {
    en: "Location saved",
    te: "స్థానం సేవ్ చేయబడింది",
    hi: "लोकेशन सेव हो गई",
  },
  toastCouldNotSaveOffline: {
    en: "Could not save (offline)",
    te: "సేవ్ చేయలేకపోయాం (ఆఫ్‌లైన్)",
    hi: "सेव नहीं हो सका (ऑफ़लाइन)",
  },
  toastBreach: {
    en: "BREACH",
    te: "సరిహద్దు అతిక్రమణ",
    hi: "सीमा उल्लंघन",
  },
  toastClearNoBreach: {
    en: "Clear — no boundary breach",
    te: "క్లియర్ — సరిహద్దు అతిక్రమణ లేదు",
    hi: "साफ़ — कोई सीमा उल्लंघन नहीं",
  },
  toastGeofenceFailedOffline: {
    en: "Geofence check failed (offline)",
    te: "జియోఫెన్స్ చెక్ విఫలమైంది (ఆఫ్‌లైన్)",
    hi: "जियोफेंस जांच विफल (ऑफ़लाइन)",
  },
};

export const t = (key: string, lang: Lang) =>
  STRINGS[key]?.[lang] ?? STRINGS[key]?.en ?? key;

// Letter-spacing (tracking) on uppercase headers looks great for English but
// visually breaks Telugu/Devanagari conjunct glyphs (matras get pushed apart
// from their base consonant). Use this wherever a *translated* string is
// rendered with tracking so it only applies for English.
export const trackingFor = (lang: Lang, base: number) => (lang === "en" ? base : 0);

const rid = () =>
  `sess-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  const [sessionId, setSessionId] = useState<string>("boot");
  const [region, setRegionState] = useState<Region>(DEFAULT_REGION);
  const [regions, setRegions] = useState<Region[]>([DEFAULT_REGION]);
  const userId = "demo-user";

  useEffect(() => {
    (async () => {
      const savedLang = (await storage.getItem("orca_lang", "en")) as Lang;
      setLangState(
        savedLang === "te" || savedLang === "hi" ? savedLang : "en",
      );
      let sid = (await storage.getItem("orca_session", "")) as string;
      if (!sid) {
        sid = rid();
        await storage.setItem("orca_session", sid);
      }
      setSessionId(sid);

      // Load the India-wide region roster + last-selected region (offline
      // safe: falls back to the bundled default demo region on failure).
      try {
        const savedRegionRaw = (await storage.getItem(
          "orca_region",
          "",
        )) as string;
        if (savedRegionRaw) {
          setRegionState(JSON.parse(savedRegionRaw));
        }
      } catch {
        /* ignore corrupt cache */
      }
      try {
        const list = await api.listRegions();
        if (list?.regions?.length) setRegions(list.regions);
      } catch {
        /* offline: keep default single-region list */
      }
    })();
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    storage.setItem("orca_lang", l);
  }, []);

  const setRegion = useCallback((r: Region) => {
    setRegionState(r);
    storage.setItem("orca_region", JSON.stringify(r));
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
      value={{
        lang,
        setLang,
        sessionId,
        newSession,
        userId,
        showToast,
        region,
        regions,
        setRegion,
      }}
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
