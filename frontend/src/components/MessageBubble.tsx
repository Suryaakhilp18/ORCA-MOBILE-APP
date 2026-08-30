import { memo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ChatMessage } from "@/src/api";
import ChartWidget from "@/src/components/ChartWidget";
import MapWidget from "@/src/components/MapWidget";
import ReasoningTrace from "@/src/components/ReasoningTrace";
import VerdictBadge from "@/src/components/VerdictBadge";
import { Lang, t } from "@/src/context/AppContext";
import { colors, fonts, radius, spacing, type } from "@/src/theme";

// Render **bold** markdown spans as bold Text, everything else plain.
function renderRich(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? (
      <Text key={i} style={{ fontWeight: "800" }}>
        {p.slice(2, -2)}
      </Text>
    ) : (
      <Text key={i}>{p}</Text>
    ),
  );
}

function MessageBubble({ msg, lang }: { msg: ChatMessage; lang: Lang }) {
  const isUser = msg.role === "user";

  if (isUser) {
    return (
      <View testID="msg-user" style={styles.userWrap}>
        <View style={styles.userBubble}>
          <Text style={styles.userText}>{msg.content}</Text>
        </View>
      </View>
    );
  }

  return (
    <View testID="msg-assistant" style={styles.aiWrap}>
      <View style={styles.aiHeader}>
        <View style={styles.aiDot} />
        <Text style={styles.aiTag}>ORCA</Text>
      </View>
      <View style={styles.aiBubble}>
        <VerdictBadge verdict={msg.verdict} />
        <Text style={styles.aiText}>{renderRich(msg.content)}</Text>

        {(msg.widgets || []).map((w, i) =>
          w.type === "map" ? (
            <MapWidget key={i} widget={w} />
          ) : (
            <ChartWidget key={i} widget={w} />
          ),
        )}

        {!!msg.citations?.length && (
          <View style={styles.sources}>
            <Text style={styles.sourcesTitle}>{t("sources", lang)}</Text>
            {msg.citations.map((c, i) => (
              <Text key={i} style={styles.sourceItem}>
                • {c}
              </Text>
            ))}
          </View>
        )}

        <ReasoningTrace
          trace={msg.reasoning_trace || []}
          label={t("reasoning", lang)}
        />
      </View>
    </View>
  );
}

export default memo(MessageBubble);

const styles = StyleSheet.create({
  userWrap: { alignItems: "flex-end", marginBottom: spacing.lg },
  userBubble: {
    maxWidth: "85%",
    backgroundColor: colors.brand,
    borderRadius: radius.md,
    borderBottomRightRadius: radius.sm,
    padding: spacing.md,
  },
  userText: { color: colors.onBrand, fontSize: type.base, lineHeight: 20 },

  aiWrap: { alignItems: "flex-start", marginBottom: spacing.lg, width: "100%" },
  aiHeader: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    marginBottom: spacing.xs,
  },
  aiTag: {
    fontFamily: fonts.mono,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 2,
    color: colors.brand,
  },
  aiDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.brand,
    marginRight: spacing.xs,
  },
  aiBubble: {
    width: "100%",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.md,
  },
  aiText: { color: colors.onSurface, fontSize: type.base, lineHeight: 21 },

  sources: {
    marginTop: spacing.md,
    borderTopWidth: 2,
    borderColor: colors.divider,
    paddingTop: spacing.sm,
  },
  sourcesTitle: {
    fontFamily: fonts.mono,
    fontSize: type.sm,
    fontWeight: "700",
    letterSpacing: 1,
    color: colors.onSurface,
    marginBottom: spacing.xs,
  },
  sourceItem: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.onSurfaceSecondary,
    lineHeight: 17,
  },
});
