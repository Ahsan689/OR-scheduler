"""Tests for the scheduling service and proposal flow."""

from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    Case,
    CaseStatus,
    Hospital,
    Procedure,
    ProposalStatus,
    Room,
    Surgeon,
)
from app.schemas.schedule import ProposalPatch
from app.services.scheduling_service import (
    accept_proposal,
    edit_proposal,
    list_proposals,
    optimize_day,
    reject_proposal,
)

DAY = date(2025, 3, 3)


def _seed(session: Session) -> None:
    hospital = Hospital(name="Demo General")
    rooms = [Room(hospital=hospital, code=c) for c in ("OR-1", "OR-2")]
    surgeons = [Surgeon(hospital=hospital, code=f"SUR-{i}", specialty="ortho") for i in range(2)]
    procedure = Procedure(
        hospital=hospital,
        code="TKA",
        name="Total Knee Arthroplasty",
        specialty="ortho",
        baseline_duration_minutes=120,
    )
    open_dt = datetime(2025, 3, 3, 8, tzinfo=UTC)
    # Baseline: all six stacked back-to-back in OR-1 (naive) -> overflows the day.
    cases = []
    for i in range(6):
        start = open_dt + timedelta(minutes=120 * i)
        cases.append(
            Case(
                hospital=hospital,
                patient_ref=f"P-{i:05d}",
                procedure=procedure,
                surgeon=surgeons[i % 2],
                room=rooms[0],
                service_date=DAY,
                scheduled_start=start,
                scheduled_end=start + timedelta(minutes=120),
                predicted_duration_minutes=120,
                surgeon_estimate_minutes=120,
                status=CaseStatus.SCHEDULED,
            )
        )
    session.add(hospital)
    session.add_all(cases)
    session.commit()


def test_optimize_creates_pending_proposals_and_cuts_overtime(session: Session) -> None:
    _seed(session)
    response = optimize_day(session, DAY, actor="coordinator")

    assert response.num_cases == 6
    assert response.num_proposals == 6
    assert all(p.status is ProposalStatus.PENDING for p in response.proposals)
    # Two rooms let the two surgeons run in parallel -> no overtime, beating baseline.
    assert response.baseline.overtime_minutes > 0
    assert response.optimized.overtime_minutes < response.baseline.overtime_minutes


def test_optimize_is_idempotent(session: Session) -> None:
    _seed(session)
    optimize_day(session, DAY, actor="c")
    optimize_day(session, DAY, actor="c")
    pending = session.scalars(
        select(Case).join(Case.proposals)
    ).all()
    # Re-running replaces stale pending proposals rather than piling them up.
    total = len(list_proposals(session, DAY, ProposalStatus.PENDING))
    assert total == 6
    assert pending  # sanity


def test_accept_applies_to_case_and_audits(session: Session) -> None:
    _seed(session)
    response = optimize_day(session, DAY, actor="coordinator")
    proposal = response.proposals[0]

    accepted = accept_proposal(session, proposal.id, actor="alice")
    assert accepted.status is ProposalStatus.ACCEPTED

    case = session.get(Case, accepted.case_id)
    assert case is not None
    assert case.scheduled_start == proposal.proposed_start
    assert case.scheduled_end == proposal.proposed_end

    events = session.scalars(select(AuditEvent)).all()
    assert any(e.action == "proposal.accept" and e.entity_id == case.id for e in events)


def test_accept_twice_is_rejected(session: Session) -> None:
    _seed(session)
    response = optimize_day(session, DAY, actor="c")
    pid = response.proposals[0].id
    accept_proposal(session, pid, actor="a")
    try:
        accept_proposal(session, pid, actor="a")
        raise AssertionError("expected ScheduleError on double accept")
    except Exception as exc:  # noqa: BLE001 - verifying it raises
        assert "pending" in str(exc)


def test_reject_and_edit(session: Session) -> None:
    _seed(session)
    response = optimize_day(session, DAY, actor="c")

    rejected = reject_proposal(session, response.proposals[1].id, actor="a")
    assert rejected.status is ProposalStatus.REJECTED

    new_start = datetime(2025, 3, 3, 7, 30, tzinfo=UTC)
    edited = edit_proposal(
        session,
        response.proposals[2].id,
        ProposalPatch(proposed_room_code="OR-2", proposed_start=new_start),
        actor="a",
    )
    assert edited.proposed_room_code == "OR-2"
    assert edited.proposed_start is not None
    # SQLite drops tzinfo on round-trip; compare the wall-clock value.
    assert edited.proposed_start.replace(tzinfo=None) == new_start.replace(tzinfo=None)


def test_optimize_endpoint_role_gate(client: TestClient, session: Session) -> None:
    _seed(session)
    assert client.post("/schedule/optimize?date=2025-03-03").status_code == 422
    assert (
        client.post(
            "/schedule/optimize?date=2025-03-03", headers={"X-Role": "nurse"}
        ).status_code
        == 403
    )
    ok = client.post(
        "/schedule/optimize?date=2025-03-03", headers={"X-Role": "coordinator"}
    )
    assert ok.status_code == 200
    assert ok.json()["num_proposals"] == 6


def test_proposal_endpoints_flow(client: TestClient, session: Session) -> None:
    _seed(session)
    optimized = client.post(
        "/schedule/optimize?date=2025-03-03", headers={"X-Role": "coordinator"}
    ).json()
    pid = optimized["proposals"][0]["id"]

    listed = client.get(
        "/proposals?date=2025-03-03&status=pending", headers={"X-Role": "nurse"}
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 6

    accepted = client.post(
        f"/proposals/{pid}/accept", headers={"X-Role": "coordinator"}
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    missing = client.post("/proposals/999999/accept", headers={"X-Role": "admin"})
    assert missing.status_code == 404
