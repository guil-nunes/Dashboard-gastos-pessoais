"""Consultas usadas pelo estágio `persist` da importação."""

from collections.abc import Collection
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.keys import dedup_key_projected
from app.domain.months import YearMonth
from app.domain.projection import LastReal, plan_projection
from app.repo.models import (
    Account,
    ImportBatch,
    InstallmentGroupOverride,
    Transaction,
    TransactionSource,
)


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


def delete_projected(session: Session, account_ids: Collection[int]) -> None:
    """Apaga as projetadas das contas: precisa vir antes de gravar reais (UNIQUE grupo/número)."""
    if not account_ids:
        return
    session.execute(
        delete(Transaction)
        .where(Transaction.status == "projetada", Transaction.account_id.in_(account_ids))
        .execution_options(synchronize_session="fetch")  # tira as apagadas da identity map
    )
    session.flush()


def rebuild_projected(session: Session, account_ids: Collection[int], now: datetime) -> None:
    """Reconstrói as projetadas (R10) das contas: apaga e regenera a partir das reais.

    Para cada grupo, a partir da maior parcela real `n`, cria `n+1…N` com o valor da última real.
    Categoria: a do override do grupo, senão a da última real. Dado derivado: não depende da
    ordem de importação.
    """
    if not account_ids:
        return
    delete_projected(session, account_ids)
    overrides = {
        row.installment_group_key: row.category_id
        for row in session.scalars(select(InstallmentGroupOverride))
    }
    last_real: dict[str, Transaction] = {}
    reals = session.scalars(
        select(Transaction)
        .where(
            Transaction.status == "real",
            Transaction.account_id.in_(account_ids),
            Transaction.installment_group_key.is_not(None),
            Transaction.installment_first_month.is_not(None),
        )
        .order_by(Transaction.installment_group_key, Transaction.installment_number)
    )
    for transaction in reals:
        last_real[transaction.installment_group_key] = transaction  # ascendente: fica a maior

    for group_key, last in last_real.items():
        specs = plan_projection(
            LastReal(
                description_raw=last.description_raw,
                number=last.installment_number,
                total=last.installment_total,
                first_month=YearMonth.parse(last.installment_first_month),
                occurred_on=last.occurred_on,
            )
        )
        for spec in specs:
            if group_key in overrides:
                category_id, source, confidence = overrides[group_key], "manual", 1.0
            else:
                category_id, source, confidence = (
                    last.category_id,
                    last.category_source,
                    last.category_confidence,
                )
            session.add(
                Transaction(
                    account_id=last.account_id,
                    import_batch_id=None,
                    occurred_on=spec.occurred_on,
                    competence_month=str(spec.competence),
                    amount_cents=last.amount_cents,
                    description_raw=spec.description_raw,
                    merchant_key=last.merchant_key,
                    normalizer_version=last.normalizer_version,
                    kind=last.kind,
                    ignore_reason=last.ignore_reason,
                    category_id=category_id,
                    category_source=source,
                    category_confidence=confidence,
                    installment_number=spec.number,
                    installment_total=last.installment_total,
                    installment_group_key=group_key,
                    installment_first_month=last.installment_first_month,
                    status="projetada",
                    dedup_key=dedup_key_projected(group_key, spec.number),
                    created_at=now,
                )
            )
    session.flush()


def projected_by_description(
    session: Session, account_id: int, descriptions: Collection[str]
) -> dict[str, Transaction]:
    """Projetadas da conta indexadas pela descrição (conferência com a próxima fatura)."""
    if not descriptions:
        return {}
    rows = session.scalars(
        select(Transaction).where(
            Transaction.status == "projetada",
            Transaction.account_id == account_id,
            Transaction.description_raw.in_(descriptions),
        )
    )
    return {row.description_raw: row for row in rows}


def existing_ids_by_dedup_key(session: Session, keys: Collection[str]) -> dict[str, int]:
    if not keys:
        return {}
    rows = session.execute(
        select(Transaction.dedup_key, Transaction.id).where(Transaction.dedup_key.in_(keys))
    )
    return {key: transaction_id for key, transaction_id in rows}
