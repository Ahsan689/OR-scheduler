"""Disruption handling: emergency insertion.

In the manual world an on-call emergency gets added to the block surgeon's room
-- which is often already full -- so overtime spikes there. An on-call case can
in fact run in any available room, so the optimizer places it where there is
slack. Electives stay pinned to their current (block) room in both plans, so the
only thing that changes is where the emergency lands -- a clean, attributable
win for the scheduler.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Case, CaseStatus, Room
from app.services.scheduling_service import _solver_config
from app.services.solver import CaseInput, SolverConfig, evaluate, solve_day

RAN = (CaseStatus.COMPLETED, CaseStatus.IN_PROGRESS)
# Emergencies run under an on-call surgeon, modeled as unconstrained by giving
# each a unique surgeon id so it can be placed in any room.
ON_CALL_BASE = 10_000_000
Interval = tuple[int, int]


@dataclass
class EmergencyResult:
    days: int
    emergencies: int
    baseline_overtime_minutes: int
    optimized_overtime_minutes: int
    overtime_reduction_pct: float


def _duration(case: Case) -> int:
    assert case.actual_start is not None and case.actual_end is not None
    return max(1, int((case.actual_end - case.actual_start).total_seconds() // 60))


def simulate_emergency_handling(session: Session) -> EmergencyResult:
    config = replace(_solver_config(), time_limit_seconds=0.5)
    close = config.day_close_minutes
    turnover = config.turnover_minutes

    rooms = list(
        session.scalars(
            select(Room).where(Room.active.is_(True)).order_by(Room.code)
        ).all()
    )
    room_index = {room.id: i for i, room in enumerate(rooms)}
    num_rooms = len(rooms) or 1

    cases = list(
        session.scalars(
            select(Case).options(joinedload(Case.procedure)).where(
                Case.status.in_(RAN)
            )
        ).all()
    )
    by_date: dict[date, list[Case]] = defaultdict(list)
    for case in cases:
        if case.actual_start and case.actual_end:
            by_date[case.service_date].append(case)

    days = 0
    emergency_count = 0
    baseline_overtime = 0
    optimized_overtime = 0

    for day_cases in by_date.values():
        emergencies = [c for c in day_cases if c.scheduled_start is None]
        electives = [
            c for c in day_cases if c.scheduled_start is not None and c.room_id is not None
        ]
        if not emergencies or not electives:
            continue
        days += 1
        emergency_count += len(emergencies)

        baseline_overtime += _baseline_overtime(
            electives, emergencies, room_index, close, turnover
        )
        optimized_overtime += _optimized_overtime(
            electives, emergencies, room_index, num_rooms, config
        )

    reduction = (
        round(100.0 * (baseline_overtime - optimized_overtime) / baseline_overtime, 1)
        if baseline_overtime
        else 0.0
    )
    return EmergencyResult(
        days=days,
        emergencies=emergency_count,
        baseline_overtime_minutes=baseline_overtime,
        optimized_overtime_minutes=optimized_overtime,
        overtime_reduction_pct=reduction,
    )


def _baseline_overtime(
    electives: list[Case],
    emergencies: list[Case],
    room_index: dict[int, int],
    close: int,
    turnover: int,
) -> int:
    """Electives packed in their room; each emergency appended to its own room."""
    by_room: dict[int, list[Case]] = defaultdict(list)
    for case in [*electives, *emergencies]:
        idx = room_index.get(case.room_id, 0) if case.room_id is not None else 0
        by_room[idx].append(case)

    rooms: dict[int, list[Interval]] = {}
    for idx, room_cases in by_room.items():
        # electives first (in scheduled order), then emergencies appended
        ordered = sorted(
            room_cases,
            key=lambda c: (c.scheduled_start is None, c.scheduled_start.isoformat()
                           if c.scheduled_start else "", c.id),
        )
        clock = 0
        intervals: list[Interval] = []
        for case in ordered:
            intervals.append((clock, clock + _duration(case)))
            clock += _duration(case) + turnover
        rooms[idx] = intervals

    overtime, _, _ = evaluate(rooms, close, turnover)
    return overtime


def _optimized_overtime(
    electives: list[Case],
    emergencies: list[Case],
    room_index: dict[int, int],
    num_rooms: int,
    config: SolverConfig,
) -> int:
    inputs = [
        CaseInput(
            case_id=c.id,
            surgeon_id=c.surgeon_id,
            duration_minutes=_duration(c),
            fixed_room_index=room_index.get(c.room_id, 0) if c.room_id is not None else 0,
        )
        for c in electives
    ]
    inputs += [
        CaseInput(
            case_id=c.id,
            surgeon_id=ON_CALL_BASE + c.id,
            duration_minutes=_duration(c),
            fixed_room_index=None,
        )
        for c in emergencies
    ]
    schedule = solve_day(inputs, num_rooms=num_rooms, config=config)
    return schedule.total_overtime_minutes
