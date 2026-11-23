"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DailyPoint } from "@/lib/api";
import { tooltipContentStyle, tooltipLabelStyle } from "@/lib/chartTheme";
import { shortDate } from "@/lib/format";
import { useChartColors } from "@/lib/useChartColors";

export function UtilizationTrend({ data }: { data: DailyPoint[] }) {
  const colors = useChartColors();
  const chartData = data.map((d) => ({
    day: shortDate(d.day),
    utilization: d.utilization_pct,
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={colors.grid} vertical={false} />
        <XAxis
          dataKey="day"
          stroke={colors.axis}
          tick={{ fill: colors.muted, fontSize: 12 }}
          minTickGap={28}
          tickLine={false}
        />
        <YAxis
          stroke={colors.axis}
          tick={{ fill: colors.muted, fontSize: 12 }}
          tickLine={false}
          width={44}
          unit="%"
        />
        <Tooltip
          contentStyle={tooltipContentStyle}
          labelStyle={tooltipLabelStyle}
          formatter={(value: number) => [`${value.toFixed(1)}%`, "Utilization"]}
        />
        <Line
          type="monotone"
          dataKey="utilization"
          stroke={colors.series1}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
          name="Utilization"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
