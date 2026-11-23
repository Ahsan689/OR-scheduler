"""Procedure model: a catalog of surgical procedure types."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.hospital import Hospital


class Procedure(Base, TimestampMixin):
    """A type of procedure (e.g. total knee arthroplasty)."""

    __tablename__ = "procedure"
    __table_args__ = (
        UniqueConstraint("hospital_id", "code", name="uq_procedure_hospital_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospital.id"), nullable=False)
    code: Mapped[str] = mapped_column(nullable=False)  # e.g. "TKA"
    name: Mapped[str] = mapped_column(nullable=False)
    specialty: Mapped[str] = mapped_column(nullable=False)
    # Baseline planned duration in minutes; the predictor refines per case.
    baseline_duration_minutes: Mapped[int] = mapped_column(nullable=False)

    hospital: Mapped[Hospital] = relationship(back_populates="procedures")
    cases: Mapped[list[Case]] = relationship(back_populates="procedure")
