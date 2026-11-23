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

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  return { "X-Role": DEMO_ROLE, "X-Actor": DEMO_ACTOR, ...extra };
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // keep the default message
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export async function fetchDashboard(signal?: AbortSignal): Promise<DashboardResponse> {
  return request<DashboardResponse>(`${API_URL}/metrics/dashboard`, {
    signal,
    headers: authHeaders(),
  });
}

// ---- Scheduler / proposals ----

export type ProposalStatus = "pending" | "accepted" | "rejected";

export type ProposalOut = {
  id: number;
  case_id: number;
  patient_ref: string;
  proposed_room_code: string | null;
  proposed_start: string | null;
  proposed_end: string | null;
  status: ProposalStatus;
  rationale: string | null;
};

export type ScheduleMetrics = {
  overtime_minutes: number;
  idle_minutes: number;
  makespan_minutes: number;
};

export type OptimizeResponse = {
  service_date: string;
  num_cases: number;
  num_proposals: number;
  baseline: ScheduleMetrics;
  optimized: ScheduleMetrics;
  proposals: ProposalOut[];
};

export type ProposalPatch = {
  proposed_room_code?: string;
  proposed_start?: string;
  proposed_end?: string;
};

export async function optimizeSchedule(date: string): Promise<OptimizeResponse> {
  return request<OptimizeResponse>(
    `${API_URL}/schedule/optimize?date=${encodeURIComponent(date)}`,
    { method: "POST", headers: authHeaders() },
  );
}

export async function acceptProposal(id: number): Promise<ProposalOut> {
  return request<ProposalOut>(`${API_URL}/proposals/${id}/accept`, {
    method: "POST",
    headers: authHeaders(),
  });
}

export async function rejectProposal(id: number): Promise<ProposalOut> {
  return request<ProposalOut>(`${API_URL}/proposals/${id}/reject`, {
    method: "POST",
    headers: authHeaders(),
  });
}

export async function editProposal(id: number, patch: ProposalPatch): Promise<ProposalOut> {
  return request<ProposalOut>(`${API_URL}/proposals/${id}`, {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(patch),
  });
}
