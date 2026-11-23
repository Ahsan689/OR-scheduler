"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ProcedureAccuracy } from "@/lib/api";
import { axisTick, tooltipContentStyle, tooltipLabelStyle } from "@/lib/chartTheme";

export function EstimateVsActual({ data }: { data: ProcedureAccuracy[] }) {
  const chartData = data.map((p) => ({
    procedure: p.procedure_code,
    estimate: Math.round(p.avg_estimate_minutes),
    actual: Math.round(p.avg_actual_minutes),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 24 }}>
        <CartesianGrid stroke="var(--viz-grid)" vertical={false} />
        <XAxis
          dataKey="procedure"
          stroke="var(--viz-axis)"
          tick={axisTick}
          tickLine={false}
          angle={-40}
          textAnchor="end"
          interval={0}
          height={60}
        />
        <YAxis
          stroke="var(--viz-axis)"
          tick={axisTick}
          tickLine={false}
          width={44}
          unit="m"
        />
        <Tooltip
          contentStyle={tooltipContentStyle}
          labelStyle={tooltipLabelStyle}
          cursor={{ fill: "var(--viz-grid)", opacity: 0.4 }}
          formatter={(value: number, name: string) => [`${value}m`, name]}
        />
        <Legend wrapperStyle={{ fontSize: 12, color: "var(--viz-secondary)" }} />
        <Bar dataKey="estimate" fill="var(--series-1)" radius={[4, 4, 0, 0]} name="Surgeon estimate" />
        <Bar dataKey="actual" fill="var(--series-2)" radius={[4, 4, 0, 0]} name="Actual" />
      </BarChart>
    </ResponsiveContainer>
  );
}
