"""Deterministic synthetic data generation.

Given a :class:`SimConfig`, :func:`generate_dataset` produces a full, internally
consistent dataset: a hospital, its rooms/surgeons/staff/procedures, a year of
block time, and the surgical cases that filled (or didn't fill) those blocks.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta

import numpy as np

from orsim.config import ProcedureSpec, SimConfig, SurgeonSpec
from orsim.enums import (
    BLOCK_RELEASED,
    BLOCK_UNUSED,
    BLOCK_USED,
    CASE_CANCELLED,
    CASE_COMPLETED,
    CASE_NO_SHOW,
)
from orsim.records import (
    BlockTimeRecord,
    CaseRecord,
    HospitalRecord,
    ProcedureRecord,
    RoomRecord,
    SurgeonRecord,
    SyntheticDataset,
)


def _weekdays(config: SimConfig) -> list[date]:
    """Every weekday (Mon-Fri) in the configured window."""
    end = _add_months(config.start_date, config.months)
    days: list[date] = []
    current = config.start_date
    while current < end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def _lognormal_minutes(rng: np.random.Generator, median: float, sigma: float) -> int:
    """Draw a strictly positive duration in whole minutes from a log-normal."""
    value = float(rng.lognormal(mean=math.log(median), sigma=sigma))
    return max(5, int(round(value)))


class _PatientCounter:
    def __init__(self) -> None:
        self._n = 0

    def next_ref(self) -> str:
        self._n += 1
        return f"P-{self._n:05d}"


def _fill_block(
    rng: np.random.Generator,
    config: SimConfig,
    day: date,
    room_code: str,
    surgeon: SurgeonSpec,
    procedures_by_sub: dict[str, list[ProcedureSpec]],
    emergency_procedures: list[ProcedureSpec],
    patients: _PatientCounter,
) -> list[CaseRecord]:
    """Generate the cases run in one room on one day for one surgeon."""
    block_start = _at(day, config.day_start_hour)
    block_end = _at(day, config.day_end_hour)
    choices = procedures_by_sub[surgeon.subspecialty]

    cases: list[CaseRecord] = []
    plan_clock = block_start
    actual_clock = block_start
    started = False

    while plan_clock < block_end:
        proc = choices[int(rng.integers(0, len(choices)))]
        estimate = max(5, int(round(proc.median_minutes * surgeon.estimate_bias)))
        scheduled_start = plan_clock
        scheduled_end = plan_clock + timedelta(minutes=estimate)

        true_median = proc.median_minutes * surgeon.speed_factor
        actual_minutes = _lognormal_minutes(rng, true_median, proc.log_sigma)

        outcome = float(rng.random())
        actual_start: datetime | None
        actual_end: datetime | None
        if outcome < config.cancellation_prob:
            status, actual_start, actual_end = CASE_CANCELLED, None, None
        elif outcome < config.cancellation_prob + config.no_show_prob:
            status, actual_start, actual_end = CASE_NO_SHOW, None, None
        else:
            status = CASE_COMPLETED
            if not started:
                delay = 0.0
                if float(rng.random()) < config.late_start_prob:
                    delay = float(rng.exponential(config.late_start_mean_minutes))
                actual_start = block_start + timedelta(minutes=delay)
                started = True
            else:
                turnover = float(
                    rng.lognormal(
                        mean=math.log(config.turnover_mean_minutes),
                        sigma=config.turnover_log_sigma,
                    )
                )
                actual_start = actual_clock + timedelta(minutes=turnover)
            actual_end = actual_start + timedelta(minutes=actual_minutes)
            actual_clock = actual_end

        cases.append(
            CaseRecord(
                patient_ref=patients.next_ref(),
                procedure_code=proc.code,
                surgeon_code=surgeon.code,
                room_code=room_code,
                service_date=day,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                actual_start=actual_start,
                actual_end=actual_end,
                surgeon_estimate_minutes=estimate,
                status=status,
                is_emergency=False,
            )
        )
        plan_clock = scheduled_end + timedelta(minutes=config.turnover_mean_minutes)

    if float(rng.random()) < config.emergency_prob_per_room_day:
        cases.append(
            _emergency_case(
                rng, config, day, room_code, surgeon, emergency_procedures, actual_clock, patients
            )
        )
    return cases


def _emergency_case(
    rng: np.random.Generator,
    config: SimConfig,
    day: date,
    room_code: str,
    surgeon: SurgeonSpec,
    emergency_procedures: list[ProcedureSpec],
    actual_clock: datetime,
    patients: _PatientCounter,
) -> CaseRecord:
    """An unplanned add-on case appended after the day's elective list."""
    proc = emergency_procedures[int(rng.integers(0, len(emergency_procedures)))]
    actual_minutes = _lognormal_minutes(
        rng, proc.median_minutes * surgeon.speed_factor, proc.log_sigma
    )
    actual_start = max(actual_clock, _at(day, config.day_start_hour))
    actual_end = actual_start + timedelta(minutes=actual_minutes)
    return CaseRecord(
        patient_ref=patients.next_ref(),
        procedure_code=proc.code,
        surgeon_code=surgeon.code,
        room_code=room_code,
        service_date=day,
        # Not scheduled in advance: planned times are unknown.
        scheduled_start=None,
        scheduled_end=None,
        actual_start=actual_start,
        actual_end=actual_end,
        surgeon_estimate_minutes=proc.median_minutes,
        status=CASE_COMPLETED,
        is_emergency=True,
    )


def generate_dataset(config: SimConfig | None = None) -> SyntheticDataset:
    """Generate a complete, reproducible synthetic dataset."""
    config = config or SimConfig()
    rng = np.random.default_rng(config.seed)
    patients = _PatientCounter()

    procedures_by_sub: dict[str, list[ProcedureSpec]] = {}
    emergency_procedures: list[ProcedureSpec] = []
    for proc in config.procedures:
        if proc.is_emergency:
            emergency_procedures.append(proc)
        else:
            procedures_by_sub.setdefault(proc.subspecialty, []).append(proc)

    cases: list[CaseRecord] = []
    block_times: list[BlockTimeRecord] = []
    surgeons = config.surgeons
    n_surgeons = len(surgeons)

    for day_index, day in enumerate(_weekdays(config)):
        for room_index, room_code in enumerate(config.rooms):
            surgeon = surgeons[(day_index + room_index) % n_surgeons]
            block_start = _at(day, config.day_start_hour)
            block_end = _at(day, config.day_end_hour)

            roll = float(rng.random())
            if roll < config.unused_block_prob:
                block_times.append(
                    BlockTimeRecord(
                        room_code, surgeon.code, None, day, block_start, block_end, BLOCK_UNUSED
                    )
                )
                continue
            if roll < config.unused_block_prob + config.released_block_prob:
                block_times.append(
                    BlockTimeRecord(
                        room_code, surgeon.code, None, day, block_start, block_end, BLOCK_RELEASED
                    )
                )
                continue

            day_cases = _fill_block(
                rng,
                config,
                day,
                room_code,
                surgeon,
                procedures_by_sub,
                emergency_procedures,
                patients,
            )
            cases.extend(day_cases)
            status = BLOCK_USED if day_cases else BLOCK_UNUSED
            block_times.append(
                BlockTimeRecord(
                    room_code, surgeon.code, None, day, block_start, block_end, status
                )
            )

    return SyntheticDataset(
        hospital=HospitalRecord(config.hospital_name),
        rooms=[
            RoomRecord(code, f"Operating Room {i + 1}")
            for i, code in enumerate(config.rooms)
        ],
        surgeons=[SurgeonRecord(s.code, "orthopedics") for s in surgeons],
        staff=list(config.staff),
        procedures=[
            ProcedureRecord(p.code, p.name, p.subspecialty, p.median_minutes)
            for p in config.procedures
        ],
        cases=cases,
        block_times=block_times,
    )
