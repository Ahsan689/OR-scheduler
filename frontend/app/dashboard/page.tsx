"use client";

import { useEffect, useState } from "react";

import { CasesPerRoom } from "@/components/charts/CasesPerRoom";
import { EstimateVsActual } from "@/components/charts/EstimateVsActual";
import { UtilizationTrend } from "@/components/charts/UtilizationTrend";
import { KpiCard } from "@/components/KpiCard";
import { Panel } from "@/components/Panel";
import { type DashboardResponse, fetchDashboard } from "@/lib/api";
import { minutes, pct, rate } from "@/lib/format";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: DashboardResponse };

function onTimeTone(value: number): "good" | "warning" | "critical" {
  if (value >= 0.9) return "good";
  if (value >= 0.7) return "warning";
  return "critical";
}

export default function DashboardPage() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetchDashboard(controller.signal)
      .then((data) => setState({ kind: "ready", data }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          kind: "error",
          message: err instanceof Error ? err.message : "Unknown error",
        });
      });
    return () => controller.abort();
  }, []);

  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">OR Utilization</h1>
        <p className="text-sm opacity-60">
          Synthetic data — not a clinical system.
        </p>
      </header>

      {state.kind === "loading" && (
        <p className="text-sm opacity-70">Loading dashboard…</p>
      )}

      {state.kind === "error" && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-600 dark:text-red-400">
          Could not load dashboard: {state.message}
          <div className="mt-1 opacity-70">
            Is the backend running with imported data?
          </div>
        </div>
      )}

      {state.kind === "ready" && state.data.summary.cases_ran === 0 && (
        <p className="text-sm opacity-70">
          No cases in range. Import data first, then refresh.
        </p>
      )}

      {state.kind === "ready" && state.data.summary.cases_ran > 0 && (
        <DashboardView data={state.data} />
      )}
    </main>
  );
}

function DashboardView({ data }: { data: DashboardResponse }) {
  const { summary, rooms, daily, procedures } = data;

  return (
    <div className="flex flex-col gap-6">
      <p className="text-xs opacity-60">
        {summary.date_from} → {summary.date_to} · {summary.cases_ran} cases ·{" "}
        {summary.cases_cancelled} cancelled · {summary.cases_no_show} no-show
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <KpiCard label="Utilization" value={pct(summary.avg_utilization_pct)} />
        <KpiCard
          label="Cases / room / day"
          value={summary.avg_cases_per_room_day.toFixed(1)}
        />
        <KpiCard
          label="On-time starts"
          value={rate(summary.on_time_start_rate)}
          tone={onTimeTone(summary.on_time_start_rate)}
        />
        <KpiCard label="Idle time" value={minutes(summary.total_idle_minutes)} />
        <KpiCard
          label="Overtime"
          value={minutes(summary.total_overtime_minutes)}
          tone={summary.total_overtime_minutes > 0 ? "warning" : "good"}
        />
        <KpiCard
          label="Avg overrun / case"
          value={minutes(summary.avg_overrun_minutes_per_case)}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="Utilization over time" subtitle="Operative time ÷ working window">
          <UtilizationTrend data={daily} />
        </Panel>
        <Panel title="Cases per room" subtitle="Cases that ran in each OR">
          <CasesPerRoom data={rooms} />
        </Panel>
      </div>

      <Panel
        title="Estimate vs actual duration"
        subtitle="Average minutes by procedure"
      >
        <EstimateVsActual data={procedures} />
      </Panel>

      <Panel title="Rooms" subtitle="Breakdown by operating room">
        <RoomsTable rooms={rooms} />
      </Panel>

      <Panel title="Procedures" subtitle="Duration accuracy by procedure">
        <ProceduresTable procedures={procedures} />
      </Panel>
    </div>
  );
}

function RoomsTable({ rooms }: { rooms: DashboardResponse["rooms"] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm tabular-nums">
        <thead className="text-left text-xs uppercase tracking-wide opacity-60">
          <tr>
            <th className="py-2 pr-4">Room</th>
            <th className="py-2 pr-4">Cases</th>
            <th className="py-2 pr-4">Utilization</th>
            <th className="py-2 pr-4">Idle</th>
            <th className="py-2 pr-4">Overtime</th>
            <th className="py-2 pr-4">On-time</th>
          </tr>
        </thead>
        <tbody>
          {rooms.map((r) => (
            <tr key={r.room_code} className="border-t border-black/5 dark:border-white/5">
              <td className="py-2 pr-4 font-medium">{r.room_code}</td>
              <td className="py-2 pr-4">{r.cases_ran}</td>
              <td className="py-2 pr-4">{pct(r.utilization_pct)}</td>
              <td className="py-2 pr-4">{minutes(r.idle_minutes)}</td>
              <td className="py-2 pr-4">{minutes(r.overtime_minutes)}</td>
              <td className="py-2 pr-4">{rate(r.on_time_start_rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProceduresTable({
  procedures,
}: {
  procedures: DashboardResponse["procedures"];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm tabular-nums">
        <thead className="text-left text-xs uppercase tracking-wide opacity-60">
          <tr>
            <th className="py-2 pr-4">Procedure</th>
            <th className="py-2 pr-4">Cases</th>
            <th className="py-2 pr-4">Est (avg)</th>
            <th className="py-2 pr-4">Actual (avg)</th>
            <th className="py-2 pr-4">Overrun</th>
          </tr>
        </thead>
        <tbody>
          {procedures.map((p) => (
            <tr
              key={p.procedure_code}
              className="border-t border-black/5 dark:border-white/5"
            >
              <td className="py-2 pr-4 font-medium">{p.procedure_name}</td>
              <td className="py-2 pr-4">{p.cases}</td>
              <td className="py-2 pr-4">{minutes(p.avg_estimate_minutes)}</td>
              <td className="py-2 pr-4">{minutes(p.avg_actual_minutes)}</td>
              <td className="py-2 pr-4">{minutes(p.avg_overrun_minutes)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
