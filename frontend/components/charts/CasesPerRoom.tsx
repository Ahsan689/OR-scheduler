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
import { axisTick, tooltipContentStyle, tooltipLabelStyle } from "@/lib/chartTheme";

export function CasesPerRoom({ data }: { data: RoomUtilization[] }) {
  const chartData = data.map((r) => ({ room: r.room_code, cases: r.cases_ran }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--viz-grid)" vertical={false} />
        <XAxis dataKey="room" stroke="var(--viz-axis)" tick={axisTick} tickLine={false} />
        <YAxis stroke="var(--viz-axis)" tick={axisTick} tickLine={false} width={44} />
        <Tooltip
          contentStyle={tooltipContentStyle}
          labelStyle={tooltipLabelStyle}
          cursor={{ fill: "var(--viz-grid)", opacity: 0.4 }}
          formatter={(value: number) => [value, "Cases"]}
        />
        <Bar dataKey="cases" fill="var(--series-1)" radius={[4, 4, 0, 0]} name="Cases" />
      </BarChart>
    </ResponsiveContainer>
  );
}
