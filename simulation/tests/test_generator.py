"""Tests for the synthetic data generator."""

import statistics
from dataclasses import replace

from orsim.config import SimConfig
from orsim.enums import (
    BLOCK_RELEASED,
    BLOCK_UNUSED,
    CASE_CANCELLED,
    CASE_COMPLETED,
    CASE_NO_SHOW,
)
from orsim.generator import generate_dataset
from orsim.records import CaseRecord


def _duration_minutes(case: CaseRecord) -> float:
    assert case.actual_start is not None
    assert case.actual_end is not None
    return (case.actual_end - case.actual_start).total_seconds() / 60.0


def test_reproducible_for_same_seed() -> None:
    a = generate_dataset(SimConfig(seed=7))
    b = generate_dataset(SimConfig(seed=7))
    assert a.cases == b.cases
    assert a.block_times == b.block_times


def test_different_seed_changes_output() -> None:
    a = generate_dataset(SimConfig(seed=1))
    b = generate_dataset(SimConfig(seed=2))
    assert a.cases != b.cases


def test_covers_a_year_of_weekdays_across_all_rooms() -> None:
    config = SimConfig()
    dataset = generate_dataset(config)

    dates = [c.service_date for c in dataset.cases]
    span_days = (max(dates) - min(dates)).days
    assert span_days > 330  # roughly a year

    assert all(d.weekday() < 5 for d in dates)  # weekdays only
    assert {c.room_code for c in dataset.cases} == set(config.rooms)


def test_referential_integrity_and_unique_patients() -> None:
    dataset = generate_dataset(SimConfig())
    procedure_codes = {p.code for p in dataset.procedures}
    surgeon_codes = {s.code for s in dataset.surgeons}
    room_codes = {r.code for r in dataset.rooms}

    for case in dataset.cases:
        assert case.procedure_code in procedure_codes
        assert case.surgeon_code in surgeon_codes
        assert case.room_code in room_codes

    refs = [c.patient_ref for c in dataset.cases]
    assert len(refs) == len(set(refs))


def test_surgeon_estimates_are_optimistic_on_average() -> None:
    dataset = generate_dataset(SimConfig())
    completed = [
        c
        for c in dataset.cases
        if c.status == CASE_COMPLETED and not c.is_emergency
    ]
    assert completed

    mean_estimate = statistics.mean(c.surgeon_estimate_minutes for c in completed)
    mean_actual = statistics.mean(_duration_minutes(c) for c in completed)
    # Surgeons under-estimate: real durations run longer than their estimates.
    assert mean_actual > mean_estimate


def test_actual_durations_are_right_skewed() -> None:
    dataset = generate_dataset(SimConfig())
    durations = [
        _duration_minutes(c) for c in dataset.cases if c.status == CASE_COMPLETED
    ]
    # Log-normal: mean is pulled above the median by the right tail.
    assert statistics.mean(durations) > statistics.median(durations)


def test_contains_cancellations_emergencies_and_idle_blocks() -> None:
    dataset = generate_dataset(SimConfig())

    statuses = {c.status for c in dataset.cases}
    assert CASE_CANCELLED in statuses
    assert CASE_NO_SHOW in statuses
    assert any(c.is_emergency for c in dataset.cases)

    block_statuses = {b.status for b in dataset.block_times}
    assert BLOCK_UNUSED in block_statuses
    assert BLOCK_RELEASED in block_statuses


def test_case_time_fields_match_status() -> None:
    dataset = generate_dataset(SimConfig())
    for case in dataset.cases:
        if case.status in (CASE_CANCELLED, CASE_NO_SHOW):
            assert case.actual_start is None
            assert case.actual_end is None
        if case.status == CASE_COMPLETED:
            assert case.actual_start is not None
            assert case.actual_end is not None
            assert case.actual_end > case.actual_start
        if case.is_emergency:
            # Add-on emergencies are not scheduled in advance.
            assert case.scheduled_start is None
        else:
            assert case.scheduled_start is not None


def test_config_overrides_take_effect() -> None:
    small = replace(SimConfig(), months=1, rooms=("OR-1",))
    dataset = generate_dataset(small)
    assert {c.room_code for c in dataset.cases} == {"OR-1"}
    span_days = (
        max(c.service_date for c in dataset.cases)
        - min(c.service_date for c in dataset.cases)
    ).days
    assert span_days < 40
