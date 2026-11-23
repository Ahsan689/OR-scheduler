"""Tests for the baseline-vs-optimized simulation."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Case, CaseStatus, Hospital, Procedure, Room, Surgeon
from app.services.simulation import run_simulation

DAY = date(2025, 1, 6)
OPEN = datetime(2025, 1, 6, 8, tzinfo=UTC)


def _seed(session: Session) -> None:
    hospital = Hospital(name="Demo General")
    room = Room(hospital=hospital, code="OR-1")
    surgeon = Surgeon(hospital=hospital, code="SUR-1", specialty="ortho")
    procedure = Procedure(
        hospital=hospital,
        code="P",
        name="Proc",
        specialty="ortho",
        baseline_duration_minutes=60,
    )

    def case(ref: str, start_min: int, end_min: int) -> Case:
        start = OPEN + timedelta(minutes=start_min)
        end = OPEN + timedelta(minutes=end_min)
        return Case(
            hospital=hospital,
            patient_ref=ref,
            procedure=procedure,
            surgeon=surgeon,
            room=room,
            service_date=DAY,
            scheduled_start=start,
            scheduled_end=end,
            actual_start=start,
            actual_end=end,
            predicted_duration_minutes=60,
            surgeon_estimate_minutes=55,
            status=CaseStatus.COMPLETED,
        )

    cases = [
        case("P-00001", 30, 90),  # late first start (08:30)
        case("P-00002", 120, 180),  # 30-min idle gap before this
        case("P-00003", 180, 240),
    ]
    cancelled = Case(
        hospital=hospital,
        patient_ref="P-00004",
        procedure=procedure,
        surgeon=surgeon,
        room=room,
        service_date=DAY,
        surgeon_estimate_minutes=55,
        status=CaseStatus.CANCELLED,
    )
    session.add(hospital)
    session.add_all([*cases, cancelled])
    session.commit()


def test_optimized_cuts_idle_and_improves_on_time(session: Session) -> None:
    result = run_simulation(session)
    # empty DB: safe, zeroed result
    assert result.days == 0

    _seed(session)
    result = run_simulation(session)

    assert result.days == 1
    assert result.cancellations == 1
    assert result.baseline.idle_minutes > 0
    assert result.optimized.idle_minutes < result.baseline.idle_minutes
    assert result.optimized.on_time_rate > result.baseline.on_time_rate
    assert result.idle_reduction_pct > 0
