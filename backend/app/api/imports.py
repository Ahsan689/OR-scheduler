"""Import endpoint: upload a CSV/XLSX table for one entity kind."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Principal, Role, require_roles
from app.schemas.imports import ImportKind, ImportResult
from app.services.importer import ImportDataError, import_table, parse_table

router = APIRouter(prefix="/import", tags=["import"])

# 20 MB cap on uploaded files.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.post("", response_model=ImportResult)
def import_file(
    kind: Annotated[ImportKind, Form()],
    file: Annotated[UploadFile, File()],
    principal: Annotated[Principal, Depends(require_roles(Role.COORDINATOR, Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> ImportResult:
    """Validate and import one uploaded table. Coordinator/admin only."""
    content = file.file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded file is too large",
        )

    filename = file.filename or ""
    try:
        rows = parse_table(content, filename)
        return import_table(db, kind, rows, actor=principal.actor)
    except ImportDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
