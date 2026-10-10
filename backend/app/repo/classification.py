"""Consultas da classificação: contexto das estratégias 1–3 e titular da conta."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classification.base import ClassifierContext, KeywordRuleEntry, MemoryEntry
from app.repo.models import Account, BankCategoryMap, KeywordRule, MerchantMemory


def load_context(session: Session) -> ClassifierContext:
    memory = {
        row.merchant_key: MemoryEntry(row.category_id, row.kind, row.ignore_reason)
        for row in session.scalars(select(MerchantMemory))
    }
    rules = tuple(
        KeywordRuleEntry(row.pattern, row.match_type, row.category_id, row.kind)
        for row in session.scalars(
            select(KeywordRule).order_by(KeywordRule.priority, KeywordRule.id)
        )
    )
    bank_map = {
        row.bank_category.strip().upper(): row.category_id
        for row in session.scalars(select(BankCategoryMap))
        if row.category_id is not None
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
