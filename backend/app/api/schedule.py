"""Scheduler and proposal endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Principal, Role, get_principal, require_roles
from app.models.enums import ProposalStatus
from app.schemas.schedule import OptimizeResponse, ProposalOut, ProposalPatch
from app.services.scheduling_service import (
    ProposalNotFoundError,
    ScheduleError,
    accept_proposal,
    edit_proposal,
    list_proposals,
    optimize_day,
    reject_proposal,
)

schedule_router = APIRouter(prefix="/schedule", tags=["schedule"])
proposals_router = APIRouter(prefix="/proposals", tags=["proposals"])

Coordinator = Annotated[Principal, Depends(require_roles(Role.COORDINATOR, Role.ADMIN))]
AnyRole = Annotated[Principal, Depends(get_principal)]
Db = Annotated[Session, Depends(get_db)]


def _handle(exc: ScheduleError) -> HTTPException:
    code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(exc, ProposalNotFoundError)
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=code, detail=str(exc))


@schedule_router.post("/optimize", response_model=OptimizeResponse)
def optimize(
    db: Db,
    principal: Coordinator,
    date_: Annotated[date, Query(alias="date")],
) -> OptimizeResponse:
    """Build an optimized schedule for a date and store it as proposals."""
    try:
        return optimize_day(db, date_, actor=principal.actor)
    except ScheduleError as exc:
        raise _handle(exc) from exc


@proposals_router.get("", response_model=list[ProposalOut])
def get_proposals(
    db: Db,
    principal: AnyRole,
    date_: Annotated[date | None, Query(alias="date")] = None,
    proposal_status: Annotated[ProposalStatus | None, Query(alias="status")] = None,
) -> list[ProposalOut]:
    """List proposals, optionally filtered by date and status."""
    return list_proposals(db, date_, proposal_status)


@proposals_router.post("/{proposal_id}/accept", response_model=ProposalOut)
def accept(db: Db, principal: Coordinator, proposal_id: int) -> ProposalOut:
    """Apply a proposal to its case (the human approval step)."""
    try:
        return accept_proposal(db, proposal_id, actor=principal.actor)
    except ScheduleError as exc:
        raise _handle(exc) from exc


@proposals_router.post("/{proposal_id}/reject", response_model=ProposalOut)
def reject(db: Db, principal: Coordinator, proposal_id: int) -> ProposalOut:
    try:
        return reject_proposal(db, proposal_id, actor=principal.actor)
    except ScheduleError as exc:
        raise _handle(exc) from exc


@proposals_router.patch("/{proposal_id}", response_model=ProposalOut)
def edit(
    db: Db, principal: Coordinator, proposal_id: int, patch: ProposalPatch
) -> ProposalOut:
    try:
        return edit_proposal(db, proposal_id, patch, actor=principal.actor)
    except ScheduleError as exc:
        raise _handle(exc) from exc
