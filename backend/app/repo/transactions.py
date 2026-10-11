"""Consultas da revisão (R7): transações, estabelecimentos pendentes, categorias e regras."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session

from app.domain.review import LOW_CONFIDENCE_THRESHOLD
from app.repo.models import Account, Category, KeywordRule, Transaction


def pending_clause() -> ColumnElement[bool]:
    """Fila de revisão: despesa real não revisada, sem categoria, de baixa confiança ou com
    sugestão a confirmar. Memória e regras com categoria ficam fora, mas seguem listáveis."""
    return and_(
        Transaction.status == "real",
        Transaction.reviewed_at.is_(None),
        Transaction.kind == "despesa",
        or_(
            Transaction.category_id.is_(None),
            Transaction.category_confidence.is_(None),
            Transaction.category_confidence < LOW_CONFIDENCE_THRESHOLD,
            Transaction.suggested_ignore_reason.is_not(None),
        ),
    )


def list_transactions(
    session: Session,
    *,
    month: str | None = None,
    account_id: int | None = None,
    category_id: int | None = None,
    source: str | None = None,
    merchant_key: str | None = None,
    kind: str | None = None,
    status: str | None = None,
    bank: str | None = None,
    account_kind: str | None = None,
    without_category: bool = False,
    pending: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[tuple[Transaction, Account]], int]:
    filters = []
    if month is not None:
        filters.append(Transaction.competence_month == month)
    if account_id is not None:
        filters.append(Transaction.account_id == account_id)
    if category_id is not None:
        filters.append(Transaction.category_id == category_id)
    if source is not None:
        filters.append(Transaction.category_source == source)
    if merchant_key is not None:
        filters.append(Transaction.merchant_key == merchant_key)
    if kind is not None:
        filters.append(Transaction.kind == kind)
    if status is not None:
        filters.append(Transaction.status == status)
    if bank is not None or account_kind is not None:
        accounts = select(Account.id)
        if bank is not None:
            accounts = accounts.where(Account.bank == bank)
        if account_kind is not None:
            accounts = accounts.where(Account.kind == account_kind)
        filters.append(Transaction.account_id.in_(accounts))
    if without_category:
        filters.append(Transaction.category_id.is_(None))
    if pending:
        filters.append(pending_clause())

    total = session.scalar(select(func.count()).select_from(Transaction).where(*filters))
    rows = session.execute(
        select(Transaction, Account)
        .join(Account, Account.id == Transaction.account_id)
        .where(*filters)
        .order_by(Transaction.occurred_on.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [(transaction, account) for transaction, account in rows], total or 0


def pending_for_merchant(
    session: Session, merchant_key: str, ids: list[int] | None = None
) -> list[Transaction]:
    query = select(Transaction).where(pending_clause(), Transaction.merchant_key == merchant_key)
    if ids is not None:
        query = query.where(Transaction.id.in_(ids))
    return list(session.scalars(query.order_by(Transaction.id)))


@dataclass(frozen=True)
class PendingMerchant:
    merchant_key: str
    count: int
    total_cents: int
    sample_description: str
    category_id: int | None  # só quando todas concordam
    category_source: str | None
    min_confidence: float | None
    suggested_ignore_reason: str | None  # só quando todas concordam
    latest_on: date


def pending_merchants(session: Session) -> list[PendingMerchant]:
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for transaction in session.scalars(select(Transaction).where(pending_clause())):
        groups[transaction.merchant_key].append(transaction)

    merchants = []
    for key, items in groups.items():
        categories = {t.category_id for t in items}
        sources = {t.category_source for t in items}
        suggestions = {t.suggested_ignore_reason for t in items}
        confidences = [t.category_confidence for t in items if t.category_confidence is not None]
        merchants.append(
            PendingMerchant(
                merchant_key=key,
                count=len(items),
                total_cents=sum(t.amount_cents for t in items),
                sample_description=items[0].description_raw,
                category_id=categories.pop() if len(categories) == 1 else None,
                category_source=sources.pop() if len(sources) == 1 else None,
                min_confidence=min(confidences) if confidences else None,
                suggested_ignore_reason=suggestions.pop() if len(suggestions) == 1 else None,
                latest_on=max(t.occurred_on for t in items),
            )
        )
    return sorted(merchants, key=lambda m: (-m.count, m.merchant_key))


def list_categories(session: Session) -> list[Category]:
    return list(session.scalars(select(Category).order_by(Category.id)))


def get_category(session: Session, category_id: int) -> Category | None:
    return session.get(Category, category_id)


def category_name_taken(session: Session, name: str, except_id: int | None = None) -> bool:
    query = select(Category.id).where(Category.name == name)
    if except_id is not None:
        query = query.where(Category.id != except_id)
    return session.scalar(query) is not None


def list_rules(session: Session) -> list[KeywordRule]:
    return list(session.scalars(select(KeywordRule).order_by(KeywordRule.priority, KeywordRule.id)))
