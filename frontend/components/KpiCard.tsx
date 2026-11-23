type Tone = "default" | "good" | "warning" | "critical";

const DOT: Record<Tone, string> = {
  default: "var(--series-1)",
  good: "var(--status-good)",
  warning: "var(--status-warning)",
  critical: "var(--status-critical)",
};

type KpiCardProps = {
  label: string;
  value: string;
  hint?: string;
  tone?: Tone;
};

export function KpiCard({ label, value, hint, tone = "default" }: KpiCardProps) {
  return (
    <div className="rounded-xl border border-black/10 bg-white p-4 dark:border-white/10 dark:bg-[#1a1a19]">
      <div className="flex items-center gap-2">
        <span
          aria-hidden
          className="inline-block h-2 w-2 rounded-full"
          style={{ background: DOT[tone] }}
        />
        <span className="text-xs font-medium uppercase tracking-wide opacity-60">
          {label}
        </span>
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-1 text-xs opacity-60">{hint}</div>}
    </div>
  );
}
