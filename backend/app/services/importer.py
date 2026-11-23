"""Import service: parse and validate uploaded tables, then persist them.

Business rules:
- Uploaded files are never trusted; each row is validated with Pydantic.
- Catalog entities (rooms, surgeons, staff, procedures) upsert by code within
  the single hospital. Cases and blocks resolve their foreign keys by code.
- Invalid rows are reported and skipped; valid rows in the same file are still
  imported. The whole batch is committed atomically.
- Each import writes one summary ``AuditEvent`` (source = import).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from datetime import date, datetime

from openpyxl import load_workbook
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    AuditSource,
    BlockTime,
    Case,
    Hospital,
    Procedure,
    Room,
    Staff,
    Surgeon,
)
from app.schemas.imports import (
    BlockTimeIn,
    CaseIn,
    HospitalIn,
    ImportKind,
    ImportResult,
    ProcedureIn,
    RoomIn,
    RowError,
    StaffIn,
    SurgeonIn,
)

MAX_ROWS = 100_000


class ImportDataError(Exception):
    """Raised for import problems the caller should fix (mapped to HTTP 400)."""


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def _stringify(value: object) -> str | None:
    """Normalize a cell value to a string (or None for blanks)."""
    if value is None:
        return None
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text or None


def parse_table(content: bytes, filename: str) -> list[dict[str, str | None]]:
    """Parse CSV or XLSX bytes into a list of row dicts."""
    name = filename.lower()
    if name.endswith(".csv"):
        rows = _parse_csv(content)
    elif name.endswith(".xlsx"):
        rows = _parse_xlsx(content)
    else:
        raise ImportDataError("Unsupported file type; use .csv or .xlsx")

    if len(rows) > MAX_ROWS:
        raise ImportDataError(f"Too many rows ({len(rows)} > {MAX_ROWS})")
    return rows


def _parse_csv(content: bytes) -> list[dict[str, str | None]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [{key: _stringify(value) for key, value in row.items()} for row in reader]


def _parse_xlsx(content: bytes) -> list[dict[str, str | None]]:
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = workbook.active
    if sheet is None:
        return []
    row_iter = sheet.iter_rows(values_only=True)
    try:
        header_raw = next(row_iter)
    except StopIteration:
        return []
    headers = [str(cell) if cell is not None else "" for cell in header_raw]
    rows: list[dict[str, str | None]] = []
    for raw in row_iter:
        rows.append({headers[i]: _stringify(raw[i]) for i in range(len(headers))})
    workbook.close()
    return rows


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _format_validation_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(item) for item in err["loc"])
        parts.append(f"{loc}: {err['msg']}" if loc else err["msg"])
    return "; ".join(parts)


def _get_single_hospital(session: Session) -> Hospital:
    hospitals = session.scalars(select(Hospital)).all()
    if not hospitals:
        raise ImportDataError("No hospital found; import hospitals first")
    if len(hospitals) > 1:
        raise ImportDataError("Multiple hospitals found; import is single-hospital")
    return hospitals[0]


def _validate(
    rows: Sequence[dict[str, str | None]], model_cls: type[BaseModel]
) -> tuple[list[tuple[int, BaseModel]], list[RowError]]:
    """Validate rows, returning (index, model) pairs and per-row errors."""
    valid: list[tuple[int, BaseModel]] = []
    errors: list[RowError] = []
    for index, row in enumerate(rows, start=1):
        try:
            valid.append((index, model_cls.model_validate(row)))
        except ValidationError as exc:
            errors.append(RowError(row=index, message=_format_validation_error(exc)))
    return valid, errors


# --------------------------------------------------------------------------- #
# Per-kind importers
# --------------------------------------------------------------------------- #
def _import_hospitals(session: Session, rows: Sequence[dict[str, str | None]]) -> ImportResult:
    valid, errors = _validate(rows, HospitalIn)
    existing = {h.name for h in session.scalars(select(Hospital)).all()}
    created = updated = 0
    for _, model in valid:
        assert isinstance(model, HospitalIn)
        if model.name in existing:
            updated += 1
        else:
            session.add(Hospital(name=model.name))
            existing.add(model.name)
            created += 1
    return ImportResult(
        kind=ImportKind.HOSPITALS, created=created, updated=updated,
        skipped=len(errors), errors=errors,
    )


def _import_rooms(
    session: Session, hospital: Hospital, rows: Sequence[dict[str, str | None]]
) -> ImportResult:
    valid, errors = _validate(rows, RoomIn)
    existing = {
        r.code: r
        for r in session.scalars(select(Room).where(Room.hospital_id == hospital.id)).all()
    }
    created = updated = 0
    for _, model in valid:
        assert isinstance(model, RoomIn)
        if model.code in existing:
            existing[model.code].name = model.name
            updated += 1
        else:
            room = Room(hospital_id=hospital.id, code=model.code, name=model.name)
            session.add(room)
            existing[model.code] = room
            created += 1
    return ImportResult(
        kind=ImportKind.ROOMS, created=created, updated=updated,
        skipped=len(errors), errors=errors,
    )


def _import_surgeons(
    session: Session, hospital: Hospital, rows: Sequence[dict[str, str | None]]
) -> ImportResult:
    valid, errors = _validate(rows, SurgeonIn)
    existing = {
        s.code: s
        for s in session.scalars(
            select(Surgeon).where(Surgeon.hospital_id == hospital.id)
        ).all()
    }
    created = updated = 0
    for _, model in valid:
        assert isinstance(model, SurgeonIn)
        if model.code in existing:
            existing[model.code].specialty = model.specialty
            updated += 1
        else:
            surgeon = Surgeon(
                hospital_id=hospital.id, code=model.code, specialty=model.specialty
            )
            session.add(surgeon)
            existing[model.code] = surgeon
            created += 1
    return ImportResult(
        kind=ImportKind.SURGEONS, created=created, updated=updated,
        skipped=len(errors), errors=errors,
    )


def _import_staff(
    session: Session, hospital: Hospital, rows: Sequence[dict[str, str | None]]
) -> ImportResult:
    valid, errors = _validate(rows, StaffIn)
    existing = {
        s.code: s
        for s in session.scalars(select(Staff).where(Staff.hospital_id == hospital.id)).all()
    }
    created = updated = 0
    for _, model in valid:
        assert isinstance(model, StaffIn)
        if model.code in existing:
            existing[model.code].role = model.role
            updated += 1
        else:
            member = Staff(hospital_id=hospital.id, code=model.code, role=model.role)
            session.add(member)
            existing[model.code] = member
            created += 1
    return ImportResult(
        kind=ImportKind.STAFF, created=created, updated=updated,
        skipped=len(errors), errors=errors,
    )


def _import_procedures(
    session: Session, hospital: Hospital, rows: Sequence[dict[str, str | None]]
) -> ImportResult:
    valid, errors = _validate(rows, ProcedureIn)
    existing = {
        p.code: p
        for p in session.scalars(
            select(Procedure).where(Procedure.hospital_id == hospital.id)
        ).all()
    }
    created = updated = 0
    for _, model in valid:
        assert isinstance(model, ProcedureIn)
        if model.code in existing:
            proc = existing[model.code]
            proc.name = model.name
            proc.specialty = model.specialty
            proc.baseline_duration_minutes = model.baseline_duration_minutes
            updated += 1
        else:
            proc = Procedure(
                hospital_id=hospital.id,
                code=model.code,
                name=model.name,
                specialty=model.specialty,
                baseline_duration_minutes=model.baseline_duration_minutes,
            )
            session.add(proc)
            existing[model.code] = proc
            created += 1
    return ImportResult(
        kind=ImportKind.PROCEDURES, created=created, updated=updated,
        skipped=len(errors), errors=errors,
    )


def _import_cases(
    session: Session, hospital: Hospital, rows: Sequence[dict[str, str | None]]
) -> ImportResult:
    valid, errors = _validate(rows, CaseIn)
    procedures = {
        p.code: p.id
        for p in session.scalars(
            select(Procedure).where(Procedure.hospital_id == hospital.id)
        ).all()
    }
    surgeons = {
        s.code: s.id
        for s in session.scalars(
            select(Surgeon).where(Surgeon.hospital_id == hospital.id)
        ).all()
    }
    rooms = {
        r.code: r.id
        for r in session.scalars(select(Room).where(Room.hospital_id == hospital.id)).all()
    }

    created = 0
    for index, model in valid:
        assert isinstance(model, CaseIn)
        procedure_id = procedures.get(model.procedure_code)
        surgeon_id = surgeons.get(model.surgeon_code)
        room_id = rooms.get(model.room_code) if model.room_code else None

        missing: list[str] = []
        if procedure_id is None:
            missing.append(f"procedure {model.procedure_code}")
        if surgeon_id is None:
            missing.append(f"surgeon {model.surgeon_code}")
        if model.room_code and room_id is None:
            missing.append(f"room {model.room_code}")
        if missing:
            errors.append(RowError(row=index, message="unknown " + ", ".join(missing)))
            continue

        assert procedure_id is not None and surgeon_id is not None
        session.add(
            Case(
                hospital_id=hospital.id,
                patient_ref=model.patient_ref,
                procedure_id=procedure_id,
                surgeon_id=surgeon_id,
                room_id=room_id,
                service_date=model.service_date,
                scheduled_start=model.scheduled_start,
                scheduled_end=model.scheduled_end,
                actual_start=model.actual_start,
                actual_end=model.actual_end,
                surgeon_estimate_minutes=model.surgeon_estimate_minutes,
                status=model.status,
            )
        )
        created += 1
    return ImportResult(
        kind=ImportKind.CASES, created=created, updated=0,
        skipped=len(errors), errors=errors,
    )


def _import_block_times(
    session: Session, hospital: Hospital, rows: Sequence[dict[str, str | None]]
) -> ImportResult:
    valid, errors = _validate(rows, BlockTimeIn)
    surgeons = {
        s.code: s.id
        for s in session.scalars(
            select(Surgeon).where(Surgeon.hospital_id == hospital.id)
        ).all()
    }
    rooms = {
        r.code: r.id
        for r in session.scalars(select(Room).where(Room.hospital_id == hospital.id)).all()
    }

    created = 0
    for index, model in valid:
        assert isinstance(model, BlockTimeIn)
        room_id = rooms.get(model.room_code)
        surgeon_id = surgeons.get(model.surgeon_code) if model.surgeon_code else None

        missing: list[str] = []
        if room_id is None:
            missing.append(f"room {model.room_code}")
        if model.surgeon_code and surgeon_id is None:
            missing.append(f"surgeon {model.surgeon_code}")
        if missing:
            errors.append(RowError(row=index, message="unknown " + ", ".join(missing)))
            continue

        assert room_id is not None
        session.add(
            BlockTime(
                hospital_id=hospital.id,
                room_id=room_id,
                surgeon_id=surgeon_id,
                service=model.service,
                service_date=model.service_date,
                start_time=model.start_time,
                end_time=model.end_time,
                status=model.status,
            )
        )
        created += 1
    return ImportResult(
        kind=ImportKind.BLOCK_TIMES, created=created, updated=0,
        skipped=len(errors), errors=errors,
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def import_table(
    session: Session,
    kind: ImportKind,
    rows: Sequence[dict[str, str | None]],
    actor: str,
) -> ImportResult:
    """Validate and persist one table; writes an audit event and commits."""
    if kind is ImportKind.HOSPITALS:
        result = _import_hospitals(session, rows)
    else:
        hospital = _get_single_hospital(session)
        if kind is ImportKind.ROOMS:
            result = _import_rooms(session, hospital, rows)
        elif kind is ImportKind.SURGEONS:
            result = _import_surgeons(session, hospital, rows)
        elif kind is ImportKind.STAFF:
            result = _import_staff(session, hospital, rows)
        elif kind is ImportKind.PROCEDURES:
            result = _import_procedures(session, hospital, rows)
        elif kind is ImportKind.CASES:
            result = _import_cases(session, hospital, rows)
        else:
            result = _import_block_times(session, hospital, rows)

    session.add(
        AuditEvent(
            actor=actor,
            action=f"import.{kind.value}",
            entity_type=kind.value,
            before=None,
            after={
                "created": result.created,
                "updated": result.updated,
                "skipped": result.skipped,
            },
            source=AuditSource.IMPORT,
        )
    )
    session.commit()
    return result
