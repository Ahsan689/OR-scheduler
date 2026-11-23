"""Tests for emergency-insertion disruption handling."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Case, CaseStatus, Hospital, Procedure, Room, Surgeon
from app.services.disruption import simulate_emergency_handling

DAY = date(2025, 4, 1)
OPEN = datetime(2025, 4, 1, 8, tzinfo=UTC)


def _seed(session: Session) -> None:
    hospital = Hospital(name="Demo General")
    or1 = Room(hospital=hospital, code="OR-1")
    or2 = Room(hospital=hospital, code="OR-2")
    surgeon_a = Surgeon(hospital=hospital, code="SUR-A", specialty="ortho")
    surgeon_b = Surgeon(hospital=hospital, code="SUR-B", specialty="ortho")
    procedure = Procedure(
        hospital=hospital,
        code="P",
        name="Proc",
        specialty="ortho",
        baseline_duration_minutes=100,
    )

    def case(
        ref: str, room: Room, surgeon: Surgeon, start_min: int, emergency: bool
    ) -> Case:
        start = OPEN + timedelta(minutes=start_min)
        end = start + timedelta(minutes=100)
        return Case(
            hospital=hospital,
            patient_ref=ref,
            procedure=procedure,
            surgeon=surgeon,
            room=room,
            service_date=DAY,
            scheduled_start=None if emergency else start,
            scheduled_end=None if emergency else end,
            actual_start=start,
            actual_end=end,
            surgeon_estimate_minutes=100,
            status=CaseStatus.COMPLETED,
        )

    cases = [
        # OR-1: a full block of five electives for surgeon A
        *[case(f"P-1{i}", or1, surgeon_a, 125 * i, False) for i in range(5)],
        # OR-2: a single elective for surgeon B (lots of slack)
        case("P-20", or2, surgeon_b, 0, False),
        # Emergency assigned (manually) to the already-full OR-1
        case("P-99", or1, surgeon_a, 700, True),
    ]
    session.add(hospital)
    session.add_all(cases)
    session.commit()


def test_optimizer_places_emergency_in_slack_room(session: Session) -> None:
    result = simulate_emergency_handling(session)  # empty -> safe
    assert result.days == 0

    _seed(session)
    result = simulate_emergency_handling(session)

    assert result.days == 1
    assert result.emergencies == 1
    # Baseline piles the emergency onto the full OR-1; the optimizer moves it to
    # OR-2, cutting overtime.
    assert result.optimized_overtime_minutes < result.baseline_overtime_minutes
    assert result.overtime_reduction_pct > 0
