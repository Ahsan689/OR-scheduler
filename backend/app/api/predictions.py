"""Duration predictor endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import Principal, Role, get_principal, require_roles
from app.schemas.predictions import (
    AccuracyResponse,
    PredictionExample,
    TrainResponse,
)
from app.services.prediction_service import prediction_accuracy, train_and_apply

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("/train", response_model=TrainResponse)
def train(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_roles(Role.COORDINATOR, Role.ADMIN))],
) -> TrainResponse:
    """Train the duration model, write predictions back to cases, return metrics."""
    try:
        result = train_and_apply(
            db, actor=principal.actor, model_path=get_settings().model_path
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return TrainResponse(
        n_train=result.n_train,
        n_test=result.n_test,
        surgeon_mae=result.surgeon_mae,
        model_mae=result.model_mae,
        improvement_pct=result.improvement_pct,
        within_range_pct=result.within_range_pct,
        examples=[
            PredictionExample(
                procedure_code=e.procedure_code,
                surgeon_estimate_minutes=e.surgeon_estimate_minutes,
                actual_minutes=e.actual_minutes,
                predicted_minutes=e.predicted_minutes,
                lower_minutes=e.lower_minutes,
                upper_minutes=e.upper_minutes,
            )
            for e in result.examples
        ],
    )


@router.get("/accuracy", response_model=AccuracyResponse)
def accuracy(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_principal)],
) -> AccuracyResponse:
    """Compare written predictions and surgeon estimates against actual durations."""
    return prediction_accuracy(db)
