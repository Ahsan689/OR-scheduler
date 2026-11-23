"""Utilization metrics for the dashboard.

Definitions (per room per service date, over cases that actually ran):
- operative minutes  = sum of actual case durations
- idle minutes       = span(first start .. last end) - operative minutes
                       (the between-case gaps: turnover plus true idle)
- overtime minutes   = minutes the last case ran past the OR close time
- on-time start      = first case started within the grace period of open
- overrun minutes    = actual duration beyond the surgeon's estimate (>= 0)
- utilization %      = operative minutes / working-window minutes
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models import Case
from app.models.enums import CaseStatus
from app.schemas.metrics import (
    DailyPoint,
    DashboardResponse,
    DashboardSummary,
    ProcedureAccuracy,
    RoomUtilization,
)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@dataclass
class _RoomDay:
    operative: float = 0.0
    overrun: float = 0.0
    estimate_cases: int = 0
    cases: int = 0
    first_start: datetime | None = None
    last_end: datetime | None = None

    def add(self, start: datetime, end: datetime, duration: float) -> None:
        self.cases += 1
        self.operative += duration
        if self.first_start is None or start < self.first_start:
            self.first_start = start
        if self.last_end is None or end > self.last_end:
            self.last_end = end


@dataclass
class _ProcAcc:
    name: str
    cases: int = 0
    estimate_sum: float = 0.0
    estimate_cases: int = 0
    actual_sum: float = 0.0
    overrun_sum: float = 0.0


@dataclass
class _Agg:
    cases: int = 0
    operative: float = 0.0
    idle: float = 0.0
    overtime: float = 0.0
    on_time_days: int = 0
    room_days: int = 0


def compute_dashboard(
    session: Session,
    date_from: date | None = None,
    date_to: date | None = None,
) -> DashboardResponse:
    settings = get_settings()
    window_minutes = (settings.or_day_end_hour - settings.or_day_start_hour) * 60
    grace = timedelta(minutes=settings.on_time_grace_minutes)

    stmt = select(Case).options(
        joinedload(Case.room), joinedload(Case.procedure)
    )
    if date_from is not None:
        stmt = stmt.where(Case.service_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Case.service_date <= date_to)
    cases = list(session.scalars(stmt).all())

    cancelled = sum(1 for c in cases if c.status is CaseStatus.CANCELLED)
    no_show = sum(1 for c in cases if c.status is CaseStatus.NO_SHOW)

    room_days: dict[tuple[str, date], _RoomDay] = defaultdict(_RoomDay)
    procedures: dict[str, _ProcAcc] = {}
    all_dates: list[date] = [c.service_date for c in cases]

    for case in cases:
        if case.actual_start is None or case.actual_end is None or case.room is None:
            continue
        start = _as_utc(case.actual_start)
        end = _as_utc(case.actual_end)
        duration = (end - start).total_seconds() / 60.0
        if duration <= 0:
            continue

        rd = room_days[(case.room.code, case.service_date)]
        rd.add(start, end, duration)
        if case.surgeon_estimate_minutes is not None:
            rd.estimate_cases += 1
            rd.overrun += max(0.0, duration - case.surgeon_estimate_minutes)

        proc = procedures.setdefault(
            case.procedure.code, _ProcAcc(name=case.procedure.name)
        )
        proc.cases += 1
        proc.actual_sum += duration
        if case.surgeon_estimate_minutes is not None:
            proc.estimate_cases += 1
            proc.estimate_sum += case.surgeon_estimate_minutes
            proc.overrun_sum += duration - case.surgeon_estimate_minutes

    per_room: dict[str, _Agg] = defaultdict(_Agg)
    per_day: dict[date, _Agg] = defaultdict(_Agg)
    total = _Agg()
    total_overrun = 0.0
    total_estimate_cases = 0

    for (room_code, day), rd in room_days.items():
        assert rd.first_start is not None and rd.last_end is not None
        open_dt = datetime(day.year, day.month, day.day, settings.or_day_start_hour, tzinfo=UTC)
        close_dt = datetime(day.year, day.month, day.day, settings.or_day_end_hour, tzinfo=UTC)
        span = (rd.last_end - rd.first_start).total_seconds() / 60.0
        idle = max(0.0, span - rd.operative)
        overtime = max(0.0, (rd.last_end - close_dt).total_seconds() / 60.0)
        on_time = rd.first_start <= open_dt + grace

        for agg in (per_room[room_code], per_day[day], total):
            agg.cases += rd.cases
            agg.operative += rd.operative
            agg.idle += idle
            agg.overtime += overtime
            agg.on_time_days += 1 if on_time else 0
            agg.room_days += 1
        total_overrun += rd.overrun
        total_estimate_cases += rd.estimate_cases

    resolved_from = date_from or (min(all_dates) if all_dates else date.today())
    resolved_to = date_to or (max(all_dates) if all_dates else date.today())

    summary = DashboardSummary(
        date_from=resolved_from,
        date_to=resolved_to,
        room_days=total.room_days,
        cases_ran=total.cases,
        cases_cancelled=cancelled,
        cases_no_show=no_show,
        avg_cases_per_room_day=_safe_div(total.cases, total.room_days),
        avg_utilization_pct=_pct(total.operative, total.room_days * window_minutes),
        total_idle_minutes=round(total.idle),
        total_overtime_minutes=round(total.overtime),
        on_time_start_rate=_safe_div(total.on_time_days, total.room_days),
        avg_overrun_minutes_per_case=_safe_div(total_overrun, total_estimate_cases),
    )

    rooms = [
        RoomUtilization(
            room_code=code,
            cases_ran=agg.cases,
            utilization_pct=_pct(agg.operative, agg.room_days * window_minutes),
            idle_minutes=round(agg.idle),
            overtime_minutes=round(agg.overtime),
            on_time_start_rate=_safe_div(agg.on_time_days, agg.room_days),
        )
        for code, agg in sorted(per_room.items())
    ]

    daily = [
        DailyPoint(
            day=day,
            cases_ran=agg.cases,
            utilization_pct=_pct(agg.operative, agg.room_days * window_minutes),
            idle_minutes=round(agg.idle),
            overtime_minutes=round(agg.overtime),
        )
        for day, agg in sorted(per_day.items())
    ]

    procedure_rows = [
        ProcedureAccuracy(
            procedure_code=code,
            procedure_name=acc.name,
            cases=acc.cases,
            avg_estimate_minutes=_safe_div(acc.estimate_sum, acc.estimate_cases),
            avg_actual_minutes=_safe_div(acc.actual_sum, acc.cases),
            avg_overrun_minutes=_safe_div(acc.overrun_sum, acc.estimate_cases),
        )
        for code, acc in sorted(procedures.items())
    ]

    return DashboardResponse(
        summary=summary, rooms=rooms, daily=daily, procedures=procedure_rows
    )


def _safe_div(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 2) if denominator else 0.0


def _pct(numerator: float, denominator: float) -> float:
    return round(100.0 * numerator / denominator, 2) if denominator else 0.0
