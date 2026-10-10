"""Operações de classificação sobre o banco: correção manual e reclassificação (spec R6, R7).

Transações com `reviewed_at` preenchido nunca são sobrescritas por estratégia automática.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classification.base import ClassificationInput
from app.classification.pipeline import build_strategies, classify
from app.repo.classification import load_context
from app.repo.models import (
    IGNORE_REASONS,
    TRANSACTION_KINDS,
    Account,
    Category,
    MerchantMemory,
    Transaction,
)
from app.repo.transactions import pending_for_merchant


def reclassify_unreviewed(
    session: Session, *, merchant_key: str | None = None, account_id: int | None = None
) -> int:
    """Reaplica a cadeia de estratégias às transações reais ainda não revisadas.

    Devolve quantas mudaram. A Estratégia 0 continua primeiro, então regras estruturais não
    são sobrepostas pela memória.
    """
    query = (
        select(Transaction, Account)
        .join(Account, Account.id == Transaction.account_id)
        .where(Transaction.status == "real", Transaction.reviewed_at.is_(None))
    )
    if merchant_key is not None:
        query = query.where(Transaction.merchant_key == merchant_key)
    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)

    strategies = build_strategies(load_context(session))
    changed = 0
    for transaction, account in session.execute(query):
        result = classify(
            ClassificationInput(
                account_kind=account.kind,
                amount_cents=transaction.amount_cents,
                description_raw=transaction.description_raw,
                merchant_key=transaction.merchant_key,
                bank_category=transaction.bank_category,
                holder=account.holder,
            ),
            strategies,
        )
        new = (
            result.kind,
            result.ignore_reason,
            result.suggested_ignore_reason,
            result.category_id,
            result.source,
            result.confidence,
        )
        old = (
            transaction.kind,
            transaction.ignore_reason,
            transaction.suggested_ignore_reason,
            transaction.category_id,
            transaction.category_source,
            transaction.category_confidence,
        )
        if new == old:
            continue
        (
            transaction.kind,
            transaction.ignore_reason,
            transaction.suggested_ignore_reason,
            transaction.category_id,
            transaction.category_source,
            transaction.category_confidence,
        ) = new
        changed += 1
    session.flush()
    return changed


def apply_correction(
    session: Session,
    transaction_id: int,
    *,
    kind: str,
    ignore_reason: str | None,
    category_id: int | None,
    now: datetime,
) -> Transaction | None:
    """Correção manual (ou confirmação de sugestão): grava, lembra e recategoriza o resto.

    Atualiza a memória do estabelecimento e reclassifica as não revisadas do mesmo
    `merchant_key`. `investimento` vale só para esta transação: a memória nunca o guarda (Q15).
    """
    transaction = session.get(Transaction, transaction_id)
    if transaction is None:
        return None

    _set_manual(transaction, kind, ignore_reason, category_id, now)
    if transaction.ignore_reason != "investimento":
        _remember(session, transaction, now)
    session.flush()
    reclassify_unreviewed(session, merchant_key=transaction.merchant_key)
    return transaction


def validate_target(
    session: Session, kind: str, ignore_reason: str | None, category_id: int | None
) -> None:
    """Combinação aceita pela revisão manual; `ValueError` com mensagem para o usuário."""
    if kind not in TRANSACTION_KINDS:
        raise ValueError("Tipo inválido")
    if kind == "ignorar" and ignore_reason not in IGNORE_REASONS:
        raise ValueError("Motivo obrigatório para transações ignoradas")
    if kind == "despesa" and ignore_reason is not None:
        raise ValueError("Despesa não tem motivo de ignorar")
    if category_id is not None:
        category = session.get(Category, category_id)
        if category is None:
            raise ValueError("Categoria não encontrada")
        if not category.is_active:
            raise ValueError("Categoria inativa")


def confirm_transaction(session: Session, transaction_id: int, now: datetime) -> Transaction | None:
    """Confirma a sugestão sem alterar nada: só marca como revisada (R6).

    Mantém `category_source`/`confidence` (a métrica de categorização automática depende
    disso) e não grava memória.
    """
    transaction = session.get(Transaction, transaction_id)
    if transaction is not None and transaction.reviewed_at is None:
        transaction.reviewed_at = now
        session.flush()
    return transaction


def bulk_apply(
    session: Session,
    merchant_key: str,
    *,
    kind: str,
    ignore_reason: str | None,
    category_id: int | None,
    now: datetime,
    ids: list[int] | None = None,
) -> int:
    """Aplica tipo/categoria às pendentes do estabelecimento; a memória é gravada uma vez."""
    targets = pending_for_merchant(session, merchant_key, ids)
    if not targets:
        return 0
    first, *rest = targets
    apply_correction(
        session, first.id, kind=kind, ignore_reason=ignore_reason, category_id=category_id, now=now
    )
    for transaction in rest:
        _set_manual(transaction, kind, ignore_reason, category_id, now)
    session.flush()
    return len(targets)


def bulk_confirm(
    session: Session, merchant_key: str, *, now: datetime, ids: list[int] | None = None
) -> int:
    targets = pending_for_merchant(session, merchant_key, ids)
    for transaction in targets:
        transaction.reviewed_at = now
    session.flush()
    return len(targets)


def _set_manual(
    transaction: Transaction,
    kind: str,
    ignore_reason: str | None,
    category_id: int | None,
    now: datetime,
) -> None:
    transaction.kind = kind
    transaction.ignore_reason = ignore_reason if kind == "ignorar" else None
    transaction.category_id = category_id
    transaction.category_source = "manual"
    transaction.category_confidence = 1.0
    transaction.reviewed_at = now
    if kind == "ignorar" and ignore_reason == transaction.suggested_ignore_reason:
        transaction.suggested_ignore_reason = None  # sugestão confirmada


def _remember(session: Session, transaction: Transaction, now: datetime) -> None:
    memory = session.get(MerchantMemory, transaction.merchant_key)
    if memory is None:
        memory = MerchantMemory(merchant_key=transaction.merchant_key)
        session.add(memory)
    memory.kind = transaction.kind
    memory.ignore_reason = transaction.ignore_reason
    memory.category_id = transaction.category_id
    memory.updated_at = now
