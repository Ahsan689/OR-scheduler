"""BlockTime model: reserved OR time for a surgeon or service."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import BlockStatus

if TYPE_CHECKING:
    from app.models.hospital import Hospital
    from app.models.room import Room
    from app.models.surgeon import Surgeon


class BlockTime(Base, TimestampMixin):
    """A reserved window of OR time, owned by a surgeon or a service line.

    Exactly one of ``surgeon_id`` or ``service`` identifies the owner.
    """

    __tablename__ = "block_time"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospital.id"), nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("room.id"), nullable=False)

    surgeon_id: Mapped[int | None] = mapped_column(ForeignKey("surgeon.id"), default=None)
    service: Mapped[str | None] = mapped_column(default=None)

    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[BlockStatus] = mapped_column(
        Enum(BlockStatus), default=BlockStatus.SCHEDULED, nullable=False
    )

    hospital: Mapped[Hospital] = relationship(back_populates="block_times")
    room: Mapped[Room] = relationship(back_populates="block_times")
    surgeon: Mapped[Surgeon | None] = relationship(back_populates="block_times")
