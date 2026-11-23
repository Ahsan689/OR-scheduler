"""Dashboard metrics endpoint."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Principal, get_principal
from app.schemas.metrics import DashboardResponse
from app.services.metrics import compute_dashboard

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_principal)],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> DashboardResponse:
    """Utilization KPIs, per-room and daily breakdowns, and estimate accuracy.

    Any authenticated role may read the dashboard.
    """
    return compute_dashboard(db, date_from=date_from, date_to=date_to)
