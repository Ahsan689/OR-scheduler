"""Operating-room day scheduler (OR-Tools CP-SAT).

Pure and DB-free so the simulation can reuse it. Given a day's cases (each with
a fixed surgeon and a duration), it assigns every case to a room and a start
time subject to the hard constraints, minimising a weighted sum of soft costs.

Hard constraints:
- one case per room at a time, with a turnover gap between consecutive cases
- a surgeon's cases never overlap (a surgeon is one person)

Soft objective (configurable weights):
- overtime beyond the OR close time
- total finish time (packs cases early, shrinking idle gaps)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from ortools.sat.python import cp_model


@dataclass(frozen=True)
class CaseInput:
    case_id: int
    surgeon_id: int
    duration_minutes: int


@dataclass(frozen=True)
class SolverConfig:
    turnover_minutes: int = 25
    day_open_minutes: int = 0
    day_close_minutes: int = 480  # 8h working window
    max_overtime_minutes: int = 300
    weight_overtime: int = 10
    weight_finish: int = 1
    random_seed: int = 42
    time_limit_seconds: float = 10.0


@dataclass(frozen=True)
class Assignment:
    case_id: int
    room_index: int
    start_minutes: int
    end_minutes: int


@dataclass
class DaySchedule:
    assignments: list[Assignment] = field(default_factory=list)
    total_overtime_minutes: int = 0
    total_idle_minutes: int = 0
    makespan_minutes: int = 0


class InfeasibleScheduleError(Exception):
    """Raised when no feasible schedule exists for the given input."""


def solve_day(
    cases: list[CaseInput], num_rooms: int, config: SolverConfig | None = None
) -> DaySchedule:
    config = config or SolverConfig()
    if num_rooms < 1:
        raise InfeasibleScheduleError("at least one room is required")
    if not cases:
        return DaySchedule()

    # The horizon must be large enough to always admit a feasible placement
    # (worst case: every case sequential in one room). Overtime past close is
    # then penalised, not forbidden.
    required = sum(c.duration_minutes + config.turnover_minutes for c in cases)
    horizon = max(config.day_close_minutes + config.max_overtime_minutes, required)

    model = cp_model.CpModel()
    starts: dict[int, cp_model.IntVar] = {}
    ends: dict[int, cp_model.IntVar] = {}
    real_intervals: dict[int, cp_model.IntervalVar] = {}
    presence: dict[tuple[int, int], cp_model.IntVar] = {}
    room_intervals: dict[int, list[cp_model.IntervalVar]] = defaultdict(list)

    for i, case in enumerate(cases):
        start = model.new_int_var(0, horizon - case.duration_minutes, f"start_{i}")
        end = model.new_int_var(0, horizon, f"end_{i}")
        model.add(end == start + case.duration_minutes)
        starts[i] = start
        ends[i] = end
        real_intervals[i] = model.new_interval_var(
            start, case.duration_minutes, end, f"iv_{i}"
        )

        room_lits: list[cp_model.IntVar] = []
        for r in range(num_rooms):
            present = model.new_bool_var(f"present_{i}_{r}")
            presence[(i, r)] = present
            # Reserve turnover after the case so consecutive cases keep a gap.
            room_intervals[r].append(
                model.new_optional_interval_var(
                    start,
                    case.duration_minutes + config.turnover_minutes,
                    start + case.duration_minutes + config.turnover_minutes,
                    present,
                    f"oiv_{i}_{r}",
                )
            )
            room_lits.append(present)
        model.add_exactly_one(room_lits)

    for r in range(num_rooms):
        model.add_no_overlap(room_intervals[r])

    by_surgeon: dict[int, list[int]] = defaultdict(list)
    for i, case in enumerate(cases):
        by_surgeon[case.surgeon_id].append(i)
    for indices in by_surgeon.values():
        if len(indices) > 1:
            model.add_no_overlap([real_intervals[i] for i in indices])

    overtimes: list[cp_model.IntVar] = []
    for i in range(len(cases)):
        ot_var = model.new_int_var(0, horizon, f"ot_{i}")
        model.add(ot_var >= ends[i] - config.day_close_minutes)
        overtimes.append(ot_var)

    # Consolidation nudge: prefer lower-indexed rooms so a surgeon's cases are
    # not split across rooms when that brings no benefit (avoids phantom idle).
    room_pref = sum(
        r * presence[(i, r)] for i in range(len(cases)) for r in range(num_rooms)
    )

    model.minimize(
        config.weight_overtime * sum(overtimes)
        + config.weight_finish * sum(ends[i] for i in range(len(cases)))
        + room_pref
    )

    solver = cp_model.CpSolver()
    solver.parameters.random_seed = config.random_seed
    solver.parameters.num_workers = 1  # deterministic
    solver.parameters.max_time_in_seconds = config.time_limit_seconds
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise InfeasibleScheduleError(
            f"no feasible schedule (solver status: {solver.status_name(status)})"
        )

    assignments: list[Assignment] = []
    for i, case in enumerate(cases):
        room_index = next(
            r for r in range(num_rooms) if solver.value(presence[(i, r)]) == 1
        )
        start_value = solver.value(starts[i])
        assignments.append(
            Assignment(
                case_id=case.case_id,
                room_index=room_index,
                start_minutes=start_value,
                end_minutes=start_value + case.duration_minutes,
            )
        )

    rooms: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for a in assignments:
        rooms[a.room_index].append((a.start_minutes, a.end_minutes))
    overtime, idle, makespan = evaluate(
        rooms, close_minutes=config.day_close_minutes, turnover_minutes=config.turnover_minutes
    )
    return DaySchedule(
        assignments=assignments,
        total_overtime_minutes=overtime,
        total_idle_minutes=idle,
        makespan_minutes=makespan,
    )


def evaluate(
    rooms: dict[int, list[tuple[int, int]]], close_minutes: int, turnover_minutes: int
) -> tuple[int, int, int]:
    """Overtime, idle and makespan for a set of room timelines.

    Shared by the solver and the baseline so both are measured the same way.
    Idle counts the time a room sits empty beyond the turnover it needs between
    cases (plus any gap before its first case); overtime is time past close.
    """
    overtime = 0
    idle = 0
    makespan = 0
    for intervals in rooms.values():
        if not intervals:
            continue
        ordered = sorted(intervals)
        operative = sum(end - start for start, end in ordered)
        first_start = ordered[0][0]
        last_end = ordered[-1][1]
        span = last_end - first_start
        needed_turnover = turnover_minutes * (len(ordered) - 1)
        idle += max(0, first_start) + max(0, span - operative - needed_turnover)
        overtime += max(0, last_end - close_minutes)
        makespan = max(makespan, last_end)
    return overtime, idle, makespan
