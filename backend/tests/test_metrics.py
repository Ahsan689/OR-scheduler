"""Tests for the dashboard metrics service, using a hand-computed scenario."""

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Case, CaseStatus, Hospital, Procedure, Room, Surgeon
from app.services.metrics import compute_dashboard

DAY = date(2025, 1, 2)


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2025, 1, 2, hour, minute, tzinfo=UTC)


def _seed(session: Session) -> None:
    hospital = Hospital(name="Demo General")
    or1 = Room(hospital=hospital, code="OR-1")
    or2 = Room(hospital=hospital, code="OR-2")
    surgeon = Surgeon(hospital=hospital, code="SUR-001", specialty="joints")
    tka = Procedure(
        hospital=hospital,
        code="TKA",
        name="Total Knee Arthroplasty",
        specialty="joints",
        baseline_duration_minutes=90,
    )

    def case(
        room: Room,
        start: datetime | None,
        end: datetime | None,
        estimate: int | None,
        status: CaseStatus,
        ref: str,
    ) -> Case:
        return Case(
            hospital=hospital,
            patient_ref=ref,
            procedure=tka,
            surgeon=surgeon,
            room=room,
            service_date=DAY,
            actual_start=start,
            actual_end=end,
            surgeon_estimate_minutes=estimate,
            status=status,
        )

    session.add_all(
        [
            # OR-1: operative 120 + 90 = 210, idle 30, on-time, overtime 0
            case(or1, _dt(8, 0), _dt(10, 0), 90, CaseStatus.COMPLETED, "P-00001"),
            case(or1, _dt(10, 30), _dt(12, 0), 100, CaseStatus.COMPLETED, "P-00002"),
            # OR-2: operative 490, late start (08:30), overtime 40
            case(or2, _dt(8, 30), _dt(16, 40), 480, CaseStatus.COMPLETED, "P-00003"),
            # Non-running cases
            case(or1, None, None, 90, CaseStatus.CANCELLED, "P-00004"),
            case(or1, None, None, 90, CaseStatus.NO_SHOW, "P-00005"),
        ]
    )
    session.commit()


def test_summary_numbers(session: Session) -> None:
    _seed(session)
    result = compute_dashboard(session)
    s = result.summary

    assert s.room_days == 2
    assert s.cases_ran == 3
    assert s.cases_cancelled == 1
    assert s.cases_no_show == 1
    assert s.avg_cases_per_room_day == 1.5
    # operative 700 / (2 * 480) = 72.92%
    assert s.avg_utilization_pct == 72.92
    assert s.total_idle_minutes == 30
    assert s.total_overtime_minutes == 40
    assert s.on_time_start_rate == 0.5
    # overruns: OR-1 (30 + 0), OR-2 (10) over 3 cases = 13.33
    assert s.avg_overrun_minutes_per_case == 13.33


def test_per_room_breakdown(session: Session) -> None:
    _seed(session)
    result = compute_dashboard(session)
    rooms = {r.room_code: r for r in result.rooms}

    assert rooms["OR-1"].utilization_pct == 43.75
    assert rooms["OR-1"].idle_minutes == 30
    assert rooms["OR-1"].overtime_minutes == 0
    assert rooms["OR-1"].on_time_start_rate == 1.0

    assert rooms["OR-2"].overtime_minutes == 40
    assert rooms["OR-2"].on_time_start_rate == 0.0
    assert rooms["OR-2"].utilization_pct > 100  # ran past close


def test_procedure_accuracy(session: Session) -> None:
    _seed(session)
    result = compute_dashboard(session)
    tka = next(p for p in result.procedures if p.procedure_code == "TKA")

    assert tka.cases == 3
    assert tka.avg_estimate_minutes == round((90 + 100 + 480) / 3, 2)
    assert tka.avg_actual_minutes == round((120 + 90 + 490) / 3, 2)


def test_empty_dataset_is_safe(session: Session) -> None:
    result = compute_dashboard(session)
    assert result.summary.cases_ran == 0
    assert result.summary.avg_utilization_pct == 0.0
    assert result.rooms == []
    assert result.daily == []


def test_dashboard_endpoint_requires_role(client: TestClient) -> None:
    assert client.get("/metrics/dashboard").status_code == 422


def test_dashboard_endpoint_returns_data(client: TestClient, session: Session) -> None:
    _seed(session)
    response = client.get("/metrics/dashboard", headers={"X-Role": "nurse"})
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["cases_ran"] == 3
    assert len(body["rooms"]) == 2
