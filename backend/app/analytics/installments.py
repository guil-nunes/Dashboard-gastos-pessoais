"""Parcelas futuras (spec R10): o que já está comprometido por mês e o que pede revisão.

Lê as projetadas (dado derivado, reconstruído a cada importação). Um grupo é sinalizado quando a
próxima parcela projetada cai em um mês que a conta já cobre com lançamentos reais, sem a real
correspondente (compra cancelada ou antecipada).
"""

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.repo.models import Account, Transaction


@dataclass(frozen=True)
class UpcomingItem:
    group_key: str
    description: str
    number: int
    total: int
    amount_cents: int
    category_id: int | None
    account_name: str


@dataclass(frozen=True)
class UpcomingMonth:
    month: str
    total_cents: int
    items: list[UpcomingItem]


@dataclass(frozen=True)
class FlaggedGroup:
    group_key: str
    description: str
    account_name: str
    next_number: int
    total: int
    expected_month: str
    covered_through: str
    remaining: int  # parcelas projetadas que ficam em aberto no grupo
    amount_cents: int


@dataclass(frozen=True)
class Upcoming:
    months: list[UpcomingMonth]
    flagged: list[FlaggedGroup]


def upcoming(session: Session) -> Upcoming:
    covered = dict(
        session.execute(
            select(Transaction.account_id, func.max(Transaction.competence_month))
            .where(Transaction.status == "real")
            .group_by(Transaction.account_id)
        ).all()
    )
    rows = session.execute(
        select(Transaction, Account.name)
        .join(Account, Account.id == Transaction.account_id)
        .where(Transaction.status == "projetada")
        .order_by(Transaction.installment_group_key, Transaction.installment_number)
    ).all()

    groups: dict[str, list[tuple[Transaction, str]]] = defaultdict(list)
    for transaction, account_name in rows:
        groups[transaction.installment_group_key].append((transaction, account_name))

    by_month: dict[str, list[UpcomingItem]] = defaultdict(list)
    flagged: list[FlaggedGroup] = []
    for group_key, items in groups.items():
        next_transaction, account_name = items[0]  # menor número projetado
        through = covered.get(next_transaction.account_id)
        if through is not None and next_transaction.competence_month <= through:
            flagged.append(
                FlaggedGroup(
                    group_key=group_key,
                    description=next_transaction.description_raw,
                    account_name=account_name,
                    next_number=next_transaction.installment_number,
                    total=next_transaction.installment_total,
                    expected_month=next_transaction.competence_month,
                    covered_through=through,
                    remaining=len(items),
                    amount_cents=next_transaction.amount_cents,
                )
            )
            continue
        for transaction, name in items:
            by_month[transaction.competence_month].append(
                UpcomingItem(
                    group_key=group_key,
                    description=transaction.description_raw,
                    number=transaction.installment_number,
                    total=transaction.installment_total,
                    amount_cents=transaction.amount_cents,
                    category_id=transaction.category_id,
                    account_name=name,
                )
            )

    months = [
        UpcomingMonth(
            month=month,
            total_cents=sum(item.amount_cents for item in items),
            items=sorted(items, key=lambda i: (i.description, i.number)),
        )
        for month, items in sorted(by_month.items())
    ]
    flagged.sort(key=lambda g: (g.expected_month, g.description))
    return Upcoming(months=months, flagged=flagged)
