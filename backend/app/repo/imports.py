"""Consultas usadas pelo estágio `persist` da importação."""

from collections.abc import Collection

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.repo.models import Account, ImportBatch, Transaction, TransactionSource


def get_or_create_account(
    session: Session, bank: str, kind: str, external_account_id: str, name: str
) -> Account:
    account = session.scalar(
        select(Account).where(
            Account.bank == bank,
            Account.kind == kind,
            Account.external_account_id == external_account_id,
        )
    )
    if account is None:
        account = Account(bank=bank, kind=kind, external_account_id=external_account_id, name=name)
        session.add(account)
        session.flush()
    return account


def find_batch_id(session: Session, file_sha256: str) -> int | None:
    return session.scalar(select(ImportBatch.id).where(ImportBatch.file_sha256 == file_sha256))


def get_batch_account(session: Session, batch_id: int) -> Account:
    return session.execute(
        select(Account)
        .join(ImportBatch, ImportBatch.account_id == Account.id)
        .where(ImportBatch.id == batch_id)
    ).scalar_one()


def list_batches(session: Session) -> list[tuple[ImportBatch, Account]]:
    rows = session.execute(
        select(ImportBatch, Account)
        .join(Account, ImportBatch.account_id == Account.id)
        .order_by(ImportBatch.imported_at.desc(), ImportBatch.id.desc())
    )
    return [(batch, account) for batch, account in rows]


def get_batch(session: Session, batch_id: int) -> ImportBatch | None:
    return session.get(ImportBatch, batch_id)


def delete_batch(session: Session, batch: ImportBatch) -> None:
    """Remove as transações reais cuja única origem é o lote, depois o lote (uma transação).

    A regra usa `transaction_source`, não `Transaction.import_batch_id`, que só informa quem criou.
    As origens restantes caem por CASCADE ao apagar o lote.
    """
    other_source = (
        select(TransactionSource.transaction_id)
        .where(
            TransactionSource.transaction_id == Transaction.id,
            TransactionSource.import_batch_id != batch.id,
        )
        .exists()
    )
    own_source = (
        select(TransactionSource.transaction_id)
        .where(
            TransactionSource.transaction_id == Transaction.id,
            TransactionSource.import_batch_id == batch.id,
        )
        .exists()
    )
    session.execute(
        delete(Transaction)
        .where(Transaction.status == "real", own_source, ~other_source)
        .execution_options(synchronize_session=False)
    )
    session.execute(
        delete(ImportBatch)
        .where(ImportBatch.id == batch.id)
        .execution_options(synchronize_session=False)
    )
    session.expire_all()


def set_holder(session: Session, account_id: int, holder: str) -> Account | None:
    account = session.get(Account, account_id)
    if account is not None:
        account.holder = holder
        session.flush()
    return account


def rebuild_projected(session: Session, account_ids: Collection[int]) -> None:
    """Ponto de extensão: as projetadas (R10) são reconstruídas aqui na Fase 4.1."""


def existing_ids_by_dedup_key(session: Session, keys: Collection[str]) -> dict[str, int]:
    if not keys:
        return {}
    rows = session.execute(
        select(Transaction.dedup_key, Transaction.id).where(Transaction.dedup_key.in_(keys))
    )
    return {key: transaction_id for key, transaction_id in rows}
