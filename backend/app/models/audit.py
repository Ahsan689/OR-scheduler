"""AuditEvent model: an immutable record of every case/schedule change."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import AuditSource


class AuditEvent(Base):
    """A single audit record. Append-only; rows are never updated in place."""

    __tablename__ = "audit_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(nullable=False)
    entity_type: Mapped[str] = mapped_column(nullable=False)
    entity_id: Mapped[int | None] = mapped_column(default=None)

    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)

    source: Mapped[AuditSource] = mapped_column(Enum(AuditSource), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
