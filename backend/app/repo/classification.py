"""Consultas da classificação: titular da conta."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repo.models import Account


def holder_of(session: Session, bank: str, kind: str, external_account_id: str) -> str | None:
    return session.scalar(
        select(Account.holder).where(
            Account.bank == bank,
            Account.kind == kind,
            Account.external_account_id == external_account_id,
        )
    )
