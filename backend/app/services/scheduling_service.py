"""Scheduling orchestration: run the solver, store proposals, apply on accept.

The optimizer only ever *proposes*. A proposal changes a case's room/time only
after a human accepts it, and every accept/reject/edit writes an audit event.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models import (
    AuditEvent,
    AuditSource,
    Case,
    CaseStatus,
    Proposal,
    ProposalStatus,
    Room,
)
from app.schemas.schedule import (
    OptimizeResponse,
    ProposalOut,
    ProposalPatch,
    ScheduleMetrics,
)
from app.services.solver import (
    Assignment,
    CaseInput,
    DaySchedule,
    InfeasibleScheduleError,
    SolverConfig,
    evaluate,
    solve_day,
)

SCHEDULABLE = (CaseStatus.SCHEDULED, CaseStatus.IN_PROGRESS, CaseStatus.COMPLETED)


class ScheduleError(Exception):
    """A scheduling request the caller should fix (mapped to HTTP 400)."""


class ProposalNotFoundError(ScheduleError):
    """The requested proposal does not exist (mapped to HTTP 404)."""


def _duration_for(case: Case) -> int:
    """Best available duration estimate, preferring the model prediction."""
    if case.predicted_duration_minutes is not None:
        return max(1, case.predicted_duration_minutes)
    if case.surgeon_estimate_minutes is not None:
        return max(1, case.surgeon_estimate_minutes)
    return max(1, case.procedure.baseline_duration_minutes)


def _open_dt(service_date: date, start_hour: int) -> datetime:
    return datetime(
        service_date.year, service_date.month, service_date.day, start_hour, tzinfo=UTC
    )


def _schedule_sort_key(case: Case) -> tuple[int, str, int]:
    """Order cases by scheduled start, pushing unscheduled ones to the end."""
    if case.scheduled_start is not None:
        return (0, case.scheduled_start.isoformat(), case.id)
    return (1, "", case.id)


def _baseline_schedule(
    cases: list[Case], rooms: list[Room], config: SolverConfig
) -> DaySchedule:
    """The current room assignment, run back-to-back under predicted durations.

    Each room keeps its own cases in scheduled order; unscheduled cases (add-on
    emergencies with no room) fall into the first room. Measured with the same
    ``evaluate`` as the optimized plan so the comparison is fair.
    """
    index_of = {room.id: i for i, room in enumerate(rooms)}
    by_room: dict[int, list[Case]] = defaultdict(list)
    for case in cases:
        room_index = index_of.get(case.room_id, 0) if case.room_id is not None else 0
        by_room[room_index].append(case)

    assignments: list[Assignment] = []
    intervals: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for room_index, room_cases in by_room.items():
        room_cases.sort(key=_schedule_sort_key)
        clock = 0
        for case in room_cases:
            duration = _duration_for(case)
            assignments.append(Assignment(case.id, room_index, clock, clock + duration))
            intervals[room_index].append((clock, clock + duration))
            clock += duration + config.turnover_minutes

    overtime, idle, makespan = evaluate(
        intervals, config.day_close_minutes, config.turnover_minutes
    )
    return DaySchedule(
        assignments=assignments,
        total_overtime_minutes=overtime,
        total_idle_minutes=idle,
        makespan_minutes=makespan,
    )


def _solver_config() -> SolverConfig:
    settings = get_settings()
    return SolverConfig(
        turnover_minutes=settings.schedule_turnover_minutes,
        day_open_minutes=0,
        day_close_minutes=(settings.or_day_end_hour - settings.or_day_start_hour) * 60,
        max_overtime_minutes=settings.schedule_max_overtime_minutes,
        weight_overtime=settings.schedule_weight_overtime,
        weight_finish=settings.schedule_weight_finish,
        random_seed=settings.schedule_random_seed,
        time_limit_seconds=settings.schedule_time_limit_seconds,
    )


def optimize_day(session: Session, service_date: date, actor: str) -> OptimizeResponse:
    settings = get_settings()
    cases = list(
        session.scalars(
            select(Case)
            .options(joinedload(Case.surgeon), joinedload(Case.procedure))
            .where(Case.service_date == service_date)
        ).all()
    )
    cases = [c for c in cases if c.status in SCHEDULABLE]
    if not cases:
        raise ScheduleError(f"no schedulable cases on {service_date.isoformat()}")

    hospital_id = cases[0].hospital_id
    rooms = list(
        session.scalars(
            select(Room)
            .where(Room.hospital_id == hospital_id, Room.active.is_(True))
            .order_by(Room.code)
        ).all()
    )
    if not rooms:
        raise ScheduleError("no active rooms to schedule into")

    config = _solver_config()
    open_dt = _open_dt(service_date, settings.or_day_start_hour)

    inputs = [
        CaseInput(case_id=c.id, surgeon_id=c.surgeon_id, duration_minutes=_duration_for(c))
        for c in cases
    ]
    baseline_schedule = _baseline_schedule(cases, rooms, config)
    try:
        solved = solve_day(inputs, num_rooms=len(rooms), config=config)
    except InfeasibleScheduleError as exc:
        raise ScheduleError(str(exc)) from exc

    # Never propose a schedule worse than the status quo: keep whichever plan
    # has less overtime (then less idle). A time-limited solver can return a
    # suboptimal plan, and the data may already be well balanced.
    def _cost(schedule: DaySchedule) -> int:
        # Overtime is far costlier than idle, matching the solver's weights.
        return (
            config.weight_overtime * schedule.total_overtime_minutes
            + schedule.total_idle_minutes
        )

    chosen = min(solved, baseline_schedule, key=_cost)

    baseline = ScheduleMetrics(
        overtime_minutes=baseline_schedule.total_overtime_minutes,
        idle_minutes=baseline_schedule.total_idle_minutes,
        makespan_minutes=baseline_schedule.makespan_minutes,
    )

    # Replace any existing pending proposals for these cases (idempotent re-run).
    case_ids = [c.id for c in cases]
    existing = session.scalars(
        select(Proposal).where(
            Proposal.case_id.in_(case_ids),
            Proposal.status == ProposalStatus.PENDING,
        )
    ).all()
    for stale in existing:
        session.delete(stale)

    proposals: list[Proposal] = []
    for assignment in chosen.assignments:
        room = rooms[assignment.room_index]
        proposal = Proposal(
            case_id=assignment.case_id,
            proposed_room_id=room.id,
            proposed_start=open_dt + timedelta(minutes=assignment.start_minutes),
            proposed_end=open_dt + timedelta(minutes=assignment.end_minutes),
            status=ProposalStatus.PENDING,
            rationale=f"Optimized schedule for {service_date.isoformat()}",
        )
        session.add(proposal)
        proposals.append(proposal)

    optimized = ScheduleMetrics(
        overtime_minutes=chosen.total_overtime_minutes,
        idle_minutes=chosen.total_idle_minutes,
        makespan_minutes=chosen.makespan_minutes,
    )

    session.add(
        AuditEvent(
            actor=actor,
            action="schedule.optimize",
            entity_type="service_date",
            before={
                "overtime": baseline.overtime_minutes,
                "idle": baseline.idle_minutes,
            },
            after={
                "overtime": optimized.overtime_minutes,
                "idle": optimized.idle_minutes,
                "proposals": len(proposals),
            },
            source=AuditSource.OPTIMIZER,
        )
    )
    session.commit()

    return OptimizeResponse(
        service_date=service_date,
        num_cases=len(cases),
        num_proposals=len(proposals),
        baseline=baseline,
        optimized=optimized,
        proposals=[_to_out(session, p) for p in proposals],
    )


def _to_out(session: Session, proposal: Proposal) -> ProposalOut:
    room_code: str | None = None
    if proposal.proposed_room_id is not None:
        room = session.get(Room, proposal.proposed_room_id)
        room_code = room.code if room else None
    return ProposalOut(
        id=proposal.id,
        case_id=proposal.case_id,
        patient_ref=proposal.case.patient_ref,
        proposed_room_code=room_code,
        proposed_start=proposal.proposed_start,
        proposed_end=proposal.proposed_end,
        status=proposal.status,
        rationale=proposal.rationale,
    )


def _case_state(case: Case) -> dict[str, Any]:
    return {
        "room_id": case.room_id,
        "scheduled_start": case.scheduled_start.isoformat()
        if case.scheduled_start
        else None,
        "scheduled_end": case.scheduled_end.isoformat() if case.scheduled_end else None,
    }


def _get_proposal(session: Session, proposal_id: int) -> Proposal:
    proposal = session.get(
        Proposal, proposal_id, options=[joinedload(Proposal.case)]
    )
    if proposal is None:
        raise ProposalNotFoundError(f"proposal {proposal_id} not found")
    return proposal


def list_proposals(
    session: Session, service_date: date | None, status: ProposalStatus | None
) -> list[ProposalOut]:
    stmt = select(Proposal).options(joinedload(Proposal.case))
    if status is not None:
        stmt = stmt.where(Proposal.status == status)
    if service_date is not None:
        stmt = stmt.join(Proposal.case).where(Case.service_date == service_date)
    proposals = session.scalars(stmt).all()
    return [_to_out(session, p) for p in proposals]


def accept_proposal(session: Session, proposal_id: int, actor: str) -> ProposalOut:
    proposal = _get_proposal(session, proposal_id)
    if proposal.status is not ProposalStatus.PENDING:
        raise ScheduleError("only pending proposals can be accepted")

    case = proposal.case
    before = _case_state(case)
    case.room_id = proposal.proposed_room_id
    case.scheduled_start = proposal.proposed_start
    case.scheduled_end = proposal.proposed_end

    proposal.status = ProposalStatus.ACCEPTED
    proposal.resolved_at = datetime.now(UTC)
    proposal.resolved_by = actor

    session.add(
        AuditEvent(
            actor=actor,
            action="proposal.accept",
            entity_type="case",
            entity_id=case.id,
            before=before,
            after=_case_state(case),
            source=AuditSource.API,
        )
    )
    session.commit()
    return _to_out(session, proposal)


def reject_proposal(session: Session, proposal_id: int, actor: str) -> ProposalOut:
    proposal = _get_proposal(session, proposal_id)
    if proposal.status is not ProposalStatus.PENDING:
        raise ScheduleError("only pending proposals can be rejected")

    proposal.status = ProposalStatus.REJECTED
    proposal.resolved_at = datetime.now(UTC)
    proposal.resolved_by = actor

    session.add(
        AuditEvent(
            actor=actor,
            action="proposal.reject",
            entity_type="case",
            entity_id=proposal.case_id,
            before=None,
            after={"proposal_id": proposal.id},
            source=AuditSource.API,
        )
    )
    session.commit()
    return _to_out(session, proposal)


def edit_proposal(
    session: Session, proposal_id: int, patch: ProposalPatch, actor: str
) -> ProposalOut:
    proposal = _get_proposal(session, proposal_id)
    if proposal.status is not ProposalStatus.PENDING:
        raise ScheduleError("only pending proposals can be edited")

    if patch.proposed_room_code is not None:
        room = session.scalars(
            select(Room).where(
                Room.hospital_id == proposal.case.hospital_id,
                Room.code == patch.proposed_room_code,
            )
        ).one_or_none()
        if room is None:
            raise ScheduleError(f"unknown room {patch.proposed_room_code}")
        proposal.proposed_room_id = room.id
    if patch.proposed_start is not None:
        proposal.proposed_start = patch.proposed_start
    if patch.proposed_end is not None:
        proposal.proposed_end = patch.proposed_end

    session.add(
        AuditEvent(
            actor=actor,
            action="proposal.edit",
            entity_type="case",
            entity_id=proposal.case_id,
            before=None,
            after={
                "proposed_room_id": proposal.proposed_room_id,
                "proposed_start": proposal.proposed_start.isoformat()
                if proposal.proposed_start
                else None,
                "proposed_end": proposal.proposed_end.isoformat()
                if proposal.proposed_end
                else None,
            },
            source=AuditSource.API,
        )
    )
    session.commit()
    return _to_out(session, proposal)
