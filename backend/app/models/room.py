"""Room model: a physical operating room."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.block_time import BlockTime
    from app.models.case import Case
    from app.models.hospital import Hospital


class Room(Base, TimestampMixin):
    """An operating room belonging to a hospital."""

    __tablename__ = "room"
    __table_args__ = (UniqueConstraint("hospital_id", "code", name="uq_room_hospital_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospital.id"), nullable=False)
    code: Mapped[str] = mapped_column(nullable=False)  # e.g. "OR-1"
    name: Mapped[str | None] = mapped_column(default=None)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)

    hospital: Mapped[Hospital] = relationship(back_populates="rooms")
    cases: Mapped[list[Case]] = relationship(back_populates="room")
    block_times: Mapped[list[BlockTime]] = relationship(back_populates="room")
