"""Parcelas projetadas (spec R10): quais números faltam, em que mês e com que descrição.

Puro: recebe a última parcela real do grupo e devolve as `n+1…N` que ainda não existem.
"""

import calendar
from dataclasses import dataclass
from datetime import date

from app.domain.installments import projected_description
from app.domain.months import YearMonth


@dataclass(frozen=True)
class LastReal:
    """A maior parcela real conhecida de um grupo."""

    description_raw: str
    number: int
    total: int
    first_month: YearMonth  # mês da parcela 1, pela data da linha (antes da antecipação)
    occurred_on: date


@dataclass(frozen=True)
class ProjectedSpec:
    number: int
    competence: YearMonth
    occurred_on: date
    description_raw: str


def plan_projection(last: LastReal) -> list[ProjectedSpec]:
    """Parcelas `n+1…N`: competência `first_month + (k−1)`; sem sobra quando `n == N`."""
    return [
        ProjectedSpec(
            number=number,
            competence=last.first_month.plus(number - 1),
            occurred_on=add_months(last.occurred_on, number - last.number),
            description_raw=projected_description(last.description_raw, number),
        )
        for number in range(last.number + 1, last.total + 1)
    ]


def add_months(day: date, months: int) -> date:
    """Soma meses mantendo o dia, limitado ao último dia do mês de destino (31/01 → 28/02)."""
    target = YearMonth.of(day).plus(months)
    last_day = calendar.monthrange(target.year, target.month)[1]
    return date(target.year, target.month, min(day.day, last_day))
