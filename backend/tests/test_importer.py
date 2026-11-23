"""Tests for the import service."""

import io

import pytest
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Case, Room
from app.schemas.imports import ImportKind
from app.services.importer import ImportDataError, import_table, parse_table


def _seed_catalog(session: Session) -> None:
    import_table(session, ImportKind.HOSPITALS, [{"name": "Demo General"}], actor="c")
    import_table(session, ImportKind.ROOMS, [{"code": "OR-1", "name": "Main"}], actor="c")
    import_table(
        session, ImportKind.SURGEONS, [{"code": "SUR-001", "specialty": "joints"}], actor="c"
    )
    import_table(
        session,
        ImportKind.PROCEDURES,
        [
            {
                "code": "TKA",
                "name": "Total Knee Arthroplasty",
                "specialty": "joints",
                "baseline_duration_minutes": "90",
            }
        ],
        actor="c",
    )


def _case_row(**overrides: str | None) -> dict[str, str | None]:
    row: dict[str, str | None] = {
        "patient_ref": "P-00001",
        "procedure_code": "TKA",
        "surgeon_code": "SUR-001",
        "room_code": "OR-1",
        "service_date": "2025-01-02",
        "scheduled_start": "2025-01-02T08:00:00+00:00",
        "scheduled_end": "2025-01-02T09:30:00+00:00",
        "actual_start": None,
        "actual_end": None,
        "surgeon_estimate_minutes": "80",
        "status": "scheduled",
    }
    row.update(overrides)
    return row


def test_import_catalog_then_cases(session: Session) -> None:
    _seed_catalog(session)
    result = import_table(session, ImportKind.CASES, [_case_row()], actor="coordinator")

    assert result.created == 1
    assert result.skipped == 0
    assert session.scalar(select(func.count()).select_from(Case)) == 1

    case = session.scalars(select(Case)).one()
    assert case.patient_ref == "P-00001"
    assert case.procedure.code == "TKA"
    assert case.room is not None and case.room.code == "OR-1"


def test_each_import_writes_one_audit_event(session: Session) -> None:
    _seed_catalog(session)  # 4 imports
    import_table(session, ImportKind.CASES, [_case_row()], actor="coordinator")  # 5th

    events = session.scalars(select(AuditEvent)).all()
    assert len(events) == 5
    assert all(e.source.value == "import" for e in events)
    assert events[-1].after == {"created": 1, "updated": 0, "skipped": 0}


def test_invalid_rows_are_reported_not_inserted(session: Session) -> None:
    _seed_catalog(session)
    rows = [
        _case_row(patient_ref="JOHN DOE"),  # not pseudonymous
        _case_row(status="exploded"),  # bad enum
        _case_row(scheduled_end="2025-01-02T07:00:00+00:00"),  # end before start
        _case_row(),  # valid
    ]
    result = import_table(session, ImportKind.CASES, rows, actor="c")

    assert result.created == 1
    assert result.skipped == 3
    assert {e.row for e in result.errors} == {1, 2, 3}


def test_unknown_foreign_keys_are_reported(session: Session) -> None:
    _seed_catalog(session)
    rows = [_case_row(procedure_code="NOPE"), _case_row(surgeon_code="SUR-999")]
    result = import_table(session, ImportKind.CASES, rows, actor="c")

    assert result.created == 0
    assert result.skipped == 2
    assert "procedure NOPE" in result.errors[0].message


def test_catalog_upsert_updates_existing(session: Session) -> None:
    import_table(session, ImportKind.HOSPITALS, [{"name": "Demo General"}], actor="c")
    import_table(session, ImportKind.ROOMS, [{"code": "OR-1", "name": "Main"}], actor="c")
    result = import_table(
        session, ImportKind.ROOMS, [{"code": "OR-1", "name": "Renamed"}], actor="c"
    )

    assert result.created == 0
    assert result.updated == 1
    room = session.scalars(select(Room).where(Room.code == "OR-1")).one()
    assert room.name == "Renamed"


def test_importing_before_hospital_fails(session: Session) -> None:
    with pytest.raises(ImportDataError):
        import_table(session, ImportKind.ROOMS, [{"code": "OR-1"}], actor="c")


def test_parse_csv_blanks_become_none() -> None:
    content = b"code,name\nOR-1,Main\nOR-2,\n"
    rows = parse_table(content, "rooms.csv")
    assert rows == [{"code": "OR-1", "name": "Main"}, {"code": "OR-2", "name": None}]


def test_parse_xlsx() -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["code", "name"])
    sheet.append(["OR-1", "Main"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    rows = parse_table(buffer.getvalue(), "rooms.xlsx")
    assert rows == [{"code": "OR-1", "name": "Main"}]


def test_parse_rejects_unknown_extension() -> None:
    with pytest.raises(ImportDataError):
        parse_table(b"whatever", "rooms.txt")
