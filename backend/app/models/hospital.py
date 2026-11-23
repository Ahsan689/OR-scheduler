"""Hospital model: the top-level owner of rooms, staff, and cases."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.block_time import BlockTime
    from app.models.case import Case
    from app.models.procedure import Procedure
    from app.models.room import Room
    from app.models.staff import Staff
    from app.models.surgeon import Surgeon


class Hospital(Base, TimestampMixin):
    """A hospital (single-tenant for this project, but modeled explicitly)."""

    __tablename__ = "hospital"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)

    rooms: Mapped[list[Room]] = relationship(
        back_populates="hospital", cascade="all, delete-orphan"
    )
    surgeons: Mapped[list[Surgeon]] = relationship(
        back_populates="hospital", cascade="all, delete-orphan"
    )
    staff: Mapped[list[Staff]] = relationship(
        back_populates="hospital", cascade="all, delete-orphan"
    )
    procedures: Mapped[list[Procedure]] = relationship(
        back_populates="hospital", cascade="all, delete-orphan"
    )
    cases: Mapped[list[Case]] = relationship(
        back_populates="hospital", cascade="all, delete-orphan"
    )
    block_times: Mapped[list[BlockTime]] = relationship(
        back_populates="hospital", cascade="all, delete-orphan"
    )
