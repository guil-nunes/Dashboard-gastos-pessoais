"""Gastos recorrentes (spec R9), calculados sob demanda a partir das despesas reais.

Parcelas e projetadas nunca entram. O IOF (mesmo `merchant_key` da compra) é somado à compra de
origem antes da análise (Q10). "Não é recorrente" é um override por `merchant_key`.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.dashboard import dashboard_clause
from app.config import get_settings
from app.domain.recurrence import Occurrence, RecurrenceParams, detect, merge_iof
from app.repo.models import RecurrenceOverride, Transaction

_IOF = re.compile(r'^IOF de "', re.IGNORECASE)


@dataclass(frozen=True)
class RecurringItem:
    merchant_key: str
    description: str
    average_cents: int
    last_cents: int  # inclui o IOF agregado
    last_on: date
    last_competence: str
    months_count: int
    dismissed: bool


def default_params() -> RecurrenceParams:
    settings = get_settings()
    return RecurrenceParams(
        min_occurrences=settings.recurrence_min_occurrences,
        min_days=settings.recurrence_min_days,
        max_days=settings.recurrence_max_days,
        tolerance_pct=settings.recurrence_tolerance_pct,
    )


def merchant_exists(session: Session, merchant_key: str) -> bool:
    return (
        session.scalar(
            select(Transaction.id).where(Transaction.merchant_key == merchant_key).limit(1)
        )
        is not None
    )


def detect_recurrences(
    session: Session, params: RecurrenceParams, up_to_month: str | None = None
) -> list[RecurringItem]:
    """Séries recorrentes, incluindo as marcadas "não é recorrente" (`dismissed`).

    `up_to_month` ignora lançamentos de competência posterior, para reconstruir o que se sabia
    naquele mês.
    """
    query = select(Transaction).where(
        dashboard_clause(),
        Transaction.installment_number.is_(None),
        Transaction.amount_cents > 0,
    )
    if up_to_month is not None:
        query = query.where(Transaction.competence_month <= up_to_month)

    purchases: dict[str, list[Occurrence]] = defaultdict(list)
    iofs: dict[str, list[Occurrence]] = defaultdict(list)
    names: dict[str, tuple[date, str]] = {}
    for t in session.scalars(query):
        occurrence = Occurrence(t.occurred_on, t.amount_cents, t.competence_month)
        if _IOF.match(t.description_raw):
            iofs[t.merchant_key].append(occurrence)
            continue
        purchases[t.merchant_key].append(occurrence)
        if t.merchant_key not in names or t.occurred_on >= names[t.merchant_key][0]:
            names[t.merchant_key] = (t.occurred_on, t.description_raw)

    dismissed = {
        o.merchant_key
        for o in session.scalars(
            select(RecurrenceOverride).where(RecurrenceOverride.is_recurring.is_(False))
        )
    }
    items = []
    for key, occurrences in purchases.items():
        series = detect(merge_iof(occurrences, iofs.get(key, [])), params)
        if series is None:
            continue
        last = series[-1]
        items.append(
            RecurringItem(
                merchant_key=key,
                description=names[key][1],
                average_cents=round(sum(o.cents for o in series) / len(series)),
                last_cents=last.cents,
                last_on=last.occurred_on,
                last_competence=last.competence_month,
                months_count=len({o.competence_month for o in series}),
                dismissed=key in dismissed,
            )
        )
    items.sort(key=lambda i: (-i.average_cents, i.merchant_key))
    return items
