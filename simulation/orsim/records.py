"""Flat record dataclasses, one per output CSV row.

These use external *codes* (not database IDs); the import step resolves codes
to foreign keys. Patients appear only as pseudonymous references.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class HospitalRecord:
    name: str


@dataclass(frozen=True)
class RoomRecord:
    code: str
    name: str


@dataclass(frozen=True)
class SurgeonRecord:
    code: str
    specialty: str


@dataclass(frozen=True)
class StaffRecord:
    code: str
    role: str


@dataclass(frozen=True)
class ProcedureRecord:
    code: str
    name: str
    specialty: str
    baseline_duration_minutes: int


@dataclass(frozen=True)
class CaseRecord:
    patient_ref: str
    procedure_code: str
    surgeon_code: str
    room_code: str
    service_date: date
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    surgeon_estimate_minutes: int
    status: str
    is_emergency: bool


@dataclass(frozen=True)
class BlockTimeRecord:
    room_code: str
    surgeon_code: str | None
    service: str | None
    service_date: date
    start_time: datetime
    end_time: datetime
    status: str


@dataclass(frozen=True)
class SyntheticDataset:
    """The full generated dataset, grouped by entity."""

    hospital: HospitalRecord
    rooms: list[RoomRecord]
    surgeons: list[SurgeonRecord]
    staff: list[StaffRecord]
    procedures: list[ProcedureRecord]
    cases: list[CaseRecord]
    block_times: list[BlockTimeRecord]
