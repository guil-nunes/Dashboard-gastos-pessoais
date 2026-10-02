"""Mês de competência (R3) e o mês da 1ª parcela usado na identidade do grupo (R10)."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from app.domain.installments import InstallmentInfo, InstallmentLine
from app.domain.months import YearMonth


def competence_by_line_date(line_date: date) -> YearMonth:
    """Nubank cartão (à vista e qualquer parcela) e lançamentos de conta: mês da data da linha."""
    return YearMonth.of(line_date)


def itau_card_competence(purchase_date: date, installment: InstallmentInfo | None) -> YearMonth:
    """Itaú cartão: toda parcela traz a data da compra, então n/N cai em mês da compra + (n−1)."""
    base = YearMonth.of(purchase_date)
    return base.plus(installment.number - 1) if installment else base


def first_installment_month_nubank(line_date: date, number: int) -> YearMonth:
    return YearMonth.of(line_date).plus(-(number - 1))


def first_installment_month_itau(purchase_date: date) -> YearMonth:
    return YearMonth.of(purchase_date)


def apply_anticipation(
    lines: Sequence[InstallmentLine], ordinals: Sequence[int]
) -> list[YearMonth]:
    """Q14: parcelas do mesmo grupo no mesmo arquivo recebem a competência da menor delas.

    `ordinals` vem de `keys.installment_ordinals(lines)`. Devolve a competência ajustada de cada
    linha, na ordem de entrada. A identidade do grupo não muda, só a competência.
    """
    groups: dict[tuple, list[int]] = defaultdict(list)
    for index, (line, ordinal) in enumerate(zip(lines, ordinals, strict=True)):
        groups[(line.root, line.total, line.first_month, ordinal)].append(index)

    adjusted = [line.competence for line in lines]
    for indices in groups.values():
        if len({lines[i].number for i in indices}) < 2:
            continue
        earliest = min(indices, key=lambda i: lines[i].number)
        for i in indices:
            adjusted[i] = lines[earliest].competence
    return adjusted
