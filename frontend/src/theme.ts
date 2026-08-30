// ORCA design tokens — "Maritime Command Console" (dark).
// Deep navy-black surfaces, blue command accent, mono telemetry, green "safe"
// data, amber caution, red hazard. Rounded panels with subtle borders.
export const colors = {
  bg: "#0A0E17", // app / screen background (deep navy-black)
  surface: "#0F1520", // panels, headers, cards
  surfaceSecondary: "#0A0E17", // screen background
  surfaceTertiary: "#16202E", // inputs, chips, elevated
  onSurface: "#E6EDF3",
  onSurfaceSecondary: "#AEB9C7",
  onSurfaceTertiary: "#8B98A9",
  surfaceInverse: "#0B1119", // terminal / trace blocks
  onSurfaceInverse: "#E6EDF3",

  brand: "#3B9EFF", // command blue (primary)
  onBrand: "#FFFFFF",
  accentSoft: "#5DA8FF",

  success: "#3FD07F", // safe / OK (green)
  onSuccess: "#04140B",
  warning: "#E9B44C", // caution (amber)
  onWarning: "#1A1304",
  error: "#FF5B6E", // hazard / unsafe (red)
  onError: "#FFFFFF",

  data: "#6FE3B0", // mono telemetry values (mint/cyan-green)
  dataBlue: "#6BB8FF",

  border: "#1E2A3A",
  borderStrong: "#2A3A50",
  divider: "#1A2432",
  muted: "#5A6879",
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
};

export const radius = { sm: 8, md: 10, lg: 14, xl: 18, pill: 999 };

export const type = { sm: 12, base: 14, lg: 16, xl: 20, xxl: 24 };

export const fonts = { mono: "SpaceMono" };

// Verdict color mapping used across cards/badges.
export const verdictColor = (v?: string | null) => {
  if (v === "SAFE") return { bg: colors.success, fg: colors.onSuccess };
  if (v === "UNSAFE") return { bg: colors.error, fg: colors.onError };
  if (v === "CAUTION") return { bg: colors.warning, fg: colors.onWarning };
  return { bg: colors.surfaceTertiary, fg: colors.onSurface };
};
