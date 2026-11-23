"""Session-level orchestration for training and evaluating the predictor."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import AuditEvent, AuditSource, Case
from app.schemas.predictions import AccuracyResponse, ProcedureAccuracyRow
from app.services.predictor import TrainingResult, train_predictor, write_predictions


def _load_cases(session: Session) -> list[Case]:
    stmt = select(Case).options(
        joinedload(Case.procedure), joinedload(Case.surgeon)
    )
    return list(session.scalars(stmt).all())


def train_and_apply(
    session: Session, actor: str, model_path: str | None = None
) -> TrainingResult:
    """Train on DB cases, write median predictions back, audit, and commit."""
    cases = _load_cases(session)
    predictor, result = train_predictor(cases)
    updated = write_predictions(cases, predictor)

    if model_path:
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)
        predictor.save(model_path)

    session.add(
        AuditEvent(
            actor=actor,
            action="predictions.train",
            entity_type="case",
            before=None,
            after={
                "updated": updated,
                "model_mae": result.model_mae,
                "surgeon_mae": result.surgeon_mae,
                "improvement_pct": result.improvement_pct,
            },
            source=AuditSource.SYSTEM,
        )
    )
    session.commit()
    return result


class AccuracyRow:
    """Per-procedure accuracy comparison (plain container)."""

    def __init__(self, code: str, name: str) -> None:
        self.code = code
        self.name = name
        self.cases = 0
        self.surgeon_abs = 0.0
        self.model_abs = 0.0


def prediction_accuracy(session: Session) -> AccuracyResponse:
    """Compare written predictions and surgeon estimates against actuals."""
    cases = _load_cases(session)
    rows: dict[str, AccuracyRow] = {}
    total_cases = 0
    total_surgeon = 0.0
    total_model = 0.0

    for case in cases:
        if (
            case.actual_start is None
            or case.actual_end is None
            or case.predicted_duration_minutes is None
            or case.surgeon_estimate_minutes is None
        ):
            continue
        actual = (case.actual_end - case.actual_start).total_seconds() / 60.0
        if actual <= 0:
            continue
        surgeon_abs = abs(case.surgeon_estimate_minutes - actual)
        model_abs = abs(case.predicted_duration_minutes - actual)

        row = rows.setdefault(
            case.procedure.code, AccuracyRow(case.procedure.code, case.procedure.name)
        )
        row.cases += 1
        row.surgeon_abs += surgeon_abs
        row.model_abs += model_abs

        total_cases += 1
        total_surgeon += surgeon_abs
        total_model += model_abs

    def mae(total: float, n: int) -> float:
        return round(total / n, 2) if n else 0.0

    per_procedure = [
        ProcedureAccuracyRow(
            procedure_code=row.code,
            procedure_name=row.name,
            cases=row.cases,
            surgeon_mae=mae(row.surgeon_abs, row.cases),
            model_mae=mae(row.model_abs, row.cases),
        )
        for row in sorted(rows.values(), key=lambda r: r.code)
    ]

    surgeon_mae = mae(total_surgeon, total_cases)
    model_mae = mae(total_model, total_cases)
    improvement = (
        round(100.0 * (surgeon_mae - model_mae) / surgeon_mae, 2) if surgeon_mae else 0.0
    )

    return AccuracyResponse(
        cases_scored=total_cases,
        surgeon_mae=surgeon_mae,
        model_mae=model_mae,
        improvement_pct=improvement,
        per_procedure=per_procedure,
    )
