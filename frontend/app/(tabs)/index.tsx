import { useBottomTabBarHeight } from "@react-navigation/bottom-tabs";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { KeyboardAvoidingView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, ChatMessage } from "@/src/api";
import MessageBubble from "@/src/components/MessageBubble";
import RadarCard from "@/src/components/RadarCard";
import { useApp, t, Lang } from "@/src/context/AppContext";
import { colors, fonts, radius, spacing, type } from "@/src/theme";

const SUGGESTIONS: { en: string; te: string }[] = [
  {
    en: "Is it safe to venture into the sea tomorrow morning?",
    te: "రేపు ఉదయం సముద్రంలోకి వెళ్లడం సురక్షితమేనా?",
  },
  {
    en: "Where is the nearest Potential Fishing Zone today?",
    te: "ఈ రోజు దగ్గరి ఫిషింగ్ జోన్ ఎక్కడ ఉంది?",
  },
  {
    en: "Which regions show high chlorophyll and favourable SST?",
    te: "ఏ ప్రాంతాల్లో అధిక క్లోరోఫిల్ మరియు అనుకూల SST ఉంది?",
  },
  {
    en: "Are there any lightning or cyclone alerts in my area?",
    te: "నా ప్రాంతంలో పిడుగు లేదా తుఫాను హెచ్చరికలు ఉన్నాయా?",
  },
];

const SAFE_DEFAULT: Record<Lang, string> = {
  en: "Could not verify current conditions (offline). Do not assume it is safe — check local advisories.",
  te: "ప్రస్తుత పరిస్థితులను ధృవీకరించలేకపోయాం (ఆఫ్‌లైన్). సురక్షితమని భావించవద్దు — స్థానిక సలహాలను చూడండి.",
};

export default function ChatScreen() {
  const { lang, setLang, sessionId, newSession, userId } = useApp();
  const insets = useSafeAreaInsets();
  const tabBarHeight = useBottomTabBarHeight();
  const params = useLocalSearchParams<{
    q?: string;
    lat?: string;
    lon?: string;
    locName?: string;
  }>();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [offline, setOffline] = useState(false);
  const [activeLoc, setActiveLoc] = useState<{
    name?: string;
    lat: number;
    lon: number;
  } | null>(null);
  const listRef = useRef<FlatList>(null);
  const sentParam = useRef<string | null>(null);

  const scrollEnd = useCallback(() => {
    setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 120);
  }, []);

  // Load stored conversation for this session
  useEffect(() => {
    if (sessionId === "boot") return;
    (async () => {
      try {
        const convo = await api.getConversation(sessionId);
        if (convo?.messages?.length) {
          setMessages(convo.messages);
          scrollEnd();
        }
      } catch {
        /* offline: start empty */
      }
    })();
  }, [sessionId, scrollEnd]);

  const send = useCallback(
    async (text: string, loc?: { name?: string; lat: number; lon: number } | null) => {
      const clean = text.trim();
      if (!clean || loading) return;
      const now = new Date().toISOString();
      const userMsg: ChatMessage = {
        id: `u-${Date.now()}`,
        role: "user",
        content: clean,
        created_at: now,
      };
      setMessages((p) => [...p, userMsg]);
      setInput("");
      setLoading(true);
      setOffline(false);
      scrollEnd();
      try {
        const resp = await api.chat({
          message: clean,
          session_id: sessionId,
          language: lang,
          location: loc ?? activeLoc,
          user_id: userId,
        });
        setMessages((p) => [...p, resp.assistant_message]);
      } catch {
        setOffline(true);
        setMessages((p) => [
          ...p,
          {
            id: `a-${Date.now()}`,
            role: "assistant",
            content: SAFE_DEFAULT[lang],
            created_at: new Date().toISOString(),
            verdict: null,
          },
        ]);
      } finally {
        setLoading(false);
        scrollEnd();
      }
    },
    [loading, sessionId, lang, activeLoc, userId, scrollEnd],
  );

  // Handle deep-link / param from Saved screen
  useEffect(() => {
    if (sessionId === "boot") return;
    if (params.q && sentParam.current !== params.q) {
      sentParam.current = params.q;
      const loc =
        params.lat && params.lon
          ? {
              name: params.locName,
              lat: parseFloat(params.lat),
              lon: parseFloat(params.lon),
            }
          : null;
      if (loc) setActiveLoc(loc);
      send(params.q, loc);
    }
  }, [params.q, params.lat, params.lon, params.locName, sessionId, send]);

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>ORCA</Text>
          <Text style={styles.subtitle}>
            {activeLoc?.name || "Kakinada (demo)"} · marine intelligence
          </Text>
        </View>
        <Pressable
          testID="lang-toggle"
          onPress={() => setLang(lang === "en" ? "te" : "en")}
          style={styles.langBtn}
        >
          <Text style={styles.langText}>{lang === "en" ? "EN" : "తె"}</Text>
        </Pressable>
        <Pressable
          testID="new-session"
          onPress={() => {
            newSession();
            setMessages([]);
          }}
          style={styles.iconBtn}
        >
          <Ionicons name="create-outline" size={20} color={colors.onSurface} />
        </Pressable>
      </View>

      {offline && (
        <View style={styles.offlineBar}>
          <Ionicons name="cloud-offline" size={14} color={colors.onWarning} />
          <Text style={styles.offlineText}>{t("offline", lang)}</Text>
        </View>
      )}

      <KeyboardAvoidingView
        style={styles.flex}
        behavior="translate-with-padding"
        keyboardVerticalOffset={tabBarHeight}
      >
        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(m) => m.id}
          renderItem={({ item }) => <MessageBubble msg={item} lang={lang} />}
          contentContainerStyle={styles.listContent}
          keyboardShouldPersistTaps="handled"
          onContentSizeChange={scrollEnd}
          ListEmptyComponent={
            <EmptyState lang={lang} onPick={(q) => send(q)} />
          }
          ListFooterComponent={
            loading ? (
              <View testID="typing-indicator" style={styles.typing}>
                <ActivityIndicator size="small" color={colors.brand} />
                <Text style={styles.typingText}>ORCA is reasoning…</Text>
              </View>
            ) : null
          }
        />

        {/* Input */}
        <View style={styles.inputBar}>
          <TextInput
            testID="chat-input"
            value={input}
            onChangeText={setInput}
            placeholder={t("askPlaceholder", lang)}
            placeholderTextColor={colors.muted}
            style={styles.input}
            multiline
            onSubmitEditing={() => send(input)}
          />
          <Pressable
            testID="send-button"
            onPress={() => send(input)}
            disabled={!input.trim() || loading}
            style={[
              styles.sendBtn,
              (!input.trim() || loading) && styles.sendBtnDisabled,
            ]}
          >
            <Ionicons name="arrow-up" size={20} color={colors.onBrand} />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

function EmptyState({
  lang,
  onPick,
}: {
  lang: Lang;
  onPick: (q: string) => void;
}) {
  return (
    <View testID="chat-empty" style={styles.empty}>
      <RadarCard />
      <Text style={styles.emptyTitle}>{t("emptyTitle", lang)}</Text>
      <Text style={styles.emptySub}>{t("emptySub", lang)}</Text>
      <View style={styles.suggestions}>
        {SUGGESTIONS.map((s, i) => (
          <Pressable
            key={i}
            testID={`suggestion-${i}`}
            style={styles.suggestion}
            onPress={() => onPick(s[lang])}
          >
            <Ionicons
              name="arrow-forward"
              size={14}
              color={colors.onSurface}
            />
            <Text style={styles.suggestionText}>{s[lang]}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surfaceSecondary },
  flex: { flex: 1 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderColor: colors.border,
    gap: spacing.sm,
  },
  title: {
    fontSize: type.xxl,
    fontWeight: "900",
    letterSpacing: 2,
    color: colors.onSurface,
  },
  subtitle: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.muted,
    marginTop: 2,
  },
  langBtn: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceTertiary,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    minWidth: 40,
    alignItems: "center",
  },
  langText: {
    fontFamily: fonts.mono,
    fontWeight: "700",
    color: colors.brand,
    fontSize: type.sm,
  },
  iconBtn: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceTertiary,
    padding: spacing.xs,
  },
  offlineBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.warning,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderBottomWidth: 2,
    borderColor: colors.border,
  },
  offlineText: {
    fontFamily: fonts.mono,
    fontSize: type.sm,
    fontWeight: "700",
    color: colors.onWarning,
  },
  listContent: { padding: spacing.lg, flexGrow: 1 },
  typing: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.sm,
  },
  typingText: { fontFamily: fonts.mono, fontSize: type.sm, color: colors.muted },
  inputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacing.sm,
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderColor: colors.border,
  },
  input: {
    flex: 1,
    minHeight: 44,
    maxHeight: 120,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: type.base,
    color: colors.onSurface,
    backgroundColor: colors.surfaceTertiary,
  },
  sendBtn: {
    width: 44,
    height: 44,
    backgroundColor: colors.brand,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  sendBtnDisabled: { backgroundColor: colors.surfaceTertiary },
  empty: { flex: 1, justifyContent: "center", paddingVertical: spacing.xl },
  radar: {
    width: 84,
    height: 84,
    borderWidth: 2,
    borderColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
  },
  emptyTitle: {
    fontSize: type.lg,
    fontWeight: "900",
    letterSpacing: 1,
    color: colors.onSurface,
    textAlign: "center",
  },
  emptySub: {
    fontSize: type.sm,
    color: colors.onSurfaceSecondary,
    textAlign: "center",
    marginTop: spacing.sm,
    marginBottom: spacing.xl,
    paddingHorizontal: spacing.lg,
    lineHeight: 20,
  },
  suggestions: { width: "100%", gap: spacing.sm },
  suggestion: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    backgroundColor: colors.surface,
  },
  suggestionText: {
    flex: 1,
    fontSize: type.sm,
    color: colors.onSurface,
    fontWeight: "600",
  },
});
