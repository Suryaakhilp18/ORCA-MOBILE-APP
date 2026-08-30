import { useMemo } from "react";
import { StyleSheet, Text, View, useWindowDimensions } from "react-native";
import Svg, { Circle, Line, Polyline, Text as SvgText } from "react-native-svg";

import { ChartWidgetT } from "@/src/api";
import { colors, fonts, radius, spacing, type } from "@/src/theme";

// Lightweight SST/chlorophyll trend line chart (react-native-svg).
export default function ChartWidget({ widget }: { widget: ChartWidgetT }) {
  const { width } = useWindowDimensions();
  // Console palette: SST -> blue, Chlorophyll -> mint-green.
  const lineColor = /chloro/i.test(widget.title)
    ? colors.success
    : colors.dataBlue;
  const W = width - spacing.lg * 2 - 4; // minus outer padding + border
  const H = 160;
  const padL = 34;
  const padB = 22;
  const padT = 12;
  const padR = 10;

  const { points, min, max, coords } = useMemo(() => {
    const vals = widget.values;
    const mn = Math.min(...vals);
    const mx = Math.max(...vals);
    const range = mx - mn || 1;
    const innerW = W - padL - padR;
    const innerH = H - padT - padB;
    const cs = vals.map((v, i) => {
      const x = padL + (i / (vals.length - 1)) * innerW;
      const y = padT + (1 - (v - mn) / range) * innerH;
      return { x, y, v };
    });
    return {
      points: cs.map((c) => `${c.x},${c.y}`).join(" "),
      min: mn,
      max: mx,
      coords: cs,
    };
  }, [widget, W]);

  return (
    <View testID={`chart-${widget.title}`} style={styles.wrap}>
      <Text style={styles.title}>{widget.title.toUpperCase()}</Text>
      <Text style={styles.unit}>UNIT: {widget.unit}</Text>
      <Svg width={W} height={H}>
        {/* axes */}
        <Line
          x1={padL}
          y1={padT}
          x2={padL}
          y2={H - padB}
          stroke={colors.border}
          strokeWidth={2}
        />
        <Line
          x1={padL}
          y1={H - padB}
          x2={W - padR}
          y2={H - padB}
          stroke={colors.border}
          strokeWidth={2}
        />
        {/* y labels */}
        <SvgText x={4} y={padT + 6} fontSize="9" fill={colors.onSurfaceTertiary}>
          {max.toFixed(1)}
        </SvgText>
        <SvgText x={4} y={H - padB} fontSize="9" fill={colors.onSurfaceTertiary}>
          {min.toFixed(1)}
        </SvgText>
        {/* line */}
        <Polyline
          points={points}
          fill="none"
          stroke={lineColor}
          strokeWidth={3}
        />
        {coords.map((c, i) => (
          <Circle key={i} cx={c.x} cy={c.y} r={3.5} fill={lineColor} />
        ))}
        {/* x labels (first / mid / last) */}
        {[0, Math.floor(coords.length / 2), coords.length - 1].map((idx) => (
          <SvgText
            key={idx}
            x={coords[idx].x}
            y={H - padB + 14}
            fontSize="9"
            fill={colors.onSurfaceTertiary}
            textAnchor="middle"
          >
            {widget.labels[idx]}
          </SvgText>
        ))}
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.sm,
    backgroundColor: colors.surfaceInverse,
  },
  title: {
    fontFamily: fonts.mono,
    fontSize: type.sm,
    fontWeight: "700",
    letterSpacing: 1,
    color: colors.onSurface,
  },
  unit: {
    fontFamily: fonts.mono,
    fontSize: 10,
    color: colors.muted,
    marginBottom: spacing.xs,
  },
});
