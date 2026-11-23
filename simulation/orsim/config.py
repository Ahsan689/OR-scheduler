"""Simulation configuration: parameters and the default orthopedic catalog."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from orsim.enums import (
    ROLE_ANESTHESIOLOGIST,
    ROLE_CIRCULATOR,
    ROLE_NURSE,
    ROLE_SCRUB_TECH,
)
from orsim.records import StaffRecord


@dataclass(frozen=True)
class SurgeonSpec:
    """A surgeon's identity and behavioural parameters."""

    code: str
    subspecialty: str
    # Multiplier on a procedure's median duration. <1 = faster than typical.
    speed_factor: float
    # Multiplier the surgeon applies to the median when giving their own
    # estimate. <1 = optimistic (estimates shorter than reality).
    estimate_bias: float


@dataclass(frozen=True)
class ProcedureSpec:
    """A procedure type and its (log-normal) duration distribution."""

    code: str
    name: str
    subspecialty: str
    median_minutes: int
    log_sigma: float
    is_emergency: bool = False


DEFAULT_SURGEONS: tuple[SurgeonSpec, ...] = (
    SurgeonSpec("SUR-001", "joints", speed_factor=0.95, estimate_bias=0.90),
    SurgeonSpec("SUR-002", "joints", speed_factor=1.10, estimate_bias=0.85),
    SurgeonSpec("SUR-003", "sports", speed_factor=0.90, estimate_bias=0.92),
    SurgeonSpec("SUR-004", "spine", speed_factor=1.15, estimate_bias=0.80),
    SurgeonSpec("SUR-005", "trauma", speed_factor=1.00, estimate_bias=0.88),
    SurgeonSpec("SUR-006", "foot_ankle", speed_factor=0.92, estimate_bias=0.90),
)

DEFAULT_PROCEDURES: tuple[ProcedureSpec, ...] = (
    # joints
    ProcedureSpec("TKA", "Total Knee Arthroplasty", "joints", 90, 0.28),
    ProcedureSpec("THA", "Total Hip Arthroplasty", "joints", 100, 0.30),
    ProcedureSpec("UKA", "Unicompartmental Knee Arthroplasty", "joints", 75, 0.28),
    # sports
    ProcedureSpec("ACLR", "ACL Reconstruction", "sports", 75, 0.30),
    ProcedureSpec("RCR", "Rotator Cuff Repair", "sports", 70, 0.30),
    ProcedureSpec("KNEE_SCOPE", "Knee Arthroscopy", "sports", 45, 0.35),
    ProcedureSpec("SHLD_SCOPE", "Shoulder Arthroscopy", "sports", 55, 0.33),
    # spine
    ProcedureSpec("LAMI", "Laminectomy", "spine", 120, 0.30),
    ProcedureSpec("MICRODISC", "Microdiscectomy", "spine", 95, 0.30),
    ProcedureSpec("FUSION", "Spinal Fusion", "spine", 180, 0.28),
    # trauma (elective)
    ProcedureSpec("TIBIA_ORIF", "Tibia ORIF", "trauma", 90, 0.33),
    ProcedureSpec("WRIST_ORIF", "Wrist ORIF", "trauma", 70, 0.33),
    # foot & ankle
    ProcedureSpec("ANKLE_ORIF", "Ankle ORIF", "foot_ankle", 80, 0.30),
    ProcedureSpec("BUNION", "Bunionectomy", "foot_ankle", 60, 0.32),
    ProcedureSpec("HW_REMOVAL", "Hardware Removal", "foot_ankle", 40, 0.35),
    # emergency add-ons (not scheduled in advance)
    ProcedureSpec("HIP_FX_ORIF", "Hip Fracture ORIF", "trauma", 95, 0.33, is_emergency=True),
    ProcedureSpec("TRAUMA_ORIF", "Trauma ORIF", "trauma", 85, 0.35, is_emergency=True),
)


def _default_staff() -> list[StaffRecord]:
    staff: list[StaffRecord] = []
    counter = 1

    def add(role: str, n: int) -> None:
        nonlocal counter
        for _ in range(n):
            staff.append(StaffRecord(code=f"S-{counter:03d}", role=role))
            counter += 1

    add(ROLE_NURSE, 8)
    add(ROLE_ANESTHESIOLOGIST, 4)
    add(ROLE_SCRUB_TECH, 4)
    add(ROLE_CIRCULATOR, 4)
    return staff


@dataclass(frozen=True)
class SimConfig:
    """All knobs for a simulation run. Deterministic given ``seed``."""

    seed: int = 42
    start_date: date = date(2025, 1, 1)
    months: int = 12

    rooms: tuple[str, ...] = ("OR-1", "OR-2", "OR-3", "OR-4")
    day_start_hour: int = 8
    day_end_hour: int = 16

    turnover_mean_minutes: float = 25.0
    turnover_log_sigma: float = 0.30

    late_start_prob: float = 0.30
    late_start_mean_minutes: float = 12.0

    cancellation_prob: float = 0.06
    no_show_prob: float = 0.01
    emergency_prob_per_room_day: float = 0.12

    unused_block_prob: float = 0.08
    released_block_prob: float = 0.05

    hospital_name: str = "Demo General Hospital"

    surgeons: tuple[SurgeonSpec, ...] = DEFAULT_SURGEONS
    procedures: tuple[ProcedureSpec, ...] = DEFAULT_PROCEDURES
    staff: list[StaffRecord] = field(default_factory=_default_staff)
