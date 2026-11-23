"""Tests for the pure OR-Tools day scheduler."""

from collections import defaultdict

import pytest

from app.services.solver import (
    Assignment,
    CaseInput,
    InfeasibleScheduleError,
    SolverConfig,
    solve_day,
)


def _by_room(assignments: list[Assignment]) -> dict[int, list[Assignment]]:
    rooms: dict[int, list[Assignment]] = defaultdict(list)
    for a in assignments:
        rooms[a.room_index].append(a)
    for room in rooms.values():
        room.sort(key=lambda a: a.start_minutes)
    return rooms


def test_empty_input() -> None:
    assert solve_day([], num_rooms=2).assignments == []


def test_all_cases_assigned_exactly_once() -> None:
    cases = [CaseInput(case_id=i, surgeon_id=i % 3, duration_minutes=60) for i in range(6)]
    schedule = solve_day(cases, num_rooms=2)
    assert {a.case_id for a in schedule.assignments} == {c.case_id for c in cases}
    assert len(schedule.assignments) == 6


def test_room_has_turnover_gap_and_no_overlap() -> None:
    cases = [CaseInput(case_id=i, surgeon_id=i, duration_minutes=120) for i in range(3)]
    schedule = solve_day(cases, num_rooms=1, config=SolverConfig(turnover_minutes=15))
    room = _by_room(schedule.assignments)[0]
    for prev, nxt in zip(room, room[1:], strict=False):
        assert nxt.start_minutes >= prev.end_minutes + 15


def test_surgeon_cases_never_overlap() -> None:
    # Same surgeon, two rooms available: must still be sequential in time.
    cases = [
        CaseInput(case_id=1, surgeon_id=7, duration_minutes=120),
        CaseInput(case_id=2, surgeon_id=7, duration_minutes=120),
    ]
    schedule = solve_day(cases, num_rooms=2)
    a, b = sorted(schedule.assignments, key=lambda x: x.start_minutes)
    assert b.start_minutes >= a.end_minutes


def test_parallel_rooms_avoid_overtime() -> None:
    # Two surgeons, three cases each; two rooms let them run in parallel.
    cases = [CaseInput(case_id=i, surgeon_id=i % 2, duration_minutes=120) for i in range(6)]
    schedule = solve_day(cases, num_rooms=2, config=SolverConfig(day_close_minutes=480))
    assert schedule.total_overtime_minutes == 0


def test_deterministic() -> None:
    cases = [
        CaseInput(case_id=i, surgeon_id=i % 3, duration_minutes=50 + 5 * i) for i in range(8)
    ]
    first = solve_day(cases, num_rooms=3)
    second = solve_day(cases, num_rooms=3)
    assert first.assignments == second.assignments


def test_no_rooms_is_infeasible() -> None:
    with pytest.raises(InfeasibleScheduleError):
        solve_day([CaseInput(case_id=1, surgeon_id=1, duration_minutes=60)], num_rooms=0)
