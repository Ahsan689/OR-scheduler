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
import { tooltipContentStyle, tooltipLabelStyle } from "@/lib/chartTheme";
import { useChartColors } from "@/lib/useChartColors";

export function EstimateVsActual({ data }: { data: ProcedureAccuracy[] }) {
  const colors = useChartColors();
  const chartData = data.map((p) => ({
    procedure: p.procedure_code,
    estimate: Math.round(p.avg_estimate_minutes),
    actual: Math.round(p.avg_actual_minutes),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 24 }}>
        <CartesianGrid stroke={colors.grid} vertical={false} />
        <XAxis
          dataKey="procedure"
          stroke={colors.axis}
          tick={{ fill: colors.muted, fontSize: 12 }}
          tickLine={false}
          angle={-40}
          textAnchor="end"
          interval={0}
          height={60}
        />
        <YAxis
          stroke={colors.axis}
          tick={{ fill: colors.muted, fontSize: 12 }}
          tickLine={false}
          width={44}
          unit="m"
        />
        <Tooltip
          contentStyle={tooltipContentStyle}
          labelStyle={tooltipLabelStyle}
          cursor={{ fill: colors.grid, opacity: 0.4 }}
          formatter={(value: number, name: string) => [`${value}m`, name]}
        />
        <Legend wrapperStyle={{ fontSize: 12, color: "var(--viz-secondary)" }} />
        <Bar
          dataKey="estimate"
          fill={colors.series1}
          radius={[4, 4, 0, 0]}
          isAnimationActive={false}
          name="Surgeon estimate"
        />
        <Bar
          dataKey="actual"
          fill={colors.series2}
          radius={[4, 4, 0, 0]}
          isAnimationActive={false}
          name="Actual"
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
