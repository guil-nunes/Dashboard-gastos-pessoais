"""Agregações do dashboard de fechamento (spec R8), calculadas sob demanda.

Só `status = 'real'` e `kind = 'despesa'` entram; a soma é com sinal, então estorno abate.
O mesmo `dashboard_clause` serve resumo, histórico e drill-down, para os números não divergirem.
"""

from dataclasses import dataclass, field

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.orm import Session

from app.repo.models import Account, Category, Transaction


def dashboard_clause(
    bank: str | None = None, account_kind: str | None = None
) -> ColumnElement[bool]:
    clauses = [Transaction.status == "real", Transaction.kind == "despesa"]
    if bank is not None or account_kind is not None:
        accounts = select(Account.id)
        if bank is not None:
            accounts = accounts.where(Account.bank == bank)
        if account_kind is not None:
            accounts = accounts.where(Account.kind == account_kind)
        clauses.append(Transaction.account_id.in_(accounts))
    return and_(*clauses)


def previous_month(month: str) -> str:
    year, number = int(month[:4]), int(month[5:])
    return f"{year - 1}-12" if number == 1 else f"{year}-{number - 1:02d}"


def next_month(month: str) -> str:
    year, number = int(month[:4]), int(month[5:])
    return f"{year + 1}-01" if number == 12 else f"{year}-{number + 1:02d}"


@dataclass(frozen=True)
class CategoryTotal:
    category_id: int | None  # None = "Sem categoria"
    name: str
    color: str | None
    total_cents: int
    count: int
    pct: float | None  # sobre o total do mês; None quando o total não é positivo


@dataclass(frozen=True)
class MonthSummary:
    month: str
    total_cents: int
    previous_month: str
    previous_total_cents: int
    delta_cents: int
    delta_pct: float | None  # None sem base de comparação
    categories: list[CategoryTotal]


@dataclass(frozen=True)
class HistoryMonth:
    month: str
    total_cents: int
    by_category: dict[int | None, int] = field(default_factory=dict)


@dataclass(frozen=True)
class History:
    months: list[HistoryMonth]
    categories: list[Category]


def _month_total(session: Session, month: str, clause: ColumnElement[bool]) -> int:
    total = session.scalar(
        select(func.sum(Transaction.amount_cents)).where(
            clause, Transaction.competence_month == month
        )
    )
    return int(total or 0)


def month_summary(
    session: Session, month: str, bank: str | None = None, account_kind: str | None = None
) -> MonthSummary:
    clause = dashboard_clause(bank, account_kind)
    rows = session.execute(
        select(
            Transaction.category_id,
            func.sum(Transaction.amount_cents),
            func.count(),
        )
        .where(clause, Transaction.competence_month == month)
        .group_by(Transaction.category_id)
    ).all()
    names = {c.id: c for c in session.scalars(select(Category))}

    total = sum(int(cents) for _, cents, _ in rows)
    categories = [
        CategoryTotal(
            category_id=category_id,
            name=names[category_id].name if category_id is not None else "Sem categoria",
            color=names[category_id].color if category_id is not None else None,
            total_cents=int(cents),
            count=count,
            pct=round(int(cents) / total * 100, 1) if total > 0 else None,
        )
        for category_id, cents, count in rows
    ]
    categories.sort(key=lambda c: (-c.total_cents, c.name))

    previous = previous_month(month)
    previous_total = _month_total(session, previous, clause)
    return MonthSummary(
        month=month,
        total_cents=total,
        previous_month=previous,
        previous_total_cents=previous_total,
        delta_cents=total - previous_total,
        delta_pct=round((total - previous_total) / previous_total * 100, 1)
        if previous_total > 0
        else None,
        categories=categories,
    )


def history(session: Session, bank: str | None = None, account_kind: str | None = None) -> History:
    clause = dashboard_clause(bank, account_kind)
    rows = session.execute(
        select(
            Transaction.competence_month,
            Transaction.category_id,
            func.sum(Transaction.amount_cents),
        )
        .where(clause)
        .group_by(Transaction.competence_month, Transaction.category_id)
    ).all()
    if not rows:
        return History(months=[], categories=[])

    by_month: dict[str, dict[int | None, int]] = {}
    for month, category_id, cents in rows:
        by_month.setdefault(month, {})[category_id] = int(cents)

    ordered = sorted(by_month)
    months, current = [], ordered[0]
    while current <= ordered[-1]:  # preenche meses sem despesa
        values = by_month.get(current, {})
        months.append(HistoryMonth(current, sum(values.values()), values))
        current = next_month(current)

    used = {cid for m in months for cid in m.by_category if cid is not None}
    categories = list(
        session.scalars(select(Category).where(Category.id.in_(used)).order_by(Category.id))
    )
    return History(months=months, categories=categories)
