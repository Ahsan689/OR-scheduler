const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Placeholder identity until real auth exists (see backend core/security.py).
const DEMO_ROLE = "coordinator";
const DEMO_ACTOR = "demo";

export type DashboardSummary = {
  date_from: string;
  date_to: string;
  room_days: number;
  cases_ran: number;
  cases_cancelled: number;
  cases_no_show: number;
  avg_cases_per_room_day: number;
  avg_utilization_pct: number;
  total_idle_minutes: number;
  total_overtime_minutes: number;
  on_time_start_rate: number;
  avg_overrun_minutes_per_case: number;
};

export type RoomUtilization = {
  room_code: string;
  cases_ran: number;
  utilization_pct: number;
  idle_minutes: number;
  overtime_minutes: number;
  on_time_start_rate: number;
};

export type DailyPoint = {
  day: string;
  cases_ran: number;
  utilization_pct: number;
  idle_minutes: number;
  overtime_minutes: number;
};

export type ProcedureAccuracy = {
  procedure_code: string;
  procedure_name: string;
  cases: number;
  avg_estimate_minutes: number;
  avg_actual_minutes: number;
  avg_overrun_minutes: number;
};

export type DashboardResponse = {
  summary: DashboardSummary;
  rooms: RoomUtilization[];
  daily: DailyPoint[];
  procedures: ProcedureAccuracy[];
};

export async function fetchDashboard(signal?: AbortSignal): Promise<DashboardResponse> {
  const res = await fetch(`${API_URL}/metrics/dashboard`, {
    cache: "no-store",
    signal,
    headers: { "X-Role": DEMO_ROLE, "X-Actor": DEMO_ACTOR },
  });
  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`);
  }
  return (await res.json()) as DashboardResponse;
}
