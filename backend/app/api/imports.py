from collections.abc import Callable
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ingestion.pipeline import import_files
from app.ingestion.undo import undo_import
from app.repo import imports as repo
from app.repo.backup import backup_with_settings
from app.repo.db import get_session

router = APIRouter(tags=["imports"])


class RowErrorDTO(BaseModel):
    line_no: int
    reason: str


class ImportResultDTO(BaseModel):
    filename: str
    status: Literal["importado", "ja_importado", "rejeitado", "erro"]
    batch_id: int | None
    rows_new: int
    rows_duplicate: int
    rows_error: int
    errors: list[RowErrorDTO]
    message: str | None
    account_id: int | None
    account_name: str | None
    needs_holder: bool


class ImportBatchDTO(BaseModel):
    id: int
    filename: str
    imported_at: datetime
    account_id: int
    account_name: str
    holder: str | None
    rows_total: int
    rows_new: int
    rows_duplicate: int
    rows_error: int


def get_backup() -> Callable[[datetime], object]:
    """Backup antes de importar; os testes substituem para não tocar no banco do usuário."""
    return backup_with_settings


@router.post("/imports")
def post_imports(
    files: list[UploadFile],
    session: Session = Depends(get_session),
    backup: Callable[[datetime], object] = Depends(get_backup),
) -> list[ImportResultDTO]:
    contents = [(f.filename or "arquivo", f.file.read()) for f in files]
    now = datetime.now()
    results = import_files(session, contents, now, lambda: backup(now))
    return [
        ImportResultDTO(
            **{k: getattr(r, k) for k in ImportResultDTO.model_fields if k != "errors"},
            errors=[RowErrorDTO(line_no=e.line_no, reason=e.reason) for e in r.errors],
        )
        for r in results
    ]


@router.get("/imports")
def get_imports(session: Session = Depends(get_session)) -> list[ImportBatchDTO]:
    return [
        ImportBatchDTO(
            id=batch.id,
            filename=batch.filename,
            imported_at=batch.imported_at,
            account_id=account.id,
            account_name=account.name,
            holder=account.holder,
            rows_total=batch.rows_total,
            rows_new=batch.rows_new,
            rows_duplicate=batch.rows_duplicate,
            rows_error=batch.rows_error,
        )
        for batch, account in repo.list_batches(session)
    ]


@router.delete("/imports/{batch_id}", status_code=204)
def delete_import(batch_id: int, session: Session = Depends(get_session)) -> Response:
    if not undo_import(session, batch_id):
        raise HTTPException(status_code=404, detail="Importação não encontrada")
    return Response(status_code=204)
