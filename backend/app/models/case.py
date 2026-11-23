"""Case model: a single scheduled surgical case."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import CaseStatus

if TYPE_CHECKING:
    from app.models.hospital import Hospital
    from app.models.procedure import Procedure
    from app.models.proposal import Proposal
    from app.models.room import Room
    from app.models.surgeon import Surgeon


class Case(Base, TimestampMixin):
    """A surgical case. Patients are referenced only by pseudonymous IDs."""

    __tablename__ = "case"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospital.id"), nullable=False)

    # Pseudonymous patient reference only, e.g. "P-00123". Never a real identity.
    patient_ref: Mapped[str] = mapped_column(nullable=False)

    procedure_id: Mapped[int] = mapped_column(ForeignKey("procedure.id"), nullable=False)
    surgeon_id: Mapped[int] = mapped_column(ForeignKey("surgeon.id"), nullable=False)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("room.id"), default=None)

    service_date: Mapped[date] = mapped_column(Date, nullable=False)

    scheduled_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    scheduled_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    actual_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    actual_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    # The surgeon's own estimate (often optimistic) vs. the model's prediction.
    surgeon_estimate_minutes: Mapped[int | None] = mapped_column(default=None)
    predicted_duration_minutes: Mapped[int | None] = mapped_column(default=None)

    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus), default=CaseStatus.SCHEDULED, nullable=False
    )

    hospital: Mapped[Hospital] = relationship(back_populates="cases")
    procedure: Mapped[Procedure] = relationship(back_populates="cases")
    surgeon: Mapped[Surgeon] = relationship(back_populates="cases")
    room: Mapped[Room | None] = relationship(back_populates="cases")
    proposals: Mapped[list[Proposal]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
