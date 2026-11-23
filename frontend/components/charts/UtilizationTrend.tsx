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
import { axisTick, tooltipContentStyle, tooltipLabelStyle } from "@/lib/chartTheme";
import { shortDate } from "@/lib/format";

export function UtilizationTrend({ data }: { data: DailyPoint[] }) {
  const chartData = data.map((d) => ({
    day: shortDate(d.day),
    utilization: d.utilization_pct,
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--viz-grid)" vertical={false} />
        <XAxis
          dataKey="day"
          stroke="var(--viz-axis)"
          tick={axisTick}
          minTickGap={28}
          tickLine={false}
        />
        <YAxis
          stroke="var(--viz-axis)"
          tick={axisTick}
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
          stroke="var(--series-1)"
          strokeWidth={2}
          dot={false}
          name="Utilization"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
