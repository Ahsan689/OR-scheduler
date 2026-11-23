"""Request principal and role-based access.

NOTE: This is a *placeholder* for real authentication. Identity and role are
asserted via request headers (``X-Actor``, ``X-Role``); there is no credential
verification yet. It gives endpoints a role gate and an actor for the audit log
now, and is meant to be replaced by real auth in a later build step.
"""

import enum
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status


class Role(str, enum.Enum):
    COORDINATOR = "coordinator"
    SURGEON = "surgeon"
    NURSE = "nurse"
    ADMIN = "admin"


@dataclass(frozen=True)
class Principal:
    """The identity making a request (placeholder, header-derived)."""

    actor: str
    role: Role


def get_principal(
    x_actor: str = Header(default="system"),
    x_role: str = Header(...),
) -> Principal:
    """Build a Principal from request headers."""
    try:
        role = Role(x_role)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unknown role: {x_role!r}",
        ) from exc
    return Principal(actor=x_actor, role=role)


def require_roles(*allowed: Role) -> Callable[[Principal], Principal]:
    """Dependency factory: allow only principals holding one of ``allowed``."""

    def dependency(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this action",
            )
        return principal

    return dependency
