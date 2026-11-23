"""Status string constants.

These mirror the backend's enum *values* (see backend/app/models/enums.py).
The generator emits strings so the CSV import can map them to real enums.
"""

from typing import Final

# Case status
CASE_SCHEDULED: Final = "scheduled"
CASE_COMPLETED: Final = "completed"
CASE_CANCELLED: Final = "cancelled"
CASE_NO_SHOW: Final = "no_show"

# Block status
BLOCK_USED: Final = "used"
BLOCK_RELEASED: Final = "released"
BLOCK_UNUSED: Final = "unused"

# Staff roles
ROLE_NURSE: Final = "nurse"
ROLE_ANESTHESIOLOGIST: Final = "anesthesiologist"
ROLE_SCRUB_TECH: Final = "scrub_tech"
ROLE_CIRCULATOR: Final = "circulator"
