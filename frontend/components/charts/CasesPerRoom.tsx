"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { RoomUtilization } from "@/lib/api";
import { tooltipContentStyle, tooltipLabelStyle } from "@/lib/chartTheme";
import { useChartColors } from "@/lib/useChartColors";

export function CasesPerRoom({ data }: { data: RoomUtilization[] }) {
  const colors = useChartColors();
  const chartData = data.map((r) => ({ room: r.room_code, cases: r.cases_ran }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={colors.grid} vertical={false} />
        <XAxis
          dataKey="room"
          stroke={colors.axis}
          tick={{ fill: colors.muted, fontSize: 12 }}
          tickLine={false}
        />
        <YAxis
          stroke={colors.axis}
          tick={{ fill: colors.muted, fontSize: 12 }}
          tickLine={false}
          width={44}
        />
        <Tooltip
          contentStyle={tooltipContentStyle}
          labelStyle={tooltipLabelStyle}
          cursor={{ fill: colors.grid, opacity: 0.4 }}
          formatter={(value: number) => [value, "Cases"]}
        />
        <Bar
          dataKey="cases"
          fill={colors.series1}
          radius={[4, 4, 0, 0]}
          isAnimationActive={false}
          name="Cases"
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
