"""Tests for CSV serialization."""

import csv
from pathlib import Path

from orsim.config import SimConfig
from orsim.enums import CASE_CANCELLED
from orsim.generator import generate_dataset
from orsim.writer import CASE_COLUMNS, write_dataset


def test_write_dataset_creates_all_files(tmp_path: Path) -> None:
    dataset = generate_dataset(SimConfig(months=1))
    paths = write_dataset(dataset, tmp_path)

    expected = {
        "hospitals",
        "rooms",
        "surgeons",
        "staff",
        "procedures",
        "cases",
        "block_times",
    }
    assert set(paths) == expected
    for path in paths.values():
        assert path.exists()


def test_cases_csv_header_and_row_count(tmp_path: Path) -> None:
    dataset = generate_dataset(SimConfig(months=1))
    write_dataset(dataset, tmp_path)

    with (tmp_path / "cases.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert tuple(rows[0]) == CASE_COLUMNS
    assert len(rows) - 1 == len(dataset.cases)


def test_cancelled_case_has_empty_actual_times(tmp_path: Path) -> None:
    dataset = generate_dataset(SimConfig(months=2))
    write_dataset(dataset, tmp_path)

    with (tmp_path / "cases.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        cancelled = [r for r in reader if r["status"] == CASE_CANCELLED]

    assert cancelled  # at least one in two months
    for row in cancelled:
        assert row["actual_start"] == ""
        assert row["actual_end"] == ""
