"""Surgeon model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.block_time import BlockTime
    from app.models.case import Case
    from app.models.hospital import Hospital


class Surgeon(Base, TimestampMixin):
    """A surgeon, identified by a pseudonymous code (no personal names)."""

    __tablename__ = "surgeon"
    __table_args__ = (
        UniqueConstraint("hospital_id", "code", name="uq_surgeon_hospital_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospital.id"), nullable=False)
    code: Mapped[str] = mapped_column(nullable=False)  # e.g. "SUR-001"
    specialty: Mapped[str] = mapped_column(nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)

    hospital: Mapped[Hospital] = relationship(back_populates="surgeons")
    cases: Mapped[list[Case]] = relationship(back_populates="surgeon")
    block_times: Mapped[list[BlockTime]] = relationship(back_populates="surgeon")
