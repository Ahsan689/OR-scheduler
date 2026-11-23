"""Tests for the ORM domain models and their relationships."""

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    AuditSource,
    BlockStatus,
    BlockTime,
    Case,
    CaseStatus,
    Hospital,
    Procedure,
    Proposal,
    ProposalStatus,
    Room,
    Staff,
    StaffRole,
    Surgeon,
)


def _hospital_with_case(session: Session) -> Case:
    hospital = Hospital(name="Demo General Hospital")
    room = Room(hospital=hospital, code="OR-1", name="Main OR")
    surgeon = Surgeon(hospital=hospital, code="SUR-001", specialty="orthopedics")
    procedure = Procedure(
        hospital=hospital,
        code="TKA",
        name="Total Knee Arthroplasty",
        specialty="orthopedics",
        baseline_duration_minutes=90,
    )
    case = Case(
        hospital=hospital,
        patient_ref="P-00123",
        procedure=procedure,
        surgeon=surgeon,
        room=room,
        service_date=date(2026, 1, 15),
        surgeon_estimate_minutes=80,
    )
    session.add(hospital)
    session.commit()
    session.refresh(case)
    return case


def test_create_case_sets_defaults_and_relationships(session: Session) -> None:
    case = _hospital_with_case(session)

    assert case.id is not None
    # Default status applied.
    assert case.status is CaseStatus.SCHEDULED
    # Prediction is unset until the predictor runs.
    assert case.predicted_duration_minutes is None
    # Surgeon estimate preserved.
    assert case.surgeon_estimate_minutes == 80
    # Server-managed timestamp populated.
    assert case.created_at is not None

    # Relationships navigate both ways.
    assert case.room is not None
    assert case.room.code == "OR-1"
    assert case.procedure.code == "TKA"
    assert case.surgeon.code == "SUR-001"
    assert case in case.hospital.cases
    assert case.room.active is True


def test_block_time_and_staff(session: Session) -> None:
    hospital = Hospital(name="Demo General Hospital")
    room = Room(hospital=hospital, code="OR-2")
    surgeon = Surgeon(hospital=hospital, code="SUR-002", specialty="orthopedics")
    nurse = Staff(hospital=hospital, code="S-001", role=StaffRole.NURSE)
    block = BlockTime(
        hospital=hospital,
        room=room,
        surgeon=surgeon,
        service_date=date(2026, 1, 16),
        start_time=datetime(2026, 1, 16, 8, 0, tzinfo=UTC),
        end_time=datetime(2026, 1, 16, 12, 0, tzinfo=UTC),
    )
    session.add(hospital)
    session.commit()
    session.refresh(block)
    session.refresh(nurse)

    assert block.status is BlockStatus.SCHEDULED
    assert block.surgeon is not None
    assert nurse.role is StaffRole.NURSE
    assert nurse in hospital.staff


def test_proposal_and_audit_event(session: Session) -> None:
    case = _hospital_with_case(session)

    proposal = Proposal(
        case=case,
        proposed_room=case.room,
        proposed_start=datetime(2026, 1, 15, 9, 0, tzinfo=UTC),
        proposed_end=datetime(2026, 1, 15, 10, 30, tzinfo=UTC),
        rationale="Reduce idle gap in OR-1",
    )
    audit = AuditEvent(
        actor="coordinator",
        action="propose_schedule",
        entity_type="case",
        entity_id=case.id,
        before={"room_id": None},
        after={"room_id": case.room_id},
        source=AuditSource.OPTIMIZER,
    )
    session.add_all([proposal, audit])
    session.commit()
    session.refresh(proposal)
    session.refresh(audit)

    assert proposal.status is ProposalStatus.PENDING
    assert proposal in case.proposals
    assert audit.id is not None
    assert audit.before == {"room_id": None}
    assert audit.after == {"room_id": case.room_id}
    assert audit.source is AuditSource.OPTIMIZER
    assert audit.created_at is not None
