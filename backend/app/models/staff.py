"""Staff model: non-surgeon OR staff (nurses, anesthesiologists, techs)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import StaffRole

if TYPE_CHECKING:
    from app.models.hospital import Hospital


class Staff(Base, TimestampMixin):
    """A staff member, identified by a pseudonymous code (no personal names).

    Assignment of staff to specific cases is introduced with the scheduler
    (build step 7); here staff exist as a resource pool.
    """

    __tablename__ = "staff"
    __table_args__ = (UniqueConstraint("hospital_id", "code", name="uq_staff_hospital_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospital.id"), nullable=False)
    code: Mapped[str] = mapped_column(nullable=False)  # e.g. "S-001"
    role: Mapped[StaffRole] = mapped_column(Enum(StaffRole), nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)

    hospital: Mapped[Hospital] = relationship(back_populates="staff")
