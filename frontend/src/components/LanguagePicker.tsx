import { Ionicons } from "@expo/vector-icons";
import { Modal, Pressable, StyleSheet, Text } from "react-native";

import { LANGUAGES, Lang, t, trackingFor, useApp } from "@/src/context/AppContext";
import { colors, fonts, radius, spacing, type } from "@/src/theme";

// Full-app language picker (English / Telugu / Hindi). Selecting a language
// here updates the entire UI (via STRINGS/t()) AND the language ORCA's AI
// agents reply in — not just the chatbot.
export default function LanguagePicker({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const { lang, setLang } = useApp();

  const pick = (code: Lang) => {
    setLang(code);
    onClose();
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.overlay} onPress={onClose}>
        <Pressable style={styles.card} onPress={(e) => e.stopPropagation()}>
          <Text style={[styles.title, { letterSpacing: trackingFor(lang, 1) }]}>
            {t("selectLanguage", lang)}
          </Text>
          {LANGUAGES.map((l) => (
            <Pressable
              key={l.code}
              testID={`lang-option-${l.code}`}
              style={[styles.row, l.code === lang && styles.rowActive]}
              onPress={() => pick(l.code)}
            >
              <Text style={styles.native}>{l.native}</Text>
              <Text style={styles.label}>{l.label}</Text>
              {l.code === lang && (
                <Ionicons name="checkmark-circle" size={18} color={colors.success} />
              )}
            </Pressable>
          ))}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(9,9,11,0.6)",
    justifyContent: "center",
    padding: spacing.lg,
  },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  title: {
    fontFamily: fonts.mono,
    fontSize: type.sm,
    fontWeight: "700",
    letterSpacing: 1,
    color: colors.onSurfaceSecondary,
    marginBottom: spacing.md,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    backgroundColor: colors.surfaceTertiary,
  },
  rowActive: { borderColor: colors.brand },
  native: {
    fontSize: type.base,
    fontWeight: "800",
    color: colors.onSurface,
    minWidth: 72,
  },
  label: {
    flex: 1,
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.muted,
  },
});
