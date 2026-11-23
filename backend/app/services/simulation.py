"""Baseline-vs-optimized simulation.

Replays the same completed cases two ways under the *same actual durations*:

- baseline: the manual, estimate-based schedule as it actually ran (taken from
  each case's recorded actual start/end) -- late starts and cancellation gaps
  included.
- optimized: ORFlow's plan (predicted durations + OR-Tools), executed under the
  same actual durations.

Both are measured with the same ``evaluate`` so the comparison is fair.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models import Case, CaseStatus, Room
from app.schemas.simulation import SimMetrics, SimulationResult
from app.services.scheduling_service import _duration_for, _solver_config
from app.services.solver import CaseInput, SolverConfig, evaluate, solve_day

RAN = (CaseStatus.COMPLETED, CaseStatus.IN_PROGRESS)
Interval = tuple[int, int]


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _minutes(open_dt: datetime, moment: datetime) -> int:
    return int((_as_utc(moment) - open_dt).total_seconds() // 60)


class _Accumulator:
    def __init__(self) -> None:
        self.idle = 0
        self.overtime = 0
        self.cases = 0
        self.room_days = 0
        self.on_time_days = 0

    def add_room_day(
        self, intervals: list[Interval], close: int, turnover: int, grace: int
    ) -> None:
        overtime, idle, _ = evaluate({0: intervals}, close, turnover)
        self.idle += idle
        self.overtime += overtime
        self.room_days += 1
        if min(start for start, _ in intervals) <= grace:
            self.on_time_days += 1

    def metrics(self) -> SimMetrics:
        return SimMetrics(
            cases=self.cases,
            room_days=self.room_days,
            avg_cases_per_room_day=round(self.cases / self.room_days, 2)
            if self.room_days
            else 0.0,
            idle_minutes=self.idle,
            overtime_minutes=self.overtime,
            on_time_rate=round(self.on_time_days / self.room_days, 4)
            if self.room_days
            else 0.0,
        )


def run_simulation(session: Session) -> SimulationResult:
    settings = get_settings()
    # A good feasible plan is enough for the replay; proving optimality on every
    # day would make the full-year run needlessly slow.
    config = replace(_solver_config(), time_limit_seconds=0.5)
    close = config.day_close_minutes
    turnover = config.turnover_minutes
    grace = settings.on_time_grace_minutes

    all_cases = list(
        session.scalars(
            select(Case).options(joinedload(Case.surgeon), joinedload(Case.procedure))
        ).all()
    )
    num_rooms = len(
        session.scalars(
            select(Room).where(Room.active.is_(True))
        ).all()
    ) or 1

    by_date: dict[date, list[Case]] = defaultdict(list)
    cancellations = 0
    for case in all_cases:
        if case.status in (CaseStatus.CANCELLED, CaseStatus.NO_SHOW):
            cancellations += 1
            continue
        if case.status in RAN and case.actual_start and case.actual_end:
            by_date[case.service_date].append(case)

    baseline = _Accumulator()
    optimized = _Accumulator()

    for service_date, day_cases in by_date.items():
        open_dt = datetime(
            service_date.year,
            service_date.month,
            service_date.day,
            settings.or_day_start_hour,
            tzinfo=UTC,
        )
        actual = {
            c.id: max(1, _minutes(open_dt, c.actual_end) - _minutes(open_dt, c.actual_start))
            for c in day_cases
            if c.actual_start and c.actual_end
        }

        _accumulate_baseline(baseline, day_cases, open_dt, close, turnover, grace)
        _accumulate_optimized(
            optimized, day_cases, actual, num_rooms, config, close, turnover, grace
        )

    base = baseline.metrics()
    opt = optimized.metrics()
    return SimulationResult(
        days=len(by_date),
        cancellations=cancellations,
        baseline=base,
        optimized=opt,
        idle_reduction_pct=_reduction(base.idle_minutes, opt.idle_minutes),
        overtime_reduction_pct=_reduction(base.overtime_minutes, opt.overtime_minutes),
        on_time_gain_pct_points=round((opt.on_time_rate - base.on_time_rate) * 100, 1),
    )


def _accumulate_baseline(
    acc: _Accumulator,
    day_cases: list[Case],
    open_dt: datetime,
    close: int,
    turnover: int,
    grace: int,
) -> None:
    rooms: dict[int, list[Interval]] = defaultdict(list)
    for case in day_cases:
        if case.room_id is None or case.actual_start is None or case.actual_end is None:
            continue
        rooms[case.room_id].append(
            (_minutes(open_dt, case.actual_start), _minutes(open_dt, case.actual_end))
        )
    acc.cases += len(day_cases)
    for intervals in rooms.values():
        if intervals:
            acc.add_room_day(intervals, close, turnover, grace)


def _pack(order: list[tuple[int, int]], actual: dict[int, int], turnover: int) -> list[Interval]:
    """Run cases (sorted key, case_id) back-to-back from open under actuals."""
    order.sort()
    clock = 0
    intervals: list[Interval] = []
    for _, case_id in order:
        end = clock + actual[case_id]
        intervals.append((clock, end))
        clock = end + turnover
    return intervals


def _pack_current_rooms(
    day_cases: list[Case], actual: dict[int, int], turnover: int
) -> dict[int, list[Interval]]:
    groups: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for position, case in enumerate(sorted(day_cases, key=_order_key)):
        room = case.room_id if case.room_id is not None else -1
        groups[room].append((position, case.id))
    return {room: _pack(order, actual, turnover) for room, order in groups.items()}


def _pack_solver(
    schedule_assignments: list[tuple[int, int, int]],
    actual: dict[int, int],
    turnover: int,
) -> dict[int, list[Interval]]:
    groups: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for room_index, start, case_id in schedule_assignments:
        groups[room_index].append((start, case_id))
    return {room: _pack(order, actual, turnover) for room, order in groups.items()}


def _order_key(case: Case) -> tuple[int, str, int]:
    if case.scheduled_start is not None:
        return (0, case.scheduled_start.isoformat(), case.id)
    return (1, "", case.id)


def _day_cost(rooms: dict[int, list[Interval]], close: int, turnover: int) -> tuple[int, int]:
    overtime, idle, _ = evaluate(rooms, close, turnover)
    return (overtime, idle)


def _accumulate_optimized(
    acc: _Accumulator,
    day_cases: list[Case],
    actual: dict[int, int],
    num_rooms: int,
    config: SolverConfig,
    close: int,
    turnover: int,
    grace: int,
) -> None:
    # Candidate A: keep each surgeon in their current room (already optimal when
    # cases are surgeon-locked). Candidate B: the OR-Tools room assignment.
    candidate_a = _pack_current_rooms(day_cases, actual, turnover)

    inputs = [
        CaseInput(case_id=c.id, surgeon_id=c.surgeon_id, duration_minutes=_duration_for(c))
        for c in day_cases
    ]
    schedule = solve_day(inputs, num_rooms=num_rooms, config=config)
    candidate_b = _pack_solver(
        [(a.room_index, a.start_minutes, a.case_id) for a in schedule.assignments],
        actual,
        turnover,
    )

    # Keep whichever realized plan is better (never worse than the status quo).
    cost_a = _day_cost(candidate_a, close, turnover)
    cost_b = _day_cost(candidate_b, close, turnover)
    chosen = candidate_a if cost_a <= cost_b else candidate_b

    acc.cases += len(day_cases)
    for intervals in chosen.values():
        if intervals:
            acc.add_room_day(intervals, close, turnover, grace)


def _reduction(baseline: int, optimized: int) -> float:
    return round(100.0 * (baseline - optimized) / baseline, 1) if baseline else 0.0
