"""Schemas for the duration predictor endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class PredictionExample(BaseModel):
    procedure_code: str
    surgeon_estimate_minutes: int | None
    actual_minutes: int
    predicted_minutes: int
    lower_minutes: int
    upper_minutes: int


class TrainResponse(BaseModel):
    """Result of training on a held-out future time slice."""

    n_train: int
    n_test: int
    surgeon_mae: float
    model_mae: float
    improvement_pct: float
    within_range_pct: float
    examples: list[PredictionExample]


class ProcedureAccuracyRow(BaseModel):
    procedure_code: str
    procedure_name: str
    cases: int
    surgeon_mae: float
    model_mae: float


class AccuracyResponse(BaseModel):
    """Model vs surgeon-estimate accuracy over all scored cases."""

    cases_scored: int
    surgeon_mae: float
    model_mae: float
    improvement_pct: float
    per_procedure: list[ProcedureAccuracyRow]
