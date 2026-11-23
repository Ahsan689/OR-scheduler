"""Schemas for the scheduler and proposal flow."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import ProposalStatus


class ScheduleMetrics(BaseModel):
    overtime_minutes: int
    idle_minutes: int
    makespan_minutes: int


class ProposalOut(BaseModel):
    id: int
    case_id: int
    patient_ref: str
    proposed_room_code: str | None
    proposed_start: datetime | None
    proposed_end: datetime | None
    status: ProposalStatus
    rationale: str | None


class OptimizeResponse(BaseModel):
    service_date: date
    num_cases: int
    num_proposals: int
    baseline: ScheduleMetrics
    optimized: ScheduleMetrics
    proposals: list[ProposalOut]


class ProposalPatch(BaseModel):
    proposed_room_code: str | None = None
    proposed_start: datetime | None = None
    proposed_end: datetime | None = None
