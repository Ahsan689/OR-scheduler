"""Enumerations used across the domain models."""

import enum


class CaseStatus(str, enum.Enum):
    """Lifecycle of a surgical case."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class BlockStatus(str, enum.Enum):
    """State of a surgeon/service block of OR time."""

    SCHEDULED = "scheduled"
    USED = "used"
    RELEASED = "released"
    UNUSED = "unused"


class ProposalStatus(str, enum.Enum):
    """Review state of an optimizer-proposed schedule change."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class StaffRole(str, enum.Enum):
    """Role of a non-surgeon staff member."""

    NURSE = "nurse"
    ANESTHESIOLOGIST = "anesthesiologist"
    SCRUB_TECH = "scrub_tech"
    CIRCULATOR = "circulator"


class AuditSource(str, enum.Enum):
    """Origin of a change recorded in the audit log."""

    IMPORT = "import"
    OPTIMIZER = "optimizer"
    API = "api"
    SYSTEM = "system"
