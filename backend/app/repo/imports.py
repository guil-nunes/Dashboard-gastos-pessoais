"""Consultas usadas pelo estágio `persist` da importação."""

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repo.models import Account, ImportBatch, Transaction


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


def existing_ids_by_dedup_key(session: Session, keys: Collection[str]) -> dict[str, int]:
    if not keys:
        return {}
    rows = session.execute(
        select(Transaction.dedup_key, Transaction.id).where(Transaction.dedup_key.in_(keys))
    )
    return {key: transaction_id for key, transaction_id in rows}
