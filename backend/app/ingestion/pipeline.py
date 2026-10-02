"""Importação de arquivos (spec §7.2): `prepare` (puro) e depois `persist` (borda).

`persist` grava conta, lote, transações novas e as origens de todas as linhas, inclusive das
duplicatas, em uma transação SQL por arquivo.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, fields
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ingestion.prepare import PreparedFile, PreparedTransaction, prepare
from app.ingestion.types import RejectedFile, RowError
from app.repo import imports as repo
from app.repo.models import ImportBatch, Transaction, TransactionSource


@dataclass(frozen=True)
class ImportResult:
    filename: str
    status: str  # 'importado' | 'ja_importado' | 'rejeitado' | 'erro'
    batch_id: int | None = None
    rows_new: int = 0
    rows_duplicate: int = 0
    rows_error: int = 0
    errors: list[RowError] = field(default_factory=list)
    message: str | None = None


def import_files(
    session: Session,
    files: Sequence[tuple[str, bytes]],
    now: datetime,
    backup: Callable[[], object],
) -> list[ImportResult]:
    """Um backup do banco antes de importar (spec §7.5), depois cada arquivo isoladamente."""
    backup()
    return [import_file(session, filename, content, now) for filename, content in files]


def import_file(session: Session, filename: str, content: bytes, now: datetime) -> ImportResult:
    """Atômica por arquivo: rejeitado ou com erro, nada dele fica gravado."""
    try:
        prepared = prepare(filename, content)
    except RejectedFile as error:
        return ImportResult(filename, "rejeitado", message=str(error))
    try:
        return persist(session, prepared, now)
    except SQLAlchemyError as error:
        session.rollback()
        return ImportResult(filename, "erro", message=str(getattr(error, "orig", None) or error))


def persist(session: Session, prepared: PreparedFile, now: datetime) -> ImportResult:
    """Grava o arquivo preparado e faz commit; em caso de erro, quem chama faz rollback."""
    existing_batch = repo.find_batch_id(session, prepared.file_sha256)
    if existing_batch is not None:
        return ImportResult(
            prepared.filename,
            "ja_importado",
            batch_id=existing_batch,
            message="arquivo já importado",
        )

    info = prepared.account
    account = repo.get_or_create_account(
        session, info.bank, info.kind, info.external_account_id, info.default_name
    )
    batch = ImportBatch(
        account_id=account.id,
        filename=prepared.filename,
        file_sha256=prepared.file_sha256,
        imported_at=now,
        rows_total=len(prepared.transactions) + len(prepared.errors),
        rows_new=0,
        rows_duplicate=0,
        rows_error=len(prepared.errors),
    )
    session.add(batch)
    session.flush()

    ids = repo.existing_ids_by_dedup_key(session, [t.dedup_key for t in prepared.transactions])
    sourced: set[int] = set()
    for item in prepared.transactions:
        transaction_id = ids.get(item.dedup_key)
        if transaction_id is None:
            transaction = Transaction(
                **_columns(item),
                account_id=account.id,
                import_batch_id=batch.id,
                status="real",
                created_at=now,
            )
            session.add(transaction)
            session.flush()
            transaction_id = ids[item.dedup_key] = transaction.id
            batch.rows_new += 1
        else:
            batch.rows_duplicate += 1  # nunca altera a existente: revisadas ficam intactas
        if transaction_id not in sourced:
            session.add(TransactionSource(transaction_id=transaction_id, import_batch_id=batch.id))
            sourced.add(transaction_id)

    session.commit()
    return ImportResult(
        prepared.filename,
        "importado",
        batch_id=batch.id,
        rows_new=batch.rows_new,
        rows_duplicate=batch.rows_duplicate,
        rows_error=batch.rows_error,
        errors=prepared.errors,
    )


def _columns(item: PreparedTransaction) -> dict:
    return {f.name: getattr(item, f.name) for f in fields(item)}
