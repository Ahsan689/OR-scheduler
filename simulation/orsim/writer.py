"""Write a :class:`SyntheticDataset` to CSV files.

Columns are declared explicitly (rather than derived from the dataclasses) so
the output schema stays aligned with the backend import contract.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from orsim.records import SyntheticDataset

CASE_COLUMNS = (
    "patient_ref",
    "procedure_code",
    "surgeon_code",
    "room_code",
    "service_date",
    "scheduled_start",
    "scheduled_end",
    "actual_start",
    "actual_end",
    "surgeon_estimate_minutes",
    "status",
)

BLOCK_COLUMNS = (
    "room_code",
    "surgeon_code",
    "service",
    "service_date",
    "start_time",
    "end_time",
    "status",
)


def _fmt(value: object) -> str:
    """Serialize a cell value; ``None`` becomes an empty string."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _write_csv(path: Path, header: tuple[str, ...], rows: list[list[object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row in rows:
            writer.writerow([_fmt(cell) for cell in row])


def write_dataset(dataset: SyntheticDataset, out_dir: Path) -> dict[str, Path]:
    """Write every entity to ``out_dir`` and return the paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    def emit(name: str, header: tuple[str, ...], rows: list[list[object]]) -> None:
        path = out_dir / f"{name}.csv"
        _write_csv(path, header, rows)
        paths[name] = path

    emit("hospitals", ("name",), [[dataset.hospital.name]])
    emit("rooms", ("code", "name"), [[r.code, r.name] for r in dataset.rooms])
    emit(
        "surgeons",
        ("code", "specialty"),
        [[s.code, s.specialty] for s in dataset.surgeons],
    )
    emit("staff", ("code", "role"), [[s.code, s.role] for s in dataset.staff])
    emit(
        "procedures",
        ("code", "name", "specialty", "baseline_duration_minutes"),
        [
            [p.code, p.name, p.specialty, p.baseline_duration_minutes]
            for p in dataset.procedures
        ],
    )
    emit(
        "cases",
        CASE_COLUMNS,
        [
            [
                c.patient_ref,
                c.procedure_code,
                c.surgeon_code,
                c.room_code,
                c.service_date,
                c.scheduled_start,
                c.scheduled_end,
                c.actual_start,
                c.actual_end,
                c.surgeon_estimate_minutes,
                c.status,
            ]
            for c in dataset.cases
        ],
    )
    emit(
        "block_times",
        BLOCK_COLUMNS,
        [
            [
                b.room_code,
                b.surgeon_code,
                b.service,
                b.service_date,
                b.start_time,
                b.end_time,
                b.status,
            ]
            for b in dataset.block_times
        ],
    )
    return paths
