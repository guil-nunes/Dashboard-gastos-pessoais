"""Detector de recorrência (spec R9), puro: sem banco e sem I/O.

Uma série é recorrente quando o mesmo `merchant_key` tem ≥ N ocorrências, com intervalos entre
`min_days` e `max_days` e cada valor a ±`tolerance_pct`% da mediana. Vale a sequência mais recente:
uma quebra antiga não invalida a série atual. Parâmetros vêm de configuração, nunca fixos aqui.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

IOF_WINDOW_DAYS = 7  # o IOF vem no mesmo dia da compra ou logo depois


@dataclass(frozen=True)
class RecurrenceParams:
    min_occurrences: int = 3
    min_days: int = 25
    max_days: int = 35
    tolerance_pct: int = 10


@dataclass(frozen=True)
class Occurrence:
    occurred_on: date
    cents: int
    competence_month: str = ""


def merge_iof(
    purchases: list[Occurrence],
    iofs: list[Occurrence],
    window_days: int = IOF_WINDOW_DAYS,
) -> list[Occurrence]:
    """Soma cada IOF à compra de origem mais próxima que não seja posterior a ele (Q10)."""
    merged = sorted(purchases, key=lambda o: o.occurred_on)
    for iof in sorted(iofs, key=lambda o: o.occurred_on):
        origin = max(
            (
                i
                for i, p in enumerate(merged)
                if p.occurred_on <= iof.occurred_on
                and iof.occurred_on - p.occurred_on <= timedelta(days=window_days)
            ),
            key=lambda i: merged[i].occurred_on,
            default=None,
        )
        if origin is not None:
            p = merged[origin]
            merged[origin] = Occurrence(p.occurred_on, p.cents + iof.cents, p.competence_month)
    return merged


def _within_tolerance(occurrences: list[Occurrence], tolerance_pct: int) -> bool:
    twice_median = round(2 * median(o.cents for o in occurrences))
    return all(
        abs(2 * o.cents - twice_median) * 100 <= tolerance_pct * twice_median for o in occurrences
    )


def detect(occurrences: list[Occurrence], params: RecurrenceParams) -> list[Occurrence] | None:
    """Devolve a sequência recorrente mais recente (em ordem de data), ou None."""
    ordered = sorted(occurrences, key=lambda o: o.occurred_on)
    if not ordered:
        return None

    start = len(ordered) - 1  # estende a cadeia de intervalos válidos para trás
    while start > 0:
        gap = (ordered[start].occurred_on - ordered[start - 1].occurred_on).days
        if not params.min_days <= gap <= params.max_days:
            break
        start -= 1

    chain = ordered[start:]
    for first in range(len(chain) - params.min_occurrences + 1):  # prefere a série mais longa
        candidate = chain[first:]
        if _within_tolerance(candidate, params.tolerance_pct):
            return candidate
    return None
