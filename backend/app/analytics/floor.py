"""Piso do mês seguinte (spec R12): parcelas + recorrentes. É um piso, não uma previsão.

Para o mês M o alvo é M+1. Só se usa o que se sabia em M (competência ≤ M) nos recorrentes, então
o piso de um mês passado pode ser comparado com o gasto real daquele mês. Recorrente "ativo" é o
que teve lançamento em M ou M-1.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.dashboard import dashboard_clause, next_month, previous_month
from app.analytics.installments import UpcomingItem, upcoming
from app.analytics.recurrence import RecurringItem, detect_recurrences
from app.domain.recurrence import RecurrenceParams
from app.repo.models import Account, Transaction


@dataclass(frozen=True)
class Floor:
    month: str
    target_month: str
    total_cents: int
    installments_cents: int
    installments: list[UpcomingItem]
    recurrences_cents: int
    recurrences: list[RecurringItem]


def _installments(session: Session, target: str) -> list[UpcomingItem]:
    items = [m.items for m in upcoming(session).months if m.month == target]
    projected = items[0] if items else []

    # Parcelas já reais no mês-alvo (mês passado): a projetada virou real e continua um compromisso.
    rows = session.execute(
        select(Transaction, Account.name)
        .join(Account, Account.id == Transaction.account_id)
        .where(
            dashboard_clause(),
            Transaction.installment_number.is_not(None),
            Transaction.competence_month == target,
        )
    ).all()
    real = [
        UpcomingItem(
            group_key=t.installment_group_key,
            description=t.description_raw,
            number=t.installment_number,
            total=t.installment_total,
            amount_cents=t.amount_cents,
            category_id=t.category_id,
            account_name=name,
        )
        for t, name in rows
    ]
    return sorted(projected + real, key=lambda i: (i.description, i.number))


def floor(session: Session, month: str, params: RecurrenceParams) -> Floor:
    target = next_month(month)
    installments = _installments(session, target)
    recurrences = [
        r
        for r in detect_recurrences(session, params, up_to_month=month)
        if not r.dismissed and r.last_competence >= previous_month(month)
    ]
    installments_cents = sum(i.amount_cents for i in installments)
    recurrences_cents = sum(r.last_cents for r in recurrences)
    return Floor(
        month=month,
        target_month=target,
        total_cents=installments_cents + recurrences_cents,
        installments_cents=installments_cents,
        installments=installments,
        recurrences_cents=recurrences_cents,
        recurrences=recurrences,
    )
