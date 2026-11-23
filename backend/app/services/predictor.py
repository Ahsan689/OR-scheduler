"""Case-duration predictor.

A quantile model (scikit-learn ``HistGradientBoostingRegressor`` at the 10th,
50th and 90th percentiles) predicts a case's duration and a confidence range,
learning the per-surgeon, per-procedure signal that the surgeon's own estimate
misses. The median prediction is written back to each case; the headline metric
is model MAE versus surgeon-estimate MAE on a held-out, future time slice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

import joblib
import numpy as np
import numpy.typing as npt
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from app.models import Case

QUANTILES = (0.1, 0.5, 0.9)
FloatArray = npt.NDArray[np.float64]


@dataclass
class Vocab:
    """Stable integer encodings for categorical features."""

    procedures: dict[str, int] = field(default_factory=dict)
    surgeons: dict[str, int] = field(default_factory=dict)

    @classmethod
    def build(cls, cases: list[Case]) -> Vocab:
        procedures: dict[str, int] = {}
        surgeons: dict[str, int] = {}
        for case in cases:
            procedures.setdefault(case.procedure.code, len(procedures))
            surgeons.setdefault(case.surgeon.code, len(surgeons))
        return cls(procedures=procedures, surgeons=surgeons)


def _duration_minutes(case: Case) -> float | None:
    if case.actual_start is None or case.actual_end is None:
        return None
    start: datetime = case.actual_start
    end: datetime = case.actual_end
    minutes = (end - start).total_seconds() / 60.0
    return minutes if minutes > 0 else None


def _feature_row(case: Case, vocab: Vocab) -> list[float]:
    proc = [0.0] * len(vocab.procedures)
    surg = [0.0] * len(vocab.surgeons)
    pi = vocab.procedures.get(case.procedure.code)
    si = vocab.surgeons.get(case.surgeon.code)
    if pi is not None:
        proc[pi] = 1.0
    if si is not None:
        surg[si] = 1.0
    weekday = float(case.service_date.weekday())
    start_hour = float(case.scheduled_start.hour) if case.scheduled_start else -1.0
    estimate = float(case.surgeon_estimate_minutes or -1)
    return [*proc, *surg, weekday, start_hour, estimate]


def build_matrix(cases: list[Case], vocab: Vocab) -> FloatArray:
    if not cases:
        width = len(vocab.procedures) + len(vocab.surgeons) + 3
        return np.empty((0, width), dtype=np.float64)
    return np.array([_feature_row(c, vocab) for c in cases], dtype=np.float64)


class DurationPredictor:
    """Wraps three quantile regressors and the feature vocabulary."""

    def __init__(self, vocab: Vocab, models: dict[float, HistGradientBoostingRegressor]):
        self.vocab = vocab
        self.models = models

    @classmethod
    def fit(cls, cases: list[Case]) -> DurationPredictor:
        vocab = Vocab.build(cases)
        x = build_matrix(cases, vocab)
        y = np.array([_duration_minutes(c) for c in cases], dtype=np.float64)
        models: dict[float, HistGradientBoostingRegressor] = {}
        for q in QUANTILES:
            model = HistGradientBoostingRegressor(
                loss="quantile",
                quantile=q,
                max_iter=200,
                learning_rate=0.05,
                max_depth=4,
                random_state=42,
            )
            model.fit(x, y)
            models[q] = model
        return cls(vocab=vocab, models=models)

    def predict(self, cases: list[Case]) -> tuple[FloatArray, FloatArray, FloatArray]:
        """Return (lower, median, upper) predicted minutes, per case."""
        x = build_matrix(cases, self.vocab)
        if x.shape[0] == 0:
            empty = np.empty((0,), dtype=np.float64)
            return empty, empty, empty
        stacked = np.vstack([self.models[q].predict(x) for q in QUANTILES])
        # Enforce non-crossing quantiles row-wise (lower <= median <= upper).
        ordered = np.sort(stacked, axis=0)
        return ordered[0], ordered[1], ordered[2]

    def save(self, path: str) -> None:
        joblib.dump({"vocab": self.vocab, "models": self.models}, path)

    @classmethod
    def load(cls, path: str) -> DurationPredictor:
        payload = joblib.load(path)
        return cls(vocab=payload["vocab"], models=payload["models"])


@dataclass
class TrainingExample:
    procedure_code: str
    surgeon_estimate_minutes: int | None
    actual_minutes: int
    predicted_minutes: int
    lower_minutes: int
    upper_minutes: int


@dataclass
class TrainingResult:
    n_train: int
    n_test: int
    surgeon_mae: float
    model_mae: float
    improvement_pct: float
    within_range_pct: float
    examples: list[TrainingExample]


def _completed_cases(cases: list[Case]) -> list[Case]:
    return [c for c in cases if _duration_minutes(c) is not None]


def train_predictor(
    cases: list[Case], test_fraction: float = 0.2
) -> tuple[DurationPredictor, TrainingResult]:
    """Fit on the earlier cases, evaluate on the most recent ``test_fraction``."""
    usable = _completed_cases(cases)
    if len(usable) < 20:
        raise ValueError("Not enough completed cases to train a predictor")

    usable.sort(key=lambda c: (c.service_date, c.id))
    split = int(len(usable) * (1 - test_fraction))
    train_cases, test_cases = usable[:split], usable[split:]

    predictor = DurationPredictor.fit(train_cases)
    lower, median, upper = predictor.predict(test_cases)

    actual = np.array([_duration_minutes(c) for c in test_cases], dtype=np.float64)
    estimate = np.array(
        [float(c.surgeon_estimate_minutes or math.nan) for c in test_cases],
        dtype=np.float64,
    )
    has_estimate = ~np.isnan(estimate)

    surgeon_mae = float(mean_absolute_error(actual[has_estimate], estimate[has_estimate]))
    model_mae = float(mean_absolute_error(actual, median))
    improvement = 100.0 * (surgeon_mae - model_mae) / surgeon_mae if surgeon_mae else 0.0
    within = float(np.mean((actual >= lower) & (actual <= upper))) * 100.0

    examples = [
        TrainingExample(
            procedure_code=case.procedure.code,
            surgeon_estimate_minutes=case.surgeon_estimate_minutes,
            actual_minutes=round(actual[i]),
            predicted_minutes=round(median[i]),
            lower_minutes=round(lower[i]),
            upper_minutes=round(upper[i]),
        )
        for i, case in enumerate(test_cases[:8])
    ]

    result = TrainingResult(
        n_train=len(train_cases),
        n_test=len(test_cases),
        surgeon_mae=round(surgeon_mae, 2),
        model_mae=round(model_mae, 2),
        improvement_pct=round(improvement, 2),
        within_range_pct=round(within, 2),
        examples=examples,
    )
    return predictor, result


def write_predictions(cases: list[Case], predictor: DurationPredictor) -> int:
    """Write the median prediction to each case; returns how many were updated."""
    _, median, _ = predictor.predict(cases)
    for case, value in zip(cases, median, strict=True):
        case.predicted_duration_minutes = round(value)
    return len(cases)
