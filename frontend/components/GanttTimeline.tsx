"use client";

import type { ProposalOut, ProposalStatus } from "@/lib/api";

function minuteOfDayUTC(iso: string): number {
  const d = new Date(iso);
  return d.getUTCHours() * 60 + d.getUTCMinutes();
}

function fmt(totalMinutes: number): string {
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return `${h}:${String(m).padStart(2, "0")}`;
}

function colorFor(status: ProposalStatus): string {
  if (status === "accepted") return "var(--status-good)";
  if (status === "rejected") return "var(--viz-muted)";
  return "var(--series-1)";
}

type Placed = { proposal: ProposalOut; start: number; end: number; room: string };

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
      {label}
    </span>
  );
}

export function GanttTimeline({ proposals }: { proposals: ProposalOut[] }) {
  const placed: Placed[] = proposals
    .filter((p) => p.proposed_start && p.proposed_end && p.proposed_room_code)
    .map((p) => ({
      proposal: p,
      start: minuteOfDayUTC(p.proposed_start as string),
      end: minuteOfDayUTC(p.proposed_end as string),
      room: p.proposed_room_code as string,
    }));

  if (placed.length === 0) {
    return <p className="text-sm opacity-60">Nothing scheduled yet.</p>;
  }

  const min = Math.floor(Math.min(...placed.map((p) => p.start)) / 60) * 60;
  const max = Math.ceil(Math.max(...placed.map((p) => p.end)) / 60) * 60;
  const span = Math.max(60, max - min);
  const pct = (t: number) => ((t - min) / span) * 100;

  const rooms = Array.from(new Set(placed.map((p) => p.room))).sort();
  const hours: number[] = [];
  for (let t = min; t <= max; t += 60) hours.push(t);

  return (
    <div className="min-w-[560px]">
      <div className="relative ml-16 h-5 text-[10px] opacity-60">
        {hours.map((h) => (
          <span key={h} className="absolute -translate-x-1/2" style={{ left: `${pct(h)}%` }}>
            {fmt(h)}
          </span>
        ))}
      </div>

      <div className="flex flex-col gap-1">
        {rooms.map((room) => (
          <div key={room} className="flex items-center gap-2">
            <div className="w-14 shrink-0 text-xs font-medium">{room}</div>
            <div className="relative h-8 flex-1 rounded bg-black/[0.03] dark:bg-white/5">
              {hours.map((h) => (
                <div
                  key={h}
                  className="absolute bottom-0 top-0 w-px bg-black/5 dark:bg-white/10"
                  style={{ left: `${pct(h)}%` }}
                />
              ))}
              {placed
                .filter((p) => p.room === room)
                .map(({ proposal, start, end }) => (
                  <div
                    key={proposal.id}
                    title={`${proposal.patient_ref} · ${fmt(start)}–${fmt(end)} · ${proposal.status}`}
                    className="absolute bottom-1 top-1 overflow-hidden rounded px-1 text-[10px] leading-6 text-white"
                    style={{
                      left: `${pct(start)}%`,
                      width: `${Math.max(0.6, pct(end) - pct(start))}%`,
                      background: colorFor(proposal.status),
                    }}
                  >
                    {proposal.patient_ref}
                  </div>
                ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 flex gap-4 text-[11px] opacity-70">
        <LegendDot color="var(--series-1)" label="Pending" />
        <LegendDot color="var(--status-good)" label="Accepted" />
        <LegendDot color="var(--viz-muted)" label="Rejected" />
      </div>
    </div>
  );
}
