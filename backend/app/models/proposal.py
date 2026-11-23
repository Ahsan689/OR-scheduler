"""Proposal model: an optimizer-suggested schedule change awaiting approval."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ProposalStatus

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.room import Room


class Proposal(Base, TimestampMixin):
    """A proposed change to a case's room/time.

    The system proposes; a human approves. A proposal is applied to the case
    only after it is accepted (handled in the scheduler build step).
    """

    __tablename__ = "proposal"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("case.id"), nullable=False)

    proposed_room_id: Mapped[int | None] = mapped_column(ForeignKey("room.id"), default=None)
    proposed_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    proposed_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    status: Mapped[ProposalStatus] = mapped_column(
        Enum(ProposalStatus), default=ProposalStatus.PENDING, nullable=False
    )
    rationale: Mapped[str | None] = mapped_column(default=None)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    resolved_by: Mapped[str | None] = mapped_column(default=None)

    case: Mapped[Case] = relationship(back_populates="proposals")
    proposed_room: Mapped[Room | None] = relationship()
