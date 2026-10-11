"""Consultas da classificação: contexto das estratégias 1–3 e titular da conta."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classification.base import ClassifierContext, KeywordRuleEntry, MemoryEntry
from app.repo.models import Account, BankCategoryMap, Category, KeywordRule, MerchantMemory


def load_context(session: Session) -> ClassifierContext:
    """Categorias inativas nunca são sugeridas: a memória perde a categoria, regras e mapa saem."""
    active = set(session.scalars(select(Category.id).where(Category.is_active)))
    memory = {
        row.merchant_key: MemoryEntry(
            row.category_id if row.category_id in active else None, row.kind, row.ignore_reason
        )
        for row in session.scalars(select(MerchantMemory))
    }
    rules = tuple(
        KeywordRuleEntry(row.pattern, row.match_type, row.category_id, row.kind)
        for row in session.scalars(
            select(KeywordRule).order_by(KeywordRule.priority, KeywordRule.id)
        )
        if row.category_id in active
    )
    bank_map = {
        row.bank_category.strip().upper(): row.category_id
        for row in session.scalars(select(BankCategoryMap))
        if row.category_id in active
    }
    return ClassifierContext(memory=memory, rules=rules, bank_map=bank_map)


def holder_of(session: Session, bank: str, kind: str, external_account_id: str) -> str | None:
    return session.scalar(
        select(Account.holder).where(
            Account.bank == bank,
            Account.kind == kind,
            Account.external_account_id == external_account_id,
        )
    )
