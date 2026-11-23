"""Schemas for the utilization dashboard."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    """Headline KPIs across the selected window."""

    date_from: date
    date_to: date
    room_days: int
    cases_ran: int
    cases_cancelled: int
    cases_no_show: int
    avg_cases_per_room_day: float
    avg_utilization_pct: float
    total_idle_minutes: int
    total_overtime_minutes: int
    on_time_start_rate: float
    avg_overrun_minutes_per_case: float


class RoomUtilization(BaseModel):
    """Per-room aggregates over the window."""

    room_code: str
    cases_ran: int
    utilization_pct: float
    idle_minutes: int
    overtime_minutes: int
    on_time_start_rate: float


class DailyPoint(BaseModel):
    """One day of aggregated activity, for trend charts."""

    day: date
    cases_ran: int
    utilization_pct: float
    idle_minutes: int
    overtime_minutes: int


class ProcedureAccuracy(BaseModel):
    """Estimate-vs-actual duration by procedure."""

    procedure_code: str
    procedure_name: str
    cases: int
    avg_estimate_minutes: float
    avg_actual_minutes: float
    avg_overrun_minutes: float


class DashboardResponse(BaseModel):
    summary: DashboardSummary
    rooms: list[RoomUtilization]
    daily: list[DailyPoint]
    procedures: list[ProcedureAccuracy]
