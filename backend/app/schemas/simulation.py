"""Schemas for the baseline-vs-optimized simulation."""

from __future__ import annotations

from pydantic import BaseModel


class SimMetrics(BaseModel):
    cases: int
    room_days: int
    avg_cases_per_room_day: float
    idle_minutes: int
    overtime_minutes: int
    on_time_rate: float


class SimulationResult(BaseModel):
    """Aggregate comparison across the whole dataset."""

    days: int
    cancellations: int
    baseline: SimMetrics
    optimized: SimMetrics
    idle_reduction_pct: float
    overtime_reduction_pct: float
    on_time_gain_pct_points: float
