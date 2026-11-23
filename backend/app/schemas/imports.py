"""Pydantic schemas for validating imported data.

Uploaded files are never trusted: every row is validated here before it can
touch the database.
"""

from __future__ import annotations

import enum
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import BlockStatus, CaseStatus, StaffRole


class ImportKind(str, enum.Enum):
    """The kinds of tables that can be imported, one file at a time."""

    HOSPITALS = "hospitals"
    ROOMS = "rooms"
    SURGEONS = "surgeons"
    STAFF = "staff"
    PROCEDURES = "procedures"
    CASES = "cases"
    BLOCK_TIMES = "block_times"


class HospitalIn(BaseModel):
    name: str = Field(min_length=1)


class RoomIn(BaseModel):
    code: str = Field(min_length=1)
    name: str | None = None


class SurgeonIn(BaseModel):
    code: str = Field(min_length=1)
    specialty: str = Field(min_length=1)


class StaffIn(BaseModel):
    code: str = Field(min_length=1)
    role: StaffRole


class ProcedureIn(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    specialty: str = Field(min_length=1)
    baseline_duration_minutes: int = Field(gt=0)


class CaseIn(BaseModel):
    # Pseudonymous reference only, e.g. "P-00123". No real identifiers allowed.
    patient_ref: str = Field(pattern=r"^P-\d{3,}$")
    procedure_code: str = Field(min_length=1)
    surgeon_code: str = Field(min_length=1)
    room_code: str | None = None
    service_date: date
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    surgeon_estimate_minutes: int | None = Field(default=None, gt=0)
    status: CaseStatus

    @model_validator(mode="after")
    def _check_time_ordering(self) -> CaseIn:
        if (
            self.scheduled_start is not None
            and self.scheduled_end is not None
            and self.scheduled_end <= self.scheduled_start
        ):
            raise ValueError("scheduled_end must be after scheduled_start")
        if (
            self.actual_start is not None
            and self.actual_end is not None
            and self.actual_end <= self.actual_start
        ):
            raise ValueError("actual_end must be after actual_start")
        return self


class BlockTimeIn(BaseModel):
    room_code: str = Field(min_length=1)
    surgeon_code: str | None = None
    service: str | None = None
    service_date: date
    start_time: datetime
    end_time: datetime
    status: BlockStatus

    @model_validator(mode="after")
    def _check_window(self) -> BlockTimeIn:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class RowError(BaseModel):
    """A single rejected row (1-based index) and why it failed."""

    row: int
    message: str


class ImportResult(BaseModel):
    """Summary returned to the caller after an import."""

    kind: ImportKind
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[RowError] = Field(default_factory=list)
