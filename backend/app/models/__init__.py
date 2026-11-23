"""ORM models.

Importing this package registers every model on ``Base.metadata`` so that
Alembic autogeneration and ``create_all`` see the full schema.
"""

from app.models.audit import AuditEvent
from app.models.base import Base
from app.models.block_time import BlockTime
from app.models.case import Case
from app.models.enums import (
    AuditSource,
    BlockStatus,
    CaseStatus,
    ProposalStatus,
    StaffRole,
)
from app.models.hospital import Hospital
from app.models.procedure import Procedure
from app.models.proposal import Proposal
from app.models.room import Room
from app.models.staff import Staff
from app.models.surgeon import Surgeon

__all__ = [
    "AuditEvent",
    "AuditSource",
    "Base",
    "BlockStatus",
    "BlockTime",
    "Case",
    "CaseStatus",
    "Hospital",
    "Procedure",
    "Proposal",
    "ProposalStatus",
    "Room",
    "Staff",
    "StaffRole",
    "Surgeon",
]
