"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { GanttTimeline } from "@/components/GanttTimeline";
import { Panel } from "@/components/Panel";
import {
  acceptProposal,
  editProposal,
  type OptimizeResponse,
  optimizeSchedule,
  type ProposalOut,
  rejectProposal,
} from "@/lib/api";
import { minutes } from "@/lib/format";

type View =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; resp: OptimizeResponse };

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function timeUTC(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

function durationMinutes(p: ProposalOut): number {
  if (!p.proposed_start || !p.proposed_end) return 60;
  return (new Date(p.proposed_end).getTime() - new Date(p.proposed_start).getTime()) / 60000;
}

export default function SchedulePage() {
  const [date, setDate] = useState("2025-06-16");
  const [view, setView] = useState<View>({ kind: "idle" });
  const [proposals, setProposals] = useState<ProposalOut[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editRoom, setEditRoom] = useState("");
  const [editStart, setEditStart] = useState("");

  const roomOptions = Array.from(
    new Set(proposals.map((p) => p.proposed_room_code).filter((c): c is string => !!c)),
  ).sort();

  // Optional deep-link: /schedule?date=YYYY-MM-DD&auto=1 runs the optimizer on load.
  const didAuto = useRef(false);
  useEffect(() => {
    if (didAuto.current) return;
    didAuto.current = true;
    const params = new URLSearchParams(window.location.search);
    const urlDate = params.get("date");
    if (urlDate) setDate(urlDate);
    if (params.get("auto") === "1") {
      void runOptimizeFor(urlDate ?? date);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runOptimizeFor(forDate: string) {
    setView({ kind: "loading" });
    setActionError(null);
    try {
      const resp = await optimizeSchedule(forDate);
      setProposals(resp.proposals);
      setView({ kind: "ready", resp });
    } catch (err) {
      setView({ kind: "error", message: err instanceof Error ? err.message : "Unknown error" });
    }
  }

  async function runOptimize() {
    await runOptimizeFor(date);
  }

  function applyUpdate(updated: ProposalOut) {
    setProposals((ps) => ps.map((p) => (p.id === updated.id ? updated : p)));
  }

  async function act(action: (id: number) => Promise<ProposalOut>, id: number) {
    setActionError(null);
    try {
      applyUpdate(await action(id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed");
    }
  }

  function startEdit(p: ProposalOut) {
    setEditingId(p.id);
    setEditRoom(p.proposed_room_code ?? "");
    setEditStart(timeUTC(p.proposed_start));
  }

  async function saveEdit(p: ProposalOut) {
    setActionError(null);
    try {
      const startISO = new Date(`${date}T${editStart}:00Z`).toISOString();
      const endISO = new Date(
        new Date(startISO).getTime() + durationMinutes(p) * 60000,
      ).toISOString();
      const updated = await editProposal(p.id, {
        proposed_room_code: editRoom,
        proposed_start: startISO,
        proposed_end: endISO,
      });
      applyUpdate(updated);
      setEditingId(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Edit failed");
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Schedule optimizer</h1>
          <p className="text-sm opacity-60">
            The system proposes; you approve. Synthetic data —{" "}
            <Link href="/dashboard" className="underline">
              dashboard
            </Link>
            .
          </p>
        </div>
        <div className="flex items-end gap-2">
          <label className="flex flex-col text-xs opacity-70">
            Date
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="mt-1 rounded-md border border-black/15 bg-transparent px-2 py-1.5 text-sm dark:border-white/20"
            />
          </label>
          <button
            onClick={runOptimize}
            disabled={view.kind === "loading"}
            className="rounded-md bg-[var(--series-1)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {view.kind === "loading" ? "Optimizing…" : "Optimize day"}
          </button>
        </div>
      </header>

      {view.kind === "error" && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-600 dark:text-red-400">
          {view.message}
        </div>
      )}

      {view.kind === "ready" && (
        <div className="flex flex-col gap-6">
          <ComparisonRow resp={view.resp} />

          <Panel
            title="Proposed schedule"
            subtitle={`${view.resp.num_proposals} proposals for ${view.resp.service_date}`}
          >
            <div className="overflow-x-auto">
              <GanttTimeline proposals={proposals} />
            </div>
          </Panel>

          {actionError && (
            <p className="text-sm text-red-600 dark:text-red-400">{actionError}</p>
          )}

          <Panel title="Proposals" subtitle="Accept, edit, or reject each proposal">
            <ProposalsTable
              proposals={proposals}
              roomOptions={roomOptions}
              editingId={editingId}
              editRoom={editRoom}
              editStart={editStart}
              setEditRoom={setEditRoom}
              setEditStart={setEditStart}
              onStartEdit={startEdit}
              onCancelEdit={() => setEditingId(null)}
              onSaveEdit={saveEdit}
              onAccept={(id) => act(acceptProposal, id)}
              onReject={(id) => act(rejectProposal, id)}
            />
          </Panel>
        </div>
      )}

      {view.kind === "idle" && (
        <p className="text-sm opacity-70">
          Pick a date and run the optimizer to see proposed room/time assignments.
        </p>
      )}
    </main>
  );
}

function ComparisonRow({ resp }: { resp: OptimizeResponse }) {
  const items = [
    {
      label: "Overtime",
      base: resp.baseline.overtime_minutes,
      opt: resp.optimized.overtime_minutes,
    },
    { label: "Idle", base: resp.baseline.idle_minutes, opt: resp.optimized.idle_minutes },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {items.map((it) => {
        const delta = it.base - it.opt;
        return (
          <div
            key={it.label}
            className="rounded-xl border border-black/10 bg-white p-4 dark:border-white/10 dark:bg-[#1a1a19]"
          >
            <div className="text-xs font-medium uppercase tracking-wide opacity-60">
              {it.label}
            </div>
            <div className="mt-1 text-sm">
              <span className="opacity-60 line-through">{minutes(it.base)}</span>{" "}
              <span className="text-lg font-semibold">{minutes(it.opt)}</span>
            </div>
            <div
              className="mt-0.5 text-xs"
              style={{
                color:
                  delta > 0
                    ? "var(--status-good)"
                    : delta < 0
                      ? "var(--status-warning)"
                      : "var(--viz-muted)",
              }}
            >
              {delta > 0
                ? `−${minutes(delta)}`
                : delta < 0
                  ? `+${minutes(-delta)}`
                  : "no change"}
            </div>
          </div>
        );
      })}
    </div>
  );
}

type TableProps = {
  proposals: ProposalOut[];
  roomOptions: string[];
  editingId: number | null;
  editRoom: string;
  editStart: string;
  setEditRoom: (v: string) => void;
  setEditStart: (v: string) => void;
  onStartEdit: (p: ProposalOut) => void;
  onCancelEdit: () => void;
  onSaveEdit: (p: ProposalOut) => void;
  onAccept: (id: number) => void;
  onReject: (id: number) => void;
};

function ProposalsTable(props: TableProps) {
  const { proposals, roomOptions, editingId } = props;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm tabular-nums">
        <thead className="text-left text-xs uppercase tracking-wide opacity-60">
          <tr>
            <th className="py-2 pr-4">Patient</th>
            <th className="py-2 pr-4">Room</th>
            <th className="py-2 pr-4">Start</th>
            <th className="py-2 pr-4">Status</th>
            <th className="py-2 pr-4">Actions</th>
          </tr>
        </thead>
        <tbody>
          {proposals.map((p) => {
            const editing = editingId === p.id;
            return (
              <tr key={p.id} className="border-t border-black/5 dark:border-white/5">
                <td className="py-2 pr-4 font-medium">{p.patient_ref}</td>
                <td className="py-2 pr-4">
                  {editing ? (
                    <select
                      value={props.editRoom}
                      onChange={(e) => props.setEditRoom(e.target.value)}
                      className="rounded border border-black/15 bg-transparent px-1 py-0.5 dark:border-white/20"
                    >
                      {roomOptions.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                  ) : (
                    p.proposed_room_code
                  )}
                </td>
                <td className="py-2 pr-4">
                  {editing ? (
                    <input
                      type="time"
                      value={props.editStart}
                      onChange={(e) => props.setEditStart(e.target.value)}
                      className="rounded border border-black/15 bg-transparent px-1 py-0.5 dark:border-white/20"
                    />
                  ) : (
                    timeUTC(p.proposed_start)
                  )}
                </td>
                <td className="py-2 pr-4">
                  <StatusBadge status={p.status} />
                </td>
                <td className="py-2 pr-4">
                  <Actions {...props} proposal={p} editing={editing} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Actions(props: TableProps & { proposal: ProposalOut; editing: boolean }) {
  const { proposal: p, editing } = props;
  if (editing) {
    return (
      <div className="flex gap-2">
        <button onClick={() => props.onSaveEdit(p)} className="text-xs underline">
          Save
        </button>
        <button onClick={props.onCancelEdit} className="text-xs underline opacity-60">
          Cancel
        </button>
      </div>
    );
  }
  if (p.status !== "pending") {
    return <span className="text-xs opacity-40">—</span>;
  }
  return (
    <div className="flex gap-2">
      <button
        onClick={() => props.onAccept(p.id)}
        className="text-xs font-medium"
        style={{ color: "var(--status-good)" }}
      >
        Accept
      </button>
      <button onClick={() => props.onStartEdit(p)} className="text-xs underline">
        Edit
      </button>
      <button
        onClick={() => props.onReject(p.id)}
        className="text-xs"
        style={{ color: "var(--status-critical)" }}
      >
        Reject
      </button>
    </div>
  );
}

function StatusBadge({ status }: { status: ProposalOut["status"] }) {
  const color =
    status === "accepted"
      ? "var(--status-good)"
      : status === "rejected"
        ? "var(--status-critical)"
        : "var(--series-1)";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
      {status}
    </span>
  );
}
